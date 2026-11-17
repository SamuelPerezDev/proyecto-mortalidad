
"""
Procesamiento, homologación e integración de datos DANE y RIPS.

Este módulo construye el dataset de entrenamiento a partir de los archivos
RAW originales.

Flujo:
    1. Detectar y validar el año de ambas fuentes.
    2. Procesar DANE: calcular la variable objetivo por municipio-grupo.
    3. Procesar RIPS: homologar diagnósticos, clasificar atenciones, agregar.
    4. Integrar ambas fuentes por municipio-grupo diagnóstico.
    5. Validar y exportar el dataset final.
"""

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

_processing_lock = threading.Lock()

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

    Conserva los valores nulos.
    Los años no nulos deben ser válidos.

    Returns:
        Tupla (anio, errores).
    """
    errores = []

    if columna not in df.columns:
        errores.append(
            f"La columna '{columna}' no existe en {fuente}."
        )
        return None, errores

    serie = df[columna]

    nulos_count = int(serie.isna().sum())

    if nulos_count > 0:
        pass

    serie_str = serie.fillna("").astype(str).str.strip()

    vacios = (
        (serie_str == "") | (serie_str == "nan")
    ).sum() - nulos_count

    if vacios > 0:
        pass

    valores = serie_str[
        serie_str.ne("") & (serie_str != "nan")
    ].unique()

    anos_validos = []
    anos_invalidos = set()

    for v in valores:
        try:
            anio_float = float(v)

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
            f"{fuente}: Valores inválidos en "
            f"'{columna}': {sorted(anos_invalidos)}."
        )

        if not anos_validos:
            return None, errores

    anos_unicos = sorted(set(anos_validos))

    if len(anos_unicos) == 0:
        errores.append(
            f"{fuente}: No se encontró ningún año "
            f"válido en '{columna}'."
        )
        return None, errores

    if len(anos_unicos) > 1:
        errores.append(
            f"{fuente}: Se detectaron múltiples años: "
            f"{anos_unicos}. El procesamiento solo "
            "admite un único año por ejecución."
        )
        return None, errores

    if anos_invalidos:
        return None, errores

    return anos_unicos[0], errores


def validar_anios_coincidentes(
    anio_dane,
    errores_dane,
    anio_rips,
    errores_rips
):
    """
    Verifica que ambas fuentes correspondan al mismo año.
    """
    errores = errores_dane + errores_rips

    if anio_dane is None or anio_rips is None:
        return None, errores

    if anio_dane != anio_rips:
        errores.append(
            f"Los años no coinciden: "
            f"DANE={anio_dane}, RIPS={anio_rips}. "
            "Ambas fuentes deben corresponder al mismo año."
        )
        return None, errores

    return anio_dane, errores


# ==========================================
# PROCESAMIENTO DANE
# ==========================================

def procesar_dane(df_dane):
    """
    Agrupa DANE sin eliminar filas por valores nulos.

    Solo excluye códigos no nulos inválidos.

    Si un grupo no tiene respuestas válidas,
    su porcentaje queda nulo.
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

    for col in ("CODPTORE", "CODMUNRE", "CAU_HOMOL", "ASIS_MED"):
        if col not in df_trabajo.columns:
            raise ValueError(
                f"DANE: falta la columna {col}"
            )

        df_trabajo[col] = (
            df_trabajo[col]
            .astype("string")
            .str.strip()
            .replace("", pd.NA)
        )

    departamento = df_trabajo["CODPTORE"]
    municipio = df_trabajo["CODMUNRE"]

    departamento_valido = departamento.str.fullmatch(
        r"[0-9]{2}"
    ).fillna(False)

    municipio_valido = municipio.str.fullmatch(
    r"[0-9]{3}"
    ).fillna(False)

    invalido_municipio = (
    (departamento.notna() & ~departamento_valido)
    | (municipio.notna() & ~municipio_valido)
    )

    df_trabajo["CODMUNRE"] = (
    departamento + municipio
    ).where(
    departamento_valido & municipio_valido,
    pd.NA
    )

    codigos_validos = set(
        todos_los_codigos_cau_homol()
    )

    grupo = df_trabajo["CAU_HOMOL"]

    invalido_grupo = (
        grupo.notna()
        & ~grupo.isin(codigos_validos)
    )

    asis = df_trabajo["ASIS_MED"]

    invalido_asis = (
        asis.notna()
        & ~asis.isin({"1", "2", "3", "9"})
    )

    stats["excluidos_cod_municipio_invalido"] = int(
        invalido_municipio.sum()
    )

    stats["excluidos_cau_homol_invalido"] = int(
        invalido_grupo.sum()
    )

    stats["excluidos_cau_homol_nulo"] = 0

    stats["excluidos_asis_med_invalido"] = int(
        invalido_asis.sum()
    )

    stats["asis_med_nulo"] = int(
        asis.isna().sum()
    )

    invalidos = (
        invalido_municipio
        | invalido_grupo
        | invalido_asis
    )

    stats["registros_excluidos"] = int(
        invalidos.sum()
    )

    stats["registros_unicos_excluidos"] = int(
        invalidos.sum()
    )

    df_trabajo = df_trabajo.loc[
        ~invalidos
    ].copy()

    df_trabajo["es_sin_asistencia"] = (
        df_trabajo["ASIS_MED"]
        .eq("2")
        .fillna(False)
        .astype(int)
    )

    df_trabajo["es_respuesta_valida"] = (
        df_trabajo["ASIS_MED"]
        .isin(["1", "2"])
        .astype(int)
    )

    agrupado = df_trabajo.groupby(
        ["CODMUNRE", "CAU_HOMOL"],
        dropna=False
    ).agg(
        dane_sin_asistencia=(
            "es_sin_asistencia",
            "sum"
        ),
        dane_total_valido=(
            "es_respuesta_valida",
            "sum"
        ),
    ).reset_index()

    sin_respuestas = (
        agrupado["dane_total_valido"].eq(0)
    )

    stats["combinaciones_sin_respuestas_validas"] = int(
        sin_respuestas.sum()
    )

    agrupado["dane_pct_sin_asistencia"] = (
        agrupado["dane_sin_asistencia"]
        .div(
            agrupado["dane_total_valido"]
            .replace(0, np.nan)
        ) * 100
    )

    agrupado = agrupado.rename(
        columns={
            "CODMUNRE": "cod_municipio",
            "CAU_HOMOL": "cod_grupo_diagnostico",
        }
    )

    stats["combinaciones_con_objetivo"] = int(
        agrupado[
            "dane_pct_sin_asistencia"
        ].notna().sum()
    )

    stats["municipios_distintos"] = int(
        agrupado["cod_municipio"].nunique()
    )

    stats["grupos_distintos"] = int(
        agrupado["cod_grupo_diagnostico"].nunique()
    )

    return agrupado, stats


