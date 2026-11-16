"""
Procesamiento, homologación e integración de datos DANE y RIPS.

Este módulo construye el dataset de entrenamiento a partir de los archivos
RAW originales, aplicando las reglas de procesamiento definidas en el
documento de la tarea.

Flujo:
    1. Detectar y validar el año de ambas fuentes.
    2. Procesar DANE: calcular la variable objetivo por municipio-grupo.
    3. Procesar RIPS: homologar diagnósticos, clasificar atenciones, agregar.
    4. Integrar ambas fuentes por municipio-grupo diagnóstico.
    5. Validar y exportar el dataset final.
"""

import fcntl
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.eda import (
    leer_csv_raw,
    encontrar_archivo_raw,
    obtener_archivo_hash,
    DANE_RAW_PATTERN,
    RIPS_RAW_PATTERN,
)
from src.diagnostic_mapping import (
    homologar_diagnostico,
    extraer_codigo_cie10,
    LISTA_105,
    todos_los_codigos_cau_homol,
    CATEGORIA_C50_AUXILIAR,
    es_categoria_c50,
)

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
REPORTS_DIR = ROOT / "reports"

DATASET_FILE = "dataset_entrenamiento.csv"
METADATA_FILE = "processing_metadata.json"
REPORT_FILE = "processing_report.json"
LOCK_FILE = ".processing_lock"

# Bloqueo de thread para FastAPI single-process
_processing_lock = threading.Lock()

# Clasificación de tipos de atención RIPS
TIPO_ATENCION_MAP = {
    "CONSULTAS": "consultas",
    "PROCEDIMIENTOS DE SALUD": "procedimientos",
    "URGENCIAS": "urgencias",
    "HOSPITALIZACIONES": "hospitalizaciones",
}


# ==========================================
# DETECCIÓN Y VALIDACIÓN DEL AÑO
# ==========================================

def detectar_anio(df, columna, fuente):
    """
    Detecta el año de un DataFrame y valida que sea único.

    Maneja correctamente valores nulos reales (None, NaN), cadenas vacías,
    representaciones numéricas como "2021.0", y evita TypeError en sorted().

    Args:
        df: DataFrame con la columna de año.
        columna: Nombre de la columna del año ("ANO" o "Año").
        fuente: Nombre de la fuente ("DANE" o "RIPS") para mensajes.

    Returns:
        Tupla (anio, errores) donde anio es el año detectado o None,
        y errores es una lista de problemas encontrados.
    """
    errores = []

    if columna not in df.columns:
        errores.append(f"La columna '{columna}' no existe en {fuente}.")
        return None, errores

    serie = df[columna]

    # Valores nulos reales (None, NaN)
    nulos_count = int(serie.isna().sum())
    if nulos_count > 0:
        errores.append(
            f"{fuente}: {nulos_count} registros con valor nulo en '{columna}'."
        )

    # Reemplazar nulos con "" antes de convertir a string
    # para evitar que None se convierta en "None" literal
    serie_str = serie.fillna("").astype(str).str.strip()

    # Valores vacíos después de conversión (incluye "nan" literal)
    vacios = ((serie_str == "") | (serie_str == "nan")).sum() - nulos_count
    if vacios > 0:
        errores.append(
            f"{fuente}: {vacios} registros con valor vacío en '{columna}'."
        )

    # Filtrar valores no vacíos y no nulos
    valores = serie_str[serie_str.ne("") & (serie_str != "nan")].unique()

    # Validar que todos sean años válidos
    anos_validos = []
    anos_invalidos = set()

    for v in valores:
        try:
            # Aceptar "2021.0" como año válido
            anio_float = float(v)
            # Rechazar fraccionarios
            if anio_float != int(anio_float):
                anos_invalidos.add(v)
                continue
            anio = int(anio_float)
            if 1900 <= anio <= 2100:
                anos_validos.append(anio)
            else:
                anos_invalidos.add(v)
        except (ValueError, OverflowError):
            anos_invalidos.add(v)

    if anos_invalidos:
        errores.append(
            f"{fuente}: Valores inválidos en '{columna}': {sorted(anos_invalidos)}."
        )
        if not anos_validos:
            return None, errores

    anos_unicos = sorted(set(anos_validos))

    if len(anos_unicos) == 0:
        errores.append(f"{fuente}: No se encontró ningún año válido en '{columna}'.")
        return None, errores

    if len(anos_unicos) > 1:
        errores.append(
            f"{fuente}: Se detectaron múltiples años: {anos_unicos}. "
            "El procesamiento solo admite un único año por ejecución."
        )
        return None, errores

    # Si hay valores inválidos, detener la ejecución
    if anos_invalidos:
        return None, errores

    return anos_unicos[0], errores


def validar_anios_coincidentes(anio_dane, errores_dane, anio_rips, errores_rips):
    """
    Verifica que ambas fuentes correspondan al mismo año.

    Returns:
        Tupla (anio, errores_combinados).
    """
    errores = errores_dane + errores_rips

    if anio_dane is None or anio_rips is None:
        return None, errores

    if anio_dane != anio_rips:
        errores.append(
            f"Los años no coinciden: DANE={anio_dane}, RIPS={anio_rips}. "
            "Ambas fuentes deben corresponder al mismo año."
        )
        return None, errores

    return anio_dane, errores


# ==========================================
# PROCESAMIENTO DANE
# ==========================================