# ==========================================
# PROCESAMIENTO RIPS
# ==========================================

def validar_y_deduplicar_rips(df_rips):
    """
    Valida la estructura y reporta duplicados exactos.

    Los duplicados se conservan en esta versión.
    """
    stats = {
        "registros_originales": len(df_rips),
        "duplicados_exactos": 0,
    }

    duplicados = int(
        df_rips.duplicated().sum()
    )

    stats["duplicados_exactos"] = duplicados

    df_limpio = df_rips.copy()

    stats["registros_despues_deduplicacion"] = len(
        df_limpio
    )

    return df_limpio, stats

def extraer_codigo_municipio(municipio):
    """
    Extrae el código DIVIPOLA de una cadena como
    '20001 - VALLEDUPAR' o '11001'.
    """
    if not municipio or not isinstance(municipio, str):
        return None

    mun = municipio.strip()
    if not mun:
        return None

    if " - " in mun:
        codigo = mun.split(" - ", 1)[0].strip()
    else:
        codigo = mun.strip()

    codigo = codigo.replace(" ", "")

    if not codigo.isdigit():
        return None

    if len(codigo) == 5:
        return codigo
    elif len(codigo) < 5:
        return codigo.zfill(5)
    else:
        return None


def clasificar_tipo_atencion(tipo):
    """
    Clasifica un tipo de atención RIPS.

    Devuelve None cuando no puede clasificarse.
    """
    if not tipo or not isinstance(tipo, str):
        return None

    tipo_limpio = tipo.strip().upper()

    if not tipo_limpio:
        return None

    return TIPO_ATENCION_MAP.get(tipo_limpio)