def procesar_dane(df_dane):
    """
    Procesa el DataFrame DANE y calcula la variable objetivo.

    Valida CODMUNRE, CAU_HOMOL y ASIS_MED antes de procesar.
    Agrupa por CODMUNRE + CAU_HOMOL y calcula
    dane_pct_sin_asistencia.

    Returns:
        DataFrame con columnas:
            cod_municipio, cod_grupo_diagnostico,
            dane_sin_asistencia, dane_total_valido,
            dane_pct_sin_asistencia
        Y un diccionario con estadísticas detalladas.
    """
    stats = {
        "registros_originales": len(df_dane),
        "registros_excluidos": 0,
        "registros_unicos_excluidos": 0,
        "excluidos_cod_municipio_invalido": 0,
        "excluidos_cau_homol_invalido": 0,
        "excluidos_cau_homol_nulo": 0,
        "excluidos_asis_med_invalido": 0,
        "asis_med_nulo": 0,
        "combinaciones_sin_respuestas_validas": 0,
    }

    df_trabajo = df_dane.copy()
    indices_excluidos = set()

    # Asegurar tipos
    df_trabajo["CODMUNRE"] = df_trabajo["CODMUNRE"].astype(str).str.strip()
    df_trabajo["CAU_HOMOL"] = df_trabajo["CAU_HOMOL"].astype(str).str.strip()
    df_trabajo["ASIS_MED"] = df_trabajo["ASIS_MED"].astype(str).str.strip()

    # Validar CODMUNRE: debe ser 5 dígitos numéricos
    codmunre_valido = (
        df_trabajo["CODMUNRE"].str.len() == 5
    ) & df_trabajo["CODMUNRE"].str.isdigit()
    invalidos_codmunre = (~codmunre_valido) & (df_trabajo["CODMUNRE"] != "")
    indices_excluidos.update(df_trabajo[invalidos_codmunre].index)
    stats["excluidos_cod_municipio_invalido"] = int(invalidos_codmunre.sum())

    # Validar CAU_HOMOL: nulos o inválidos
    codigos_validos = set(todos_los_codigos_cau_homol())
    cau_nulo = (df_trabajo["CAU_HOMOL"] == "") | (df_trabajo["CAU_HOMOL"] == "nan")
    stats["excluidos_cau_homol_nulo"] = int(cau_nulo.sum())
    indices_excluidos.update(df_trabajo[cau_nulo].index)

    cau_invalido = (~cau_nulo) & (~df_trabajo["CAU_HOMOL"].isin(codigos_validos))
    stats["excluidos_cau_homol_invalido"] = int(cau_invalido.sum())
    indices_excluidos.update(df_trabajo[cau_invalido].index)

    # Validar ASIS_MED: valores fuera de {1, 2, 3, 9}
    asis_valido_set = {"1", "2", "3", "9"}
    asis_nulo = (df_trabajo["ASIS_MED"] == "") | (df_trabajo["ASIS_MED"] == "nan")
    stats["asis_med_nulo"] = int(asis_nulo.sum())
    # ASIS_MED nulo no excluye el registro, pero no participa en el cálculo

    asis_invalido = (~asis_nulo) & (~df_trabajo["ASIS_MED"].isin(asis_valido_set))
    stats["excluidos_asis_med_invalido"] = int(asis_invalido.sum())
    indices_excluidos.update(df_trabajo[asis_invalido].index)

    stats["registros_unicos_excluidos"] = len(indices_excluidos)
    stats["registros_excluidos"] = len(indices_excluidos)

    # Filtrar registros excluidos
    if indices_excluidos:
        df_trabajo = df_trabajo.drop(indices_excluidos).reset_index(drop=True)

    # Contar sin asistencia (ASIS_MED = 2)
    df_trabajo["es_sin_asistencia"] = (df_trabajo["ASIS_MED"] == "2").astype(int)

    # Contar respuestas válidas (ASIS_MED = 1 o 2)
    df_trabajo["es_respuesta_valida"] = (
        df_trabajo["ASIS_MED"].isin(["1", "2"])
    ).astype(int)

    # Agrupar
    agrupado = df_trabajo.groupby(["CODMUNRE", "CAU_HOMOL"]).agg(
        dane_sin_asistencia=("es_sin_asistencia", "sum"),
        dane_total_valido=("es_respuesta_valida", "sum"),
    ).reset_index()

    # Identificar combinaciones sin respuestas válidas
    sin_respuestas = (agrupado["dane_total_valido"] == 0).sum()
    stats["combinaciones_sin_respuestas_validas"] = int(sin_respuestas)

    # Filtrar solo combinaciones con respuestas válidas
    agrupado = agrupado[agrupado["dane_total_valido"] > 0].copy()

    # Calcular porcentaje
    agrupado["dane_pct_sin_asistencia"] = (
        agrupado["dane_sin_asistencia"] / agrupado["dane_total_valido"] * 100
    )

    # Renombrar columnas
    agrupado = agrupado.rename(columns={
        "CODMUNRE": "cod_municipio",
        "CAU_HOMOL": "cod_grupo_diagnostico",
    })

    stats["combinaciones_con_objetivo"] = len(agrupado)
    stats["municipios_distintos"] = int(agrupado["cod_municipio"].nunique())
    stats["grupos_distintos"] = int(agrupado["cod_grupo_diagnostico"].nunique())

    return agrupado, stats


# ==========================================
# PROCESAMIENTO RIPS
# ==========================================

def validar_y_deduplicar_rips(df_rips):
    """
    Valida la estructura y elimina duplicados exactos del DataFrame RIPS.

    Returns:
        Tupla (df_limpio, stats).
    """
    stats = {
        "registros_originales": len(df_rips),
        "duplicados_exactos": 0,
    }

    duplicados = int(df_rips.duplicated().sum())
    stats["duplicados_exactos"] = duplicados

    df_limpio = df_rips.drop_duplicates().reset_index(drop=True)
    stats["registros_despues_deduplicacion"] = len(df_limpio)

    return df_limpio, stats


def extraer_codigo_municipio(municipio):
    """
    Extrae el código DIVIPOLA de 5 dígitos de una cadena como
    "20001 - VALLEDUPAR" o "11001".

    Returns:
        Código municipal como string de 5 dígitos o None.
    """
    if not municipio or not isinstance(municipio, str):
        return None

    mun = municipio.strip()
    if not mun:
        return None

    # Formato "CODIGO - NOMBRE"
    if " - " in mun:
        codigo = mun.split(" - ", 1)[0].strip()
    else:
        codigo = mun.strip()

    # Validar que sea numérico
    codigo = codigo.replace(" ", "")
    if not codigo.isdigit():
        return None

    # Asegurar 5 dígitos
    if len(codigo) == 5:
        return codigo
    elif len(codigo) < 5:
        return codigo.zfill(5)
    else:
        return codigo[:5]


def clasificar_tipo_atencion(tipo):
    """
    Clasifica un valor de TipoAtención en una categoría.

    Returns:
        Categoría ("consultas", "procedimientos", "urgencias",
        "hospitalizaciones") o None si no se puede clasificar.
    """
    if not tipo or not isinstance(tipo, str):
        return None

    tipo_limpio = tipo.strip().upper()
    if not tipo_limpio:
        return None

    return TIPO_ATENCION_MAP.get(tipo_limpio)