def procesar_rips(df_rips):
    """
    Procesa RIPS.

    Excluye registros con valores inválidos.
    Conserva los registros con valores nulos.

    Los diagnósticos sin correspondencia se conservan
    con grupo diagnóstico nulo.

    C50 se contabiliza por separado, conforme a la
    regla de homologación existente.
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
        "municipios_nulos": 0,
        "diagnosticos_nulos": 0,
        "numero_atenciones_nulos": 0,
    }

    df_trabajo = df_rips.copy()

    columnas = (
        "Municipio",
        "Diagnostico",
        "NumeroAtenciones",
        "TipoAtencion",
    )

    for col in columnas:
        if col not in df_trabajo.columns:
            raise ValueError(
                f"RIPS: falta la columna {col}"
            )

    def _nulo(serie):
        return (
            serie.isna()
            | serie.astype("string")
            .str.strip()
            .eq("")
            .fillna(False)
        )

    municipio_nulo = _nulo(
        df_trabajo["Municipio"]
    )

    diagnostico_nulo = _nulo(
        df_trabajo["Diagnostico"]
    )

    atenciones_nulas = _nulo(
        df_trabajo["NumeroAtenciones"]
    )

    stats["municipios_nulos"] = int(
        municipio_nulo.sum()
    )

    stats["diagnosticos_nulos"] = int(
        diagnostico_nulo.sum()
    )

    stats["numero_atenciones_nulos"] = int(
        atenciones_nulas.sum()
    )

    # Extraer municipio sin inventar valores faltantes.
    df_trabajo["cod_municipio"] = (
        df_trabajo["Municipio"].apply(
            extraer_codigo_municipio
        )
    )

    invalido_municipio = (
        ~municipio_nulo
        & df_trabajo["cod_municipio"].isna()
    )

    df_trabajo.loc[
        municipio_nulo,
        "cod_municipio"
    ] = None

    # Extraer diagnóstico CIE10.
    df_trabajo["codigo_cie10"] = (
        df_trabajo["Diagnostico"].apply(
            extraer_codigo_cie10
        )
    )

    def _es_cie10_valido(codigo):
        return (
            isinstance(codigo, str)
            and bool(codigo)
            and codigo[0].isalpha()
            and any(
                c.isdigit()
                for c in codigo
            )
        )

    invalido_diagnostico = (
        ~diagnostico_nulo
        & ~df_trabajo["codigo_cie10"].apply(
            _es_cie10_valido
        )
    )

    # Convertir cantidades sin reemplazar nulos por cero.
    df_trabajo["NumeroAtenciones_raw"] = (
        pd.to_numeric(
            df_trabajo["NumeroAtenciones"],
            errors="coerce"
        )
    )

    invalido_numero = (
        ~atenciones_nulas
        & ~np.isfinite(
            df_trabajo["NumeroAtenciones_raw"]
        )
    )

    negativo = (
        df_trabajo["NumeroAtenciones_raw"]
        .lt(0)
        .fillna(False)
    )

    stats[
        "excluidos_codigo_municipio_invalido"
    ] = int(invalido_municipio.sum())

    stats[
        "excluidos_diagnostico_invalido"
    ] = int(invalido_diagnostico.sum())

    stats[
        "excluidos_numero_atenciones_no_numerico"
    ] = int(invalido_numero.sum())

    stats[
        "excluidos_numero_atenciones_negativo"
    ] = int(negativo.sum())

    stats[
        "atenciones_excluidas_negativas"
    ] = int(
        abs(
            df_trabajo.loc[
                negativo,
                "NumeroAtenciones_raw"
            ].sum()
        )
    )

    # Excluir únicamente valores inválidos.
    invalidos = (
        invalido_municipio
        | invalido_diagnostico
        | invalido_numero
        | negativo
    )

    stats["registros_excluidos"] = int(
        invalidos.sum()
    )

    stats["registros_unicos_excluidos"] = int(
        invalidos.sum()
    )

    df_trabajo = df_trabajo.loc[
        ~invalidos
    ].copy()

    df_trabajo["NumeroAtenciones"] = (
        df_trabajo["NumeroAtenciones_raw"]
    )

    # Homologación diagnóstica.
    df_trabajo["cod_grupo_diagnostico"] = (
        df_trabajo["Diagnostico"].apply(
            lambda v: (
                None
                if pd.isna(v)
                or str(v).strip() == ""
                else homologar_diagnostico(v)
            )
        )
    )

    codigos_cie10 = (
        df_trabajo["codigo_cie10"]
        .dropna()
        .unique()
    )

    stats["diagnosticos_distintos"] = len(
        codigos_cie10
    )

    homologados = set()
    sin_correspondencia = set()
    c50_codigos = set()

    for codigo in codigos_cie10:
        grupo = homologar_diagnostico(codigo)

        if es_categoria_c50(grupo):
            c50_codigos.add(codigo)
        elif grupo is not None:
            homologados.add(codigo)
        else:
            sin_correspondencia.add(codigo)

    stats["diagnosticos_homologados"] = len(
        homologados
    )

    stats[
        "diagnosticos_sin_correspondencia"
    ] = len(sin_correspondencia)

    stats["diagnosticos_c50_distintos"] = len(
        c50_codigos
    )

    if codigos_cie10.size:
        stats["cobertura_homologacion"] = round(
            len(homologados)
            / len(codigos_cie10)
            * 100,
            2
        )

    c50_mask = (
        df_trabajo["cod_grupo_diagnostico"]
        .apply(es_categoria_c50)
        .astype(bool)
    )

    stats["registros_c50"] = int(
        c50_mask.sum()
    )

    stats["atenciones_c50"] = int(
        df_trabajo.loc[
            c50_mask,
            "NumeroAtenciones"
        ].sum()
    )

    stats["registros_sin_correspondencia"] = int(
        (
            df_trabajo[
                "cod_grupo_diagnostico"
            ].isna()
            | c50_mask
        ).sum()
    )

    # Clasificar atenciones.
    df_trabajo["categoria_atencion"] = (
        df_trabajo["TipoAtencion"].apply(
            clasificar_tipo_atencion
        )
    )

    no_clasificados = (
        df_trabajo["categoria_atencion"].isna()
    )

    stats[
        "tipos_atencion_no_clasificados"
    ] = int(no_clasificados.sum())

    stats["tipos_atencion_desconocidos"] = sorted(
        df_trabajo.loc[
            no_clasificados
            & df_trabajo["TipoAtencion"].notna(),
            "TipoAtencion"
        ]
        .astype(str)
        .unique()
        .tolist()
    )

    # C50 queda fuera del cruce oficial.
    df_valido = df_trabajo.loc[
        ~c50_mask
    ].copy()

    total_atenciones = (
        df_trabajo["NumeroAtenciones"]
        .sum(min_count=1)
    )

    homologadas = (
        df_valido.loc[
            df_valido[
                "cod_grupo_diagnostico"
            ].notna(),
            "NumeroAtenciones"
        ].sum(min_count=1)
    )

    if (
        pd.notna(total_atenciones)
        and total_atenciones > 0
        and pd.notna(homologadas)
    ):
        stats[
            "cobertura_homologacion_ponderada"
        ] = round(
            homologadas
            / total_atenciones
            * 100,
            2
        )

    # Agrupar por municipio y grupo diagnóstico.
    claves = [
        "cod_municipio",
        "cod_grupo_diagnostico"
    ]

    grupos = df_valido.groupby(
        claves,
        dropna=False
    )

    agrupado = (
        grupos["NumeroAtenciones"]
        .sum(min_count=1)
        .rename("rips_total_atenciones")
        .reset_index()
    )

    # Si faltan datos necesarios para calcular
    # un total, conservar el resultado como nulo.
    df_valido["dato_incompleto"] = (
        df_valido["NumeroAtenciones"].isna()
        | df_valido["categoria_atencion"].isna()
    )

    incompletos = (
        df_valido.groupby(
            claves,
            dropna=False
        )["dato_incompleto"]
        .any()
        .reset_index(name="incompleto")
    )

    agrupado = agrupado.merge(
        incompletos,
        on=claves,
        how="left"
    )

    agrupado.loc[
        agrupado["incompleto"],
        "rips_total_atenciones"
    ] = np.nan

    categorias = (
        "consultas",
        "procedimientos",
        "urgencias",
        "hospitalizaciones"
    )

    for categoria in categorias:
        nombre = f"rips_{categoria}"

        cat = df_valido.loc[
            df_valido[
                "categoria_atencion"
            ].eq(categoria)
        ]

        suma = (
            cat.groupby(
                claves,
                dropna=False
            )["NumeroAtenciones"]
            .sum(min_count=1)
            .rename(nombre)
            .reset_index()
        )

        agrupado = agrupado.merge(
            suma,
            on=claves,
            how="left"
        )

        # Solo usar cero cuando se conoce el total
        # y no hubo atenciones de esa categoría.
        sin_categoria = ~(
            agrupado[claves]
            .apply(tuple, axis=1)
            .isin(
                set(
                    suma[claves]
                    .apply(tuple, axis=1)
                )
            )
        )

        agrupado.loc[
            sin_categoria
            & ~agrupado["incompleto"],
            nombre
        ] = 0

        agrupado.loc[
            agrupado["incompleto"],
            nombre
        ] = np.nan

        agrupado[
            f"rips_pct_{categoria}"
        ] = (
            agrupado[nombre]
            .div(
                agrupado[
                    "rips_total_atenciones"
                ].replace(0, np.nan)
            )
            * 100
        )

    agrupado = agrupado.drop(
        columns=["incompleto"]
    )

    stats["combinaciones_rips"] = len(
        agrupado
    )

    return agrupado, stats


# ==========================================
# INTEGRACIÓN DANE + RIPS
# ==========================================

def integrar_dane_rips(df_dane, df_rips):
    """
    Integra DANE y RIPS por municipio y grupo.

    No reemplaza valores nulos por cero.
    No crea columnas inexistentes artificialmente.

    DANE determina las combinaciones del dataset
    supervisado porque contiene la variable objetivo.
    """
    claves = [
        "cod_municipio",
        "cod_grupo_diagnostico"
    ]

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

    columnas_finales = (
        claves
        + columnas_rips
        + ["dane_pct_sin_asistencia"]
    )

    # Verificar columnas obligatorias.
    for nombre, df, requeridas in (
        (
            "DANE",
            df_dane,
            claves + ["dane_pct_sin_asistencia"]
        ),
        (
            "RIPS",
            df_rips,
            claves + columnas_rips
        ),
    ):
        faltantes = sorted(
            set(requeridas) - set(df.columns)
        )

        if faltantes:
            raise ValueError(
                f"{nombre}: faltan columnas: {faltantes}"
            )

    # Evitar emparejar claves nulas entre fuentes.
    rips_con_claves = df_rips.loc[
        df_rips[claves].notna().all(axis=1)
    ].copy()

    integrado = df_dane.merge(
        rips_con_claves,
        on=claves,
        how="left",
        indicator=True,
        validate="one_to_one"
    )

    stats = {
        "combinaciones_sin_rips": int(
            integrado["_merge"]
            .eq("left_only")
            .sum()
        ),
        "combinaciones_rips_clave_nula_sin_integrar": int(
            df_rips[claves]
            .isna()
            .any(axis=1)
            .sum()
        ),
    }

    integrado = integrado.drop(
        columns=["_merge"]
    )

    # Conservar los valores faltantes.
    integrado = integrado[
        columnas_finales
    ].copy()

    columnas_porcentaje = [
        c
        for c in integrado.columns
        if c.startswith("rips_pct_")
    ] + ["dane_pct_sin_asistencia"]

    for col in columnas_porcentaje:
        integrado[col] = (
            integrado[col].round(2)
        )

    return integrado, stats


# ==========================================
# VALIDACIÓN DEL DATASET
# ==========================================

def validar_dataset(df):
    """
    Valida valores inválidos.

    Los valores nulos se permiten y se reportan,
    pero no se consideran errores por sí solos.
    """
    errores = []

    claves = [
        "cod_municipio",
        "cod_grupo_diagnostico"
    ]

    duplicados = (
        df.loc[
            df[claves].notna().all(axis=1)
        ]
        .duplicated(subset=claves)
        .sum()
    )

    if duplicados:
        errores.append(
            f"Se encontraron {duplicados} "
            "combinaciones duplicadas."
        )

    codigos = df[
        "cod_municipio"
    ].astype("string")

    invalidos = (
        codigos.notna()
        & ~codigos.str.fullmatch(
            r"[0-9]{5}"
        ).fillna(False)
    )

    if invalidos.any():
        errores.append(
            "Algunos códigos municipales "
            "no tienen 5 dígitos."
        )

    conteos = [
        "rips_total_atenciones",
        "rips_consultas",
        "rips_procedimientos",
        "rips_urgencias",
        "rips_hospitalizaciones",
    ]

    porcentajes = [
        "rips_pct_consultas",
        "rips_pct_procedimientos",
        "rips_pct_urgencias",
        "rips_pct_hospitalizaciones",
        "dane_pct_sin_asistencia",
    ]

    for col in conteos + porcentajes:
        serie = pd.to_numeric(
            df[col],
            errors="coerce"
        )

        invalido = (
            df[col].notna()
            & serie.isna()
        )

        if (
            invalido.any()
            or np.isinf(
                serie.dropna()
            ).any()
        ):
            errores.append(
                f"Valores no numéricos "
                f"o infinitos en {col}."
            )

        if (
            col in conteos
            and serie.lt(0).any()
        ):
            errores.append(
                f"Valores negativos en {col}."
            )

        if (
            col in porcentajes
            and (
                serie.lt(0).any()
                or serie.gt(100).any()
            )
        ):
            errores.append(
                f"Porcentajes fuera de "
                f"[0, 100] en {col}."
            )

    return errores

# ==========================================
# ESCRITURA ATÓMICA
# ==========================================

def guardar_dataset_atomico(df, ruta_final):
    """
    Guarda el CSV en un archivo temporal y luego
    lo mueve a su ubicación definitiva.
    """
    ruta_final = Path(ruta_final)

    ruta_final.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    fd, temp_path = tempfile.mkstemp(
        suffix=".csv",
        dir=str(ruta_final.parent),
        prefix=".tmp_",
    )

    try:
        with os.fdopen(
            fd,
            "w",
            encoding="utf-8"
        ) as f:
            df.to_csv(
                f,
                index=False,
                encoding="utf-8"
            )

        Path(temp_path).replace(
            ruta_final
        )

    except Exception:
        try:
            Path(temp_path).unlink(
                missing_ok=True
            )
        except OSError:
            pass

        raise


def guardar_json_atomico(ruta_final, datos):
    """
    Guarda un diccionario JSON de forma atómica.
    """
    ruta_final = Path(ruta_final)

    ruta_final.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    fd, temp_path = tempfile.mkstemp(
        suffix=".json",
        dir=str(ruta_final.parent),
        prefix=".tmp_",
    )

    try:
        with os.fdopen(
            fd,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                datos,
                f,
                ensure_ascii=False,
                indent=4
            )

        Path(temp_path).replace(
            ruta_final
        )

    except Exception:
        try:
            Path(temp_path).unlink(
                missing_ok=True
            )
        except OSError:
            pass

        raise


# ==========================================
# VERIFICACIÓN DE VIGENCIA
# ==========================================

def verificar_vigencia_procesamiento():
    """
    Comprueba si el dataset procesado sigue vigente
    respecto a los archivos RAW originales.
    """
    metadata_path = (
        REPORTS_DIR / METADATA_FILE
    )

    if not metadata_path.exists():
        return {
            "disponible": False,
            "vigente": False,
            "mensaje": (
                "No existe un dataset procesado."
            ),
        }

    try:
        with metadata_path.open(
            "r",
            encoding="utf-8"
        ) as f:
            metadata = json.load(f)

    except (
        json.JSONDecodeError,
        OSError
    ):
        return {
            "disponible": True,
            "vigente": False,
            "mensaje": "Metadatos corruptos.",
        }

    vigente = True
    mensajes = []

    # Verificar DANE.
    archivo_dane = encontrar_archivo_raw(
        DANE_RAW_PATTERN
    )

    if archivo_dane:
        hash_actual = obtener_archivo_hash(
            archivo_dane
        )

        hash_guardado = metadata.get(
            "hash_dane"
        )

        if hash_actual != hash_guardado:
            vigente = False

            mensajes.append(
                "El archivo RAW de DANE ha cambiado."
            )

    else:
        vigente = False
        mensajes.append(
            "No se encontró el archivo RAW de DANE."
        )

    # Verificar RIPS.
    archivo_rips = encontrar_archivo_raw(
        RIPS_RAW_PATTERN
    )

    if archivo_rips:
        hash_actual = obtener_archivo_hash(
            archivo_rips
        )

        hash_guardado = metadata.get(
            "hash_rips"
        )

        if hash_actual != hash_guardado:
            vigente = False

            mensajes.append(
                "El archivo RAW de RIPS ha cambiado."
            )

    else:
        vigente = False
        mensajes.append(
            "No se encontró el archivo RAW de RIPS."
        )

    return {
        "disponible": True,
        "vigente": vigente,
        "generado_en": metadata.get(
            "generado_en"
        ),
        "anio": metadata.get("anio"),
        "mensaje": (
            "; ".join(mensajes)
            if mensajes
            else "El dataset está vigente."
        ),
    }


# ==========================================
# BLOQUEO DE PROCESAMIENTO
# ==========================================

def _es_proceso_activo(pid):
    """
    Comprueba si un proceso continúa activo.
    """
    try:
        os.kill(pid, 0)
        return True

    except ProcessLookupError:
        return False

    except PermissionError:
        return True

    except OSError:
        return False


def _adquirir_bloqueo():
    """
    Adquiere el bloqueo de procesamiento.

    Utiliza un archivo con O_CREAT | O_EXCL
    para evitar ejecuciones simultáneas.
    """
    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    lock_path = (
        PROCESSED_DIR / LOCK_FILE
    )

    def crear_lock():
        try:
            fd = os.open(
                str(lock_path),
                os.O_CREAT
                | os.O_EXCL
                | os.O_WRONLY,
            )

            os.write(
                fd,
                str(os.getpid()).encode(
                    "utf-8"
                )
            )

            return fd

        except FileExistsError:
            return None

    fd = crear_lock()

    if fd is not None:
        return fd

    # El bloqueo ya existe.
    try:
        with lock_path.open(
            "r",
            encoding="utf-8"
        ) as f:
            pid_str = f.read().strip()

    except (
        OSError,
        UnicodeDecodeError
    ):
        pid_str = ""

    # Si el bloqueo está vacío o corrupto,
    # no se elimina automáticamente para
    # evitar interrumpir otro procesamiento.
    if not pid_str:
        return None

    try:
        old_pid = int(pid_str)

    except ValueError:
        return None

    if _es_proceso_activo(old_pid):
        return None

    # Recuperar bloqueo de un proceso finalizado.
    try:
        lock_path.unlink()

    except OSError:
        return None

    return crear_lock()


def _liberar_bloqueo(fd):
    """
    Libera el bloqueo de procesamiento.
    """
    if fd is not None:
        try:
            os.close(fd)

        except OSError:
            pass

        lock_path = (
            PROCESSED_DIR / LOCK_FILE
        )

        try:
            lock_path.unlink(
                missing_ok=True
            )

        except OSError:
            pass


# ==========================================
# EJECUCIÓN PRINCIPAL
# ==========================================

def ejecutar_procesamiento():
    """
    Ejecuta el procesamiento completo.

    Impide dos ejecuciones simultáneas.
    """
    if not _processing_lock.acquire(
        blocking=False
    ):
        return {
            "estado": "error",
            "errores": [
                "Ya hay una ejecución de "
                "procesamiento activa. "
                "Intente más tarde."
            ],
            "advertencias": [],
            "estadisticas": {},
        }

    lock_fd = _adquirir_bloqueo()

    if lock_fd is None:
        _processing_lock.release()

        return {
            "estado": "error",
            "errores": [
                "Ya hay una ejecución de "
                "procesamiento activa en "
                "otro proceso. "
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
    """
    Ejecuta el procesamiento DANE y RIPS.

    Genera:
      - dataset_entrenamiento.csv
      - processing_metadata.json
      - processing_report.json
    """
    resultado = {
        "estado": "en_proceso",
        "errores": [],
        "advertencias": [],
        "estadisticas": {},
    }

    ahora = datetime.now(
        timezone.utc
    ).isoformat()

    # ======================================
    # 1. LOCALIZAR ARCHIVOS RAW
    # ======================================

    archivo_dane = encontrar_archivo_raw(
        DANE_RAW_PATTERN
    )

    archivo_rips = encontrar_archivo_raw(
        RIPS_RAW_PATTERN
    )

    if archivo_dane is None:
        resultado["estado"] = "error"

        resultado["errores"].append(
            "No se encontró el archivo RAW "
            "de DANE en data/raw/."
        )

        return resultado

    if archivo_rips is None:
        resultado["estado"] = "error"

        resultado["errores"].append(
            "No se encontró el archivo RAW "
            "de RIPS en data/raw/."
        )

        return resultado

    # ======================================
    # 2. LEER DATASETS ORIGINALES
    # ======================================

    try:
        df_dane = leer_csv_raw(
            archivo_dane
        )

    except Exception as error:
        resultado["estado"] = "error"

        resultado["errores"].append(
            f"Error al leer DANE: {error}"
        )

        return resultado

    try:
        df_rips = leer_csv_raw(
            archivo_rips
        )

    except Exception as error:
        resultado["estado"] = "error"

        resultado["errores"].append(
            f"Error al leer RIPS: {error}"
        )

        return resultado

    resultado["estadisticas"][
        "archivo_dane"
    ] = archivo_dane.name

    resultado["estadisticas"][
        "archivo_rips"
    ] = archivo_rips.name

    resultado["estadisticas"][
        "registros_originales_dane"
    ] = len(df_dane)

    resultado["estadisticas"][
        "registros_originales_rips"
    ] = len(df_rips)

    # ======================================
    # 3. VALIDAR AÑOS
    # ======================================

    anio_dane, errores_anio_dane = (
        detectar_anio(
            df_dane,
            "ANO",
            "DANE"
        )
    )

    anio_rips, errores_anio_rips = (
        detectar_anio(
            df_rips,
            "Año",
            "RIPS"
        )
    )

    anio, errores_anios = (
        validar_anios_coincidentes(
            anio_dane,
            errores_anio_dane,
            anio_rips,
            errores_anio_rips
        )
    )

    if errores_anios:
        resultado["errores"].extend(
            errores_anios
        )

    if anio is None:
        resultado["estado"] = "error"
        return resultado

    resultado["estadisticas"][
        "anio"
    ] = anio

    # ======================================
    # 4. REVISAR DUPLICADOS RIPS
    # ======================================

    df_rips_limpio, stats_dedup = (
        validar_y_deduplicar_rips(
            df_rips
        )
    )

    resultado["estadisticas"][
        "duplicados_rips"
    ] = stats_dedup[
        "duplicados_exactos"
    ]

    # ======================================
    # 5. PROCESAR DANE
    # ======================================

    try:
        df_dane_proc, stats_dane = (
            procesar_dane(
                df_dane
            )
        )

    except Exception as error:
        resultado["estado"] = "error"

        resultado["errores"].append(
            f"Error al procesar DANE: {error}"
        )

        return resultado

    resultado["estadisticas"][
        "dane"
    ] = stats_dane

    # ======================================
    # 6. PROCESAR RIPS
    # ======================================

    try:
        df_rips_proc, stats_rips = (
            procesar_rips(
                df_rips_limpio
            )
        )

    except Exception as error:
        resultado["estado"] = "error"

        resultado["errores"].append(
            f"Error al procesar RIPS: {error}"
        )

        return resultado

    resultado["estadisticas"][
        "rips"
    ] = stats_rips

    # ======================================
    # 7. INTEGRAR DANE Y RIPS
    # ======================================

    try:
        df_integrado, stats_integracion = (
            integrar_dane_rips(
                df_dane_proc,
                df_rips_proc
            )
        )

    except Exception as error:
        resultado["estado"] = "error"

        resultado["errores"].append(
            f"Error al integrar: {error}"
        )

        return resultado

    resultado["estadisticas"][
        "integracion"
    ] = stats_integracion

    # ======================================
    # 8. VALIDAR DATASET UNIFICADO
    # ======================================

    errores_validacion = validar_dataset(
        df_integrado
    )

    if errores_validacion:
        resultado["errores"].extend(
            errores_validacion
        )

        resultado["estado"] = "error"

        return resultado

    # ======================================
    # 9. GUARDAR DATASET FINAL
    # ======================================

    ruta_dataset = (
        PROCESSED_DIR / DATASET_FILE
    )

    try:
        guardar_dataset_atomico(
            df_integrado,
            ruta_dataset
        )

    except Exception as error:
        resultado["estado"] = "error"

        resultado["errores"].append(
            f"Error al guardar dataset: {error}"
        )

        return resultado

    # ======================================
    # 10. GUARDAR METADATOS
    # ======================================

    metadata = {
        "generado_en": ahora,
        "anio": anio,
        "archivo_dane": archivo_dane.name,
        "archivo_rips": archivo_rips.name,
        "hash_dane": obtener_archivo_hash(
            archivo_dane
        ),
        "hash_rips": obtener_archivo_hash(
            archivo_rips
        ),
        "observaciones": len(
            df_integrado
        ),
    }

    try:
        guardar_json_atomico(
            REPORTS_DIR / METADATA_FILE,
            metadata
        )

    except Exception as error:
        resultado["advertencias"].append(
            "No se pudieron guardar "
            f"los metadatos: {error}"
        )

    # ======================================
    # 11. GENERAR REPORTE
    # ======================================

    reporte = {
        "generado_en": ahora,
        "anio": anio,

        # Datos originales.
        "registros_originales_dane": len(
            df_dane
        ),
        "registros_originales_rips": len(
            df_rips
        ),

        # Duplicados.
        "duplicados_rips_eliminados": 0,
        "duplicados_rips_detectados": (
            stats_dedup[
                "duplicados_exactos"
            ]
        ),
        "registros_rips_procesados": (
            stats_dedup[
                "registros_despues_deduplicacion"
            ]
        ),

        # Exclusiones DANE.
        "dane_registros_excluidos": (
            stats_dane[
                "registros_unicos_excluidos"
            ]
        ),
        "dane_excluidos_cod_municipio_invalido": (
            stats_dane[
                "excluidos_cod_municipio_invalido"
            ]
        ),
        "dane_excluidos_cau_homol_invalido": (
            stats_dane[
                "excluidos_cau_homol_invalido"
            ]
        ),
        "dane_excluidos_cau_homol_nulo": (
            stats_dane[
                "excluidos_cau_homol_nulo"
            ]
        ),
        "dane_excluidos_asis_med_invalido": (
            stats_dane[
                "excluidos_asis_med_invalido"
            ]
        ),
        "dane_asis_med_nulo": (
            stats_dane[
                "asis_med_nulo"
            ]
        ),

        # Exclusiones RIPS.
        "rips_registros_excluidos": (
            stats_rips[
                "registros_unicos_excluidos"
            ]
        ),
        "rips_excluidos_numero_atenciones_negativo": (
            stats_rips[
                "excluidos_numero_atenciones_negativo"
            ]
        ),
        "rips_excluidos_numero_atenciones_no_numerico": (
            stats_rips[
                "excluidos_numero_atenciones_no_numerico"
            ]
        ),
        "rips_excluidos_codigo_municipio_invalido": (
            stats_rips[
                "excluidos_codigo_municipio_invalido"
            ]
        ),
        "rips_excluidos_diagnostico_invalido": (
            stats_rips[
                "excluidos_diagnostico_invalido"
            ]
        ),
        "rips_atenciones_excluidas_negativas": (
            stats_rips[
                "atenciones_excluidas_negativas"
            ]
        ),

        # Homologación.
        "diagnosticos_cie10_distintos": (
            stats_rips[
                "diagnosticos_distintos"
            ]
        ),
        "diagnosticos_homologados": (
            stats_rips[
                "diagnosticos_homologados"
            ]
        ),
        "diagnosticos_sin_correspondencia": (
            stats_rips[
                "diagnosticos_sin_correspondencia"
            ]
        ),
        "cobertura_homologacion_pct": (
            stats_rips[
                "cobertura_homologacion"
            ]
        ),
        "cobertura_homologacion_ponderada_pct": (
            stats_rips[
                "cobertura_homologacion_ponderada"
            ]
        ),
        "registros_rips_sin_correspondencia": (
            stats_rips[
                "registros_sin_correspondencia"
            ]
        ),

        # Categoría C50.
        "registros_c50": (
            stats_rips["registros_c50"]
        ),
        "atenciones_c50": (
            stats_rips["atenciones_c50"]
        ),
        "diagnosticos_c50_distintos": (
            stats_rips[
                "diagnosticos_c50_distintos"
            ]
        ),

        # Integración.
        "municipios_distintos": (
            stats_dane[
                "municipios_distintos"
            ]
        ),
        "grupos_diagnosticos_distintos": (
            stats_dane[
                "grupos_distintos"
            ]
        ),
        "combinaciones_municipio_grupo": len(
            df_integrado
        ),
        "combinaciones_sin_registros_rips": (
            stats_integracion[
                "combinaciones_sin_rips"
            ]
        ),
        "observaciones_excluidas_sin_respuestas_validas": (
            stats_dane[
                "combinaciones_sin_respuestas_validas"
            ]
        ),
        "tipos_atencion_no_clasificados": (
            stats_rips[
                "tipos_atencion_no_clasificados"
            ]
        ),
        "tipos_atencion_desconocidos": (
            stats_rips[
                "tipos_atencion_desconocidos"
            ]
        ),

        # Resultados finales.
        "observaciones_finales": len(
            df_integrado
        ),
        "valores_faltantes": int(
            df_integrado.isna().sum().sum()
        ),
        "nulos_por_columna": {
            col: int(n)
            for col, n in (
                df_integrado
                .isna()
                .sum()
                .items()
            )
        },
        "observaciones_con_objetivo_nulo": int(
            df_integrado[
                "dane_pct_sin_asistencia"
            ].isna().sum()
        ),

        # Limitaciones conocidas.
        "limitaciones_homologacion": [
            (
                "U07 (COVID-19): Se asigna al "
                "grupo 010 siguiendo la práctica "
                "del DANE. El Boletín Técnico "
                "EEVV confirma U07 en el grupo "
                "109 de la Lista 6/67 OPS, "
                "pero no existe un documento "
                "oficial que mapee explícitamente "
                "al grupo 010 de la Lista "
                "Colombia 105. Esta regla "
                "complementaria está pendiente "
                "de verificación documental."
            )
        ],
    }

    try:
        guardar_json_atomico(
            REPORTS_DIR / REPORT_FILE,
            reporte
        )

    except Exception as error:
        resultado["advertencias"].append(
            "No se pudo guardar "
            f"el reporte: {error}"
        )

    # ======================================
    # 12. RESPUESTA FINAL
    # ======================================

    resultado["estado"] = "exitoso"

    resultado["estadisticas"][
        "observaciones_finales"
    ] = len(df_integrado)

    resultado["estadisticas"][
        "ruta_dataset"
    ] = str(ruta_dataset)

    return resultado