def procesar_rips(df_rips):
    """
    Procesa el DataFrame RIPS: valida, homologa diagnósticos, clasifica
    atenciones y agrega por municipio-grupo diagnóstico.

    Valida NumeroAtenciones, código municipal, formato de diagnóstico CIE-10.
    Los registros C50 se conservan como categoría auxiliar y no se integran.

    Returns:
        DataFrame con columnas de agregación RIPS y un diccionario con stats.
    """
    stats = {
        "diagnosticos_distintos": 0,
        "diagnosticos_homologados": 0,
        "diagnosticos_sin_correspondencia": 0,
        "registros_sin_correspondencia": 0,
        "cobertura_homologacion": 0.0,
        "cobertura_homologacion_ponderada": 0.0,
        "tipos_atencion_no_clasificados": 0,
        "tipos_atencion_desconocidos": [],
        "registros_excluidos": 0,
        "registros_unicos_excluidos": 0,
        "excluidos_numero_atenciones_negativo": 0,
        "excluidos_numero_atenciones_no_numerico": 0,
        "excluidos_codigo_municipio_invalido": 0,
        "excluidos_diagnostico_invalido": 0,
        "atenciones_excluidas_negativas": 0,
        "registros_c50": 0,
        "atenciones_c50": 0,
        "diagnosticos_c50_distintos": 0,
    }

    df_trabajo = df_rips.copy()
    indices_excluidos = set()

    # Extraer código municipal
    df_trabajo["cod_municipio"] = df_trabajo["Municipio"].apply(
        extraer_codigo_municipio
    )
    sin_municipio = df_trabajo["cod_municipio"].isna()
    stats["excluidos_codigo_municipio_invalido"] = int(sin_municipio.sum())
    indices_excluidos.update(df_trabajo[sin_municipio].index)

    # Extraer código CIE-10 y validar formato
    df_trabajo["codigo_cie10"] = df_trabajo["Diagnostico"].apply(
        extraer_codigo_cie10
    )
    # Un diagnóstico CIE-10 válido debe tener al menos una letra y un dígito
    def _es_cie10_valido(codigo):
        if not codigo or not isinstance(codigo, str):
            return False
        codigo = codigo.strip()
        if not codigo:
            return False
        # Debe empezar con letra
        if not codigo[0].isalpha():
            return False
        # Debe tener al menos un dígito
        if not any(c.isdigit() for c in codigo):
            return False
        return True

    diagnostico_invalido = ~df_trabajo["codigo_cie10"].apply(_es_cie10_valido)
    stats["excluidos_diagnostico_invalido"] = int(diagnostico_invalido.sum())
    indices_excluidos.update(df_trabajo[diagnostico_invalido].index)

    # Convertir NumeroAtenciones a numérico
    df_trabajo["NumeroAtenciones_raw"] = pd.to_numeric(
        df_trabajo["NumeroAtenciones"], errors="coerce"
    )
    # No numéricos
    no_numerico = df_trabajo["NumeroAtenciones_raw"].isna()
    stats["excluidos_numero_atenciones_no_numerico"] = int(no_numerico.sum())
    indices_excluidos.update(df_trabajo[no_numerico].index)

    # Negativos
    negativo = df_trabajo["NumeroAtenciones_raw"] < 0
    stats["excluidos_numero_atenciones_negativo"] = int(negativo.sum())
    stats["atenciones_excluidas_negativas"] = int(
        abs(df_trabajo.loc[negativo, "NumeroAtenciones_raw"].sum())
    )
    indices_excluidos.update(df_trabajo[negativo].index)

    stats["registros_unicos_excluidos"] = len(indices_excluidos)
    stats["registros_excluidos"] = len(indices_excluidos)

    # Filtrar registros excluidos
    if indices_excluidos:
        df_trabajo = df_trabajo.drop(indices_excluidos).reset_index(drop=True)

    # Homologar diagnósticos
    df_trabajo["cod_grupo_diagnostico"] = df_trabajo["Diagnostico"].apply(
        homologar_diagnostico
    )

    # Estadísticas de homologación (solo registros no excluidos)
    codigos_cie10 = df_trabajo["codigo_cie10"].dropna().unique()
    stats["diagnosticos_distintos"] = len(
        [c for c in codigos_cie10 if c]
    )

    homologados = set()
    sin_correspondencia = set()
    c50_codigos = set()

    for codigo in codigos_cie10:
        if not codigo:
            continue
        grupo = homologar_diagnostico(codigo)
        if es_categoria_c50(grupo):
            c50_codigos.add(codigo)
        elif grupo is not None:
            homologados.add(codigo)
        else:
            sin_correspondencia.add(codigo)

    stats["diagnosticos_homologados"] = len(homologados)
    stats["diagnosticos_sin_correspondencia"] = len(sin_correspondencia)
    stats["diagnosticos_c50_distintos"] = len(c50_codigos)

    if stats["diagnosticos_distintos"] > 0:
        stats["cobertura_homologacion"] = round(
            len(homologados) / stats["diagnosticos_distintos"] * 100, 2
        )

    # C50: registros y atenciones (antes de sin_correspondencia para evitar
    # advertencias de pandas al mezclar booleanos y strings)
    # Usar c50_mask como boolean Series explícitamente para evitar que
    # .sum() devuelva un string vacío en DataFrames vacíos con dtype=str
    c50_mask = df_trabajo["cod_grupo_diagnostico"].apply(es_categoria_c50)
    stats["registros_c50"] = int(c50_mask.astype(bool).sum())
    if stats["registros_c50"] > 0:
        stats["atenciones_c50"] = int(
            df_trabajo.loc[c50_mask, "NumeroAtenciones_raw"].sum()
        )

    # Registros sin correspondencia (incluye C50)
    sin_corr_mask = (
        df_trabajo["cod_grupo_diagnostico"].isna()
        | c50_mask.astype(bool)
    )
    stats["registros_sin_correspondencia"] = int(sin_corr_mask.sum())

    # Clasificar tipo de atención
    df_trabajo["categoria_atencion"] = df_trabajo["TipoAtencion"].apply(
        clasificar_tipo_atencion
    )

    # Tipos no clasificados
    no_clasificados = df_trabajo["categoria_atencion"].isna()
    stats["tipos_atencion_no_clasificados"] = int(no_clasificados.sum())
    stats["tipos_atencion_desconocidos"] = sorted(
        df_trabajo.loc[no_clasificados, "TipoAtencion"].unique().tolist()
    )

    # NumeroAtenciones limpio (0 para nulos, ya filtrados)
    df_trabajo["NumeroAtenciones"] = df_trabajo["NumeroAtenciones_raw"].fillna(0)

    # Filtrar: solo registros con grupo diagnóstico oficial (no C50, no None)
    # Usar .astype(bool) para evitar advertencias de pandas con dtype=str
    is_c50 = df_trabajo["cod_grupo_diagnostico"].apply(es_categoria_c50)
    df_valido = df_trabajo[
        df_trabajo["cod_grupo_diagnostico"].notna()
        & ~is_c50.astype(bool)
    ].copy()

    # Cobertura ponderada por atenciones
    total_atenciones_validas = df_trabajo["NumeroAtenciones"].sum()
    atenciones_homologadas = df_valido["NumeroAtenciones"].sum()
    if total_atenciones_validas > 0:
        stats["cobertura_homologacion_ponderada"] = round(
            atenciones_homologadas / total_atenciones_validas * 100, 2
        )

    # Agrupar por municipio y grupo diagnóstico
    agrupado = df_valido.groupby(
        ["cod_municipio", "cod_grupo_diagnostico"]
    ).agg(
        rips_total_atenciones=("NumeroAtenciones", "sum"),
    ).reset_index()

    # Calcular por categoría de atención
    for categoria in ["consultas", "procedimientos", "urgencias", "hospitalizaciones"]:
        mask = df_valido["categoria_atencion"] == categoria
        cat_agg = (
            df_valido[mask]
            .groupby(["cod_municipio", "cod_grupo_diagnostico"])
            .agg(**{f"rips_{categoria}": ("NumeroAtenciones", "sum")})
            .reset_index()
        )
        agrupado = agrupado.merge(
            cat_agg, on=["cod_municipio", "cod_grupo_diagnostico"], how="left"
        )
        agrupado[f"rips_{categoria}"] = agrupado[f"rips_{categoria}"].fillna(0)

    # Calcular porcentajes
    for categoria in ["consultas", "procedimientos", "urgencias", "hospitalizaciones"]:
        agrupado[f"rips_pct_{categoria}"] = np.where(
            agrupado["rips_total_atenciones"] > 0,
            agrupado[f"rips_{categoria}"] / agrupado["rips_total_atenciones"] * 100,
            0,
        )

    # Convertir a int los conteos
    for col in [
        "rips_total_atenciones",
        "rips_consultas",
        "rips_procedimientos",
        "rips_urgencias",
        "rips_hospitalizaciones",
    ]:
        agrupado[col] = agrupado[col].astype(int)

    stats["combinaciones_rips"] = len(agrupado)

    return agrupado, stats


# ==========================================
# INTEGRACIÓN
# ==========================================

def integrar_dane_rips(df_dane, df_rips):
    """
    Integra los DataFrames procesados de DANE y RIPS.

    DANE es la fuente de referencia. Las combinaciones sin registros
    RIPS se conservan con ceros.

    Returns:
        DataFrame integrado y estadísticas.
    """
    stats = {
        "combinaciones_sin_rips": 0,
    }

    # Merge con DANE como referencia (left join)
    integrado = df_dane.merge(
        df_rips,
        on=["cod_municipio", "cod_grupo_diagnostico"],
        how="left",
    )

    # Rellenar ceros donde no hay registros RIPS
    columnas_rips = [
        "rips_total_atenciones",
        "rips_consultas",
        "rips_procedimientos",
        "rips_urgencias",
        "rips_hospitalizaciones",
        "rips_pct_consultas",
        "rips_pct_procedimientos",
        "rips_pct_urgencias",
        "rips_pct_hospitalizaciones",
    ]

    sin_rips_mask = df_dane.merge(
        df_rips,
        on=["cod_municipio", "cod_grupo_diagnostico"],
        how="left",
    )["rips_total_atenciones"].isna()
    stats["combinaciones_sin_rips"] = int(sin_rips_mask.sum())

    for col in columnas_rips:
        if col in integrado.columns:
            integrado[col] = integrado[col].fillna(0)

    # Seleccionar columnas finales
    columnas_finales = [
        "cod_municipio",
        "cod_grupo_diagnostico",
        "rips_total_atenciones",
        "rips_consultas",
        "rips_procedimientos",
        "rips_urgencias",
        "rips_hospitalizaciones",
        "rips_pct_consultas",
        "rips_pct_procedimientos",
        "rips_pct_urgencias",
        "rips_pct_hospitalizaciones",
        "dane_pct_sin_asistencia",
    ]

    # Asegurar que todas existan
    for col in columnas_finales:
        if col not in integrado.columns:
            integrado[col] = 0

    integrado = integrado[columnas_finales]

    # Redondear porcentajes
    for col in [
        "rips_pct_consultas",
        "rips_pct_procedimientos",
        "rips_pct_urgencias",
        "rips_pct_hospitalizaciones",
        "dane_pct_sin_asistencia",
    ]:
        integrado[col] = integrado[col].round(2)

    return integrado, stats


# ==========================================
# VALIDACIÓN DEL DATASET
# ==========================================

def validar_dataset(df):
    """
    Valida el dataset final antes de exportar.

    Returns:
        Lista de errores encontrados.
    """
    errores = []

    # Combinaciones duplicadas
    duplicados = df.duplicated(
        subset=["cod_municipio", "cod_grupo_diagnostico"]
    ).sum()
    if duplicados > 0:
        errores.append(
            f"Se encontraron {duplicados} combinaciones duplicadas "
            "de municipio y grupo diagnóstico."
        )

    # Códigos municipales consistentes
    codigos = df["cod_municipio"].astype(str)
    if (codigos.str.len() != 5).any():
        errores.append(
            "Algunos códigos municipales no tienen 5 dígitos."
        )

    # Conteos no negativos
    for col in [
        "rips_total_atenciones",
        "rips_consultas",
        "rips_procedimientos",
        "rips_urgencias",
        "rips_hospitalizaciones",
    ]:
        if (df[col] < 0).any():
            errores.append(f"Valores negativos en {col}.")

    # Porcentajes entre 0 y 100
    for col in [
        "rips_pct_consultas",
        "rips_pct_procedimientos",
        "rips_pct_urgencias",
        "rips_pct_hospitalizaciones",
        "dane_pct_sin_asistencia",
    ]:
        if (df[col] < 0).any() or (df[col] > 100).any():
            errores.append(
                f"Porcentajes fuera de rango [0, 100] en {col}."
            )

    # Valores infinitos o NaN
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            if pd.isna(df[col]).any() or np.isinf(df[col]).any():
                errores.append(f"Valores infinitos o NaN en {col}.")
        else:
            if df[col].isna().any():
                errores.append(f"Valores NaN en {col}.")

    # Variable objetivo definida
    if df["dane_pct_sin_asistencia"].isna().any():
        errores.append(
            "Existen observaciones con variable objetivo no definida."
        )

    return errores


# ==========================================
# ESCRITURA ATÓMICA
# ==========================================

def guardar_dataset_atomico(df, ruta_final):
    """
    Guarda el DataFrame CSV de forma atómica.
    Escribe primero en un archivo temporal y luego lo renombra.
    """
    ruta_final = Path(ruta_final)
    ruta_final.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        suffix=".csv",
        dir=str(ruta_final.parent),
        prefix=".tmp_",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            df.to_csv(f, index=False, encoding="utf-8")
        Path(temp_path).replace(ruta_final)
    except Exception:
        try:
            Path(temp_path).unlink(missing_ok=True)
        except OSError:
            pass
        raise


def guardar_json_atomico(ruta_final, datos):
    """Guarda un diccionario JSON de forma atómica."""
    ruta_final = Path(ruta_final)
    ruta_final.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        suffix=".json",
        dir=str(ruta_final.parent),
        prefix=".tmp_",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=4)
        Path(temp_path).replace(ruta_final)
    except Exception:
        try:
            Path(temp_path).unlink(missing_ok=True)
        except OSError:
            pass
        raise


# ==========================================
# VERIFICACIÓN DE VIGENCIA
# ==========================================

def verificar_vigencia_procesamiento():
    """
    Verifica si el dataset procesado está vigente respecto a los archivos RAW.

    Returns:
        Diccionario con el estado de vigencia.
    """
    metadata_path = REPORTS_DIR / METADATA_FILE

    if not metadata_path.exists():
        return {
            "disponible": False,
            "vigente": False,
            "mensaje": "No existe un dataset procesado.",
        }

    try:
        with metadata_path.open("r", encoding="utf-8") as f:
            metadata = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {
            "disponible": True,
            "vigente": False,
            "mensaje": "Metadatos corruptos.",
        }

    vigente = True
    mensajes = []

    # Verificar DANE
    archivo_dane = encontrar_archivo_raw(DANE_RAW_PATTERN)
    if archivo_dane:
        hash_actual = obtener_archivo_hash(archivo_dane)
        hash_guardado = metadata.get("hash_dane")
        if hash_actual != hash_guardado:
            vigente = False
            mensajes.append("El archivo RAW de DANE ha cambiado.")
    else:
        mensajes.append("No se encontró el archivo RAW de DANE.")

    # Verificar RIPS
    archivo_rips = encontrar_archivo_raw(RIPS_RAW_PATTERN)
    if archivo_rips:
        hash_actual = obtener_archivo_hash(archivo_rips)
        hash_guardado = metadata.get("hash_rips")
        if hash_actual != hash_guardado:
            vigente = False
            mensajes.append("El archivo RAW de RIPS ha cambiado.")
    else:
        mensajes.append("No se encontró el archivo RAW de RIPS.")

    return {
        "disponible": True,
        "vigente": vigente,
        "generado_en": metadata.get("generado_en"),
        "anio": metadata.get("anio"),
        "mensaje": "; ".join(mensajes) if mensajes else "El dataset está vigente.",
    }


# ==========================================
# FUNCIÓN PRINCIPAL DE PROCESAMIENTO
# ==========================================

def _es_proceso_activo(pid):
    """
    Verifica si un proceso con el PID dado está activo.

    Args:
        pid: Identificador del proceso a verificar.

    Returns:
        True si el proceso está activo, False en caso contrario.
    """
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # PermissionError significa que el proceso existe pero no
        # tenemos permiso para enviarle señales. En Linux, un proceso
        # del sistema (PID 1) produce esto, pero un PID de usuario
        # sin permisos también. Asumir activo para ser conservadores.
        return True
    except OSError:
        return False


def _adquirir_bloqueo():
    """
    Adquiere el bloqueo de procesamiento de forma atómica.

    Usa un archivo de lock con O_CREAT | O_EXCL para proteger contra
    ejecuciones concurrentes entre procesos. El threading.Lock protege
    dentro del mismo proceso.

    Maneja archivos de bloqueo corruptos o vacíos: si el archivo existe
    pero no contiene un PID válido, se verifica si hay un proceso activo
    que podría haberlo creado. Si no hay proceso activo, se trata como
    un bloqueo abandonado y se recupera.

    Returns:
        fd del archivo de lock o None si ya existe un bloqueo activo.
    """
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = PROCESSED_DIR / LOCK_FILE

    try:
        # Crear archivo de lock de forma atómica
        fd = os.open(
            str(lock_path),
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        )
        # Escribir PID para diagnóstico de bloqueos abandonados
        os.write(fd, str(os.getpid()).encode("utf-8"))
        return fd
    except FileExistsError:
        # El archivo de lock ya existe. Leer el PID almacenado.
        pid_str = ""
        try:
            with lock_path.open("r", encoding="utf-8") as f:
                pid_str = f.read().strip()
        except (OSError, UnicodeDecodeError):
            # No se puede leer el archivo (corrupto, binario, etc.)
            # Tratar como bloqueo abandonado: intentar eliminar y reintentar
            try:
                lock_path.unlink()
            except OSError:
                return None
            try:
                fd = os.open(
                    str(lock_path),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
                os.write(fd, str(os.getpid()).encode("utf-8"))
                return fd
            except FileExistsError:
                # Otro proceso creó el lock entre unlink y open
                return None

        # Caso: archivo vacío o con contenido no numérico
        if not pid_str:
            # Archivo vacío: podría estar siendo escrito por un proceso
            # activo o ser un bloqueo abandonado. Verificar si existe
            # algún proceso que tenga el archivo abierto no es trivial
            # sin dependencias. Ser conservadores: tratar como abandonado
            # y reintentar la creación atómica.
            try:
                lock_path.unlink()
            except OSError:
                return None
            try:
                fd = os.open(
                    str(lock_path),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
                os.write(fd, str(os.getpid()).encode("utf-8"))
                return fd
            except FileExistsError:
                # Otro proceso creó el lock entre unlink y open
                return None

        # Caso: archivo con PID numérico
        try:
            old_pid = int(pid_str)
        except ValueError:
            # Contenido no numérico: bloqueo corrupto, tratar como abandonado
            try:
                lock_path.unlink()
            except OSError:
                return None
            try:
                fd = os.open(
                    str(lock_path),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
                os.write(fd, str(os.getpid()).encode("utf-8"))
                return fd
            except FileExistsError:
                return None

        # Verificar si el proceso con ese PID aún existe
        if _es_proceso_activo(old_pid):
            # El proceso existe, bloqueo activo
            return None

        # El proceso ya no existe, bloqueo abandonado
        try:
            lock_path.unlink()
        except OSError:
            return None
        # Reintentar crear el lock
        try:
            fd = os.open(
                str(lock_path),
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
            os.write(fd, str(os.getpid()).encode("utf-8"))
            return fd
        except FileExistsError:
            # Otro proceso creó el lock entre unlink y open
            return None


def _liberar_bloqueo(fd):
    """Libera el bloqueo de procesamiento."""
    if fd is not None:
        try:
            os.close(fd)
        except OSError:
            pass
        lock_path = PROCESSED_DIR / LOCK_FILE
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def ejecutar_procesamiento():
    """
    Ejecuta el flujo completo de procesamiento DANE + RIPS.

    Solo una ejecución puede estar activa a la vez. Las solicitudes
    concurrentes se rechazan.

    Returns:
        Diccionario con resultados, estadísticas y posibles errores.
    """
    # Bloqueo de thread (mismo proceso)
    if not _processing_lock.acquire(blocking=False):
        return {
            "estado": "error",
            "errores": [
                "Ya hay una ejecución de procesamiento activa. "
                "Intente más tarde."
            ],
            "advertencias": [],
            "estadisticas": {},
        }

    # Bloqueo entre procesos (archivo de lock)
    lock_fd = _adquirir_bloqueo()
    if lock_fd is None:
        _processing_lock.release()
        return {
            "estado": "error",
            "errores": [
                "Ya hay una ejecución de procesamiento activa en otro proceso. "
                "Intente más tarde."
            ],
            "advertencias": [],
            "estadisticas": {},
        }

    try:
        return _ejecutar_procesamiento_interno()
    finally:
        _liberar_bloqueo(lock_fd)
        _processing_lock.release()


def _ejecutar_procesamiento_interno():
    """Lógica interna del procesamiento (sin bloqueo)."""
    resultado = {
        "estado": "en_proceso",
        "errores": [],
        "advertencias": [],
        "estadisticas": {},
    }

    ahora = datetime.now(timezone.utc).isoformat()

    # 1. Buscar archivos RAW
    archivo_dane = encontrar_archivo_raw(DANE_RAW_PATTERN)
    archivo_rips = encontrar_archivo_raw(RIPS_RAW_PATTERN)

    if archivo_dane is None:
        resultado["estado"] = "error"
        resultado["errores"].append(
            "No se encontró el archivo RAW de DANE en data/raw/."
        )
        return resultado

    if archivo_rips is None:
        resultado["estado"] = "error"
        resultado["errores"].append(
            "No se encontró el archivo RAW de RIPS en data/raw/."
        )
        return resultado

    # 2. Leer archivos
    try:
        df_dane = leer_csv_raw(archivo_dane)
    except Exception as error:
        resultado["estado"] = "error"
        resultado["errores"].append(f"Error al leer DANE: {error}")
        return resultado

    try:
        df_rips = leer_csv_raw(archivo_rips)
    except Exception as error:
        resultado["estado"] = "error"
        resultado["errores"].append(f"Error al leer RIPS: {error}")
        return resultado

    resultado["estadisticas"]["archivo_dane"] = archivo_dane.name
    resultado["estadisticas"]["archivo_rips"] = archivo_rips.name

    # 3. Detectar y validar años
    anio_dane, errores_anio_dane = detectar_anio(
        df_dane, "ANO", "DANE"
    )
    anio_rips, errores_anio_rips = detectar_anio(
        df_rips, "Año", "RIPS"
    )

    resultado["estadisticas"]["registros_originales_dane"] = len(df_dane)
    resultado["estadisticas"]["registros_originales_rips"] = len(df_rips)

    anio, errores_anios = validar_anios_coincidentes(
        anio_dane, errores_anio_dane, anio_rips, errores_anio_rips
    )

    if errores_anios:
        resultado["errores"].extend(errores_anios)

    if anio is None:
        resultado["estado"] = "error"
        return resultado

    resultado["estadisticas"]["anio"] = anio

    # 4. Validar y deduplicar RIPS
    df_rips_limpio, stats_dedup = validar_y_deduplicar_rips(df_rips)
    resultado["estadisticas"]["duplicados_rips"] = stats_dedup["duplicados_exactos"]

    # 5. Procesar DANE
    try:
        df_dane_proc, stats_dane = procesar_dane(df_dane)
    except Exception as error:
        resultado["estado"] = "error"
        resultado["errores"].append(f"Error al procesar DANE: {error}")
        return resultado

    resultado["estadisticas"]["dane"] = stats_dane

    # 6. Procesar RIPS
    try:
        df_rips_proc, stats_rips = procesar_rips(df_rips_limpio)
    except Exception as error:
        resultado["estado"] = "error"
        resultado["errores"].append(f"Error al procesar RIPS: {error}")
        return resultado

    resultado["estadisticas"]["rips"] = stats_rips

    # 7. Integrar
    try:
        df_integrado, stats_integracion = integrar_dane_rips(
            df_dane_proc, df_rips_proc
        )
    except Exception as error:
        resultado["estado"] = "error"
        resultado["errores"].append(f"Error al integrar: {error}")
        return resultado

    resultado["estadisticas"]["integracion"] = stats_integracion

    # 8. Validar dataset
    errores_validacion = validar_dataset(df_integrado)
    if errores_validacion:
        resultado["errores"].extend(errores_validacion)
        resultado["estado"] = "error"
        return resultado

    # 9. Guardar dataset
    ruta_dataset = PROCESSED_DIR / DATASET_FILE
    try:
        guardar_dataset_atomico(df_integrado, ruta_dataset)
    except Exception as error:
        resultado["estado"] = "error"
        resultado["errores"].append(f"Error al guardar dataset: {error}")
        return resultado

    # 10. Guardar metadatos
    metadata = {
        "generado_en": ahora,
        "anio": anio,
        "archivo_dane": archivo_dane.name,
        "archivo_rips": archivo_rips.name,
        "hash_dane": obtener_archivo_hash(archivo_dane),
        "hash_rips": obtener_archivo_hash(archivo_rips),
        "observaciones": len(df_integrado),
    }

    try:
        guardar_json_atomico(REPORTS_DIR / METADATA_FILE, metadata)
    except Exception as error:
        resultado["advertencias"].append(
            f"No se pudieron guardar los metadatos: {error}"
        )

    # 11. Guardar reporte
    reporte = {
        "generado_en": ahora,
        "anio": anio,
        "registros_originales_dane": len(df_dane),
        "registros_originales_rips": len(df_rips),
        "duplicados_rips_eliminados": stats_dedup["duplicados_exactos"],
        "registros_rips_procesados": stats_dedup["registros_despues_deduplicacion"],
        # DANE
        "dane_registros_excluidos": stats_dane["registros_unicos_excluidos"],
        "dane_excluidos_cod_municipio_invalido": stats_dane["excluidos_cod_municipio_invalido"],
        "dane_excluidos_cau_homol_invalido": stats_dane["excluidos_cau_homol_invalido"],
        "dane_excluidos_cau_homol_nulo": stats_dane["excluidos_cau_homol_nulo"],
        "dane_excluidos_asis_med_invalido": stats_dane["excluidos_asis_med_invalido"],
        "dane_asis_med_nulo": stats_dane["asis_med_nulo"],
        # RIPS
        "rips_registros_excluidos": stats_rips["registros_unicos_excluidos"],
        "rips_excluidos_numero_atenciones_negativo": stats_rips["excluidos_numero_atenciones_negativo"],
        "rips_excluidos_numero_atenciones_no_numerico": stats_rips["excluidos_numero_atenciones_no_numerico"],
        "rips_excluidos_codigo_municipio_invalido": stats_rips["excluidos_codigo_municipio_invalido"],
        "rips_excluidos_diagnostico_invalido": stats_rips["excluidos_diagnostico_invalido"],
        "rips_atenciones_excluidas_negativas": stats_rips["atenciones_excluidas_negativas"],
        # Homologación
        "diagnosticos_cie10_distintos": stats_rips["diagnosticos_distintos"],
        "diagnosticos_homologados": stats_rips["diagnosticos_homologados"],
        "diagnosticos_sin_correspondencia": stats_rips["diagnosticos_sin_correspondencia"],
        "cobertura_homologacion_pct": stats_rips["cobertura_homologacion"],
        "cobertura_homologacion_ponderada_pct": stats_rips["cobertura_homologacion_ponderada"],
        "registros_rips_sin_correspondencia": stats_rips["registros_sin_correspondencia"],
        # C50
        "registros_c50": stats_rips["registros_c50"],
        "atenciones_c50": stats_rips["atenciones_c50"],
        "diagnosticos_c50_distintos": stats_rips["diagnosticos_c50_distintos"],
        # Integración
        "municipios_distintos": stats_dane["municipios_distintos"],
        "grupos_diagnosticos_distintos": stats_dane["grupos_distintos"],
        "combinaciones_municipio_grupo": len(df_integrado),
        "combinaciones_sin_registros_rips": stats_integracion["combinaciones_sin_rips"],
        "observaciones_excluidas_sin_respuestas_validas": stats_dane["combinaciones_sin_respuestas_validas"],
        "tipos_atencion_no_clasificados": stats_rips["tipos_atencion_no_clasificados"],
        "tipos_atencion_desconocidos": stats_rips["tipos_atencion_desconocidos"],
        "observaciones_finales": len(df_integrado),
        "valores_faltantes": int(df_integrado.isna().sum().sum()),
        # Limitaciones conocidas
        "limitaciones_homologacion": [
            "U07 (COVID-19): Se asigna al grupo 010 siguiendo la práctica del "
            "DANE. El Boletín Técnico EEVV confirma U07 en el grupo 109 de la "
            "Lista 6/67 OPS, pero no existe un documento oficial que mapee "
            "explícitamente al grupo 010 de la Lista Colombia 105. Esta regla "
            "complementaria está pendiente de verificación documental."
        ],
    }

    try:
        guardar_json_atomico(REPORTS_DIR / REPORT_FILE, reporte)
    except Exception as error:
        resultado["advertencias"].append(
            f"No se pudo guardar el reporte: {error}"
        )

    resultado["estado"] = "exitoso"
    resultado["estadisticas"]["observaciones_finales"] = len(df_integrado)
    resultado["estadisticas"]["ruta_dataset"] = str(ruta_dataset)

    return resultado
