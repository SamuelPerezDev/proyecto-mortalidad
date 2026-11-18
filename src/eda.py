
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.schemas import DANE_COLUMNS, RIPS_COLUMNS

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
REPORTS_DIR = ROOT / "reports"

# Archivos de estadísticas EDA
DANE_EDA_FILE = "dane_eda_statistics.json"
RIPS_EDA_FILE = "rips_eda_statistics.json"

# Archivos RAW esperados (nombres flexibles — se busca por patrón)
DANE_RAW_PATTERN = "dane_no_fetal_2021"
RIPS_RAW_PATTERN = "rips_2021"

# Límite top-N para distribuciones de alta cardinalidad
TOP_N = 10


# ==========================================
# SERIALIZACIÓN SEGURA
# ==========================================

def _safe_value(value):
    """Convierte valores NumPy/Pandas a tipos nativos de Python para JSON."""
    if value is None:
        return None
    if isinstance(value, (bool,)):
        return bool(value)
    if isinstance(value, (int,)):
        return int(value)
    if isinstance(value, (float,)):
        if pd.isna(value):
            return None
        return float(value)
    if isinstance(value, (str,)):
        return str(value)
    if isinstance(value, dict):
        return {k: _safe_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    # Fallback para tipos NumPy
    try:
        return int(value)
    except (ValueError, TypeError):
        pass
    try:
        return float(value)
    except (ValueError, TypeError):
        pass
    return str(value)


def _safe_dict(d):
    """Recorre un diccionario y convierte todos los valores a tipos JSON-safe."""
    return _safe_value(d)


# ==========================================
# LECTURA DE CSV DESDE RAW
# ==========================================

def leer_csv_raw(ruta, encoding=None):
    """
    Lee un CSV desde data/raw/ sin modificar los datos.

    Si *encoding* se proporciona, se usa directamente.
    Si es None, intenta UTF-8 y cae a Latin-1 como fallback.
    """
    if encoding is not None:
        return pd.read_csv(
            ruta,
            dtype=str,
            keep_default_na=False,
            encoding=encoding
        )
    try:
        return pd.read_csv(
            ruta,
            dtype=str,
            keep_default_na=False,
            encoding="utf-8"
        )
    except UnicodeDecodeError:
        return pd.read_csv(
            ruta,
            dtype=str,
            keep_default_na=False,
            encoding="latin-1"
        )


def encontrar_archivo_raw(patron):
    """Busca un archivo CSV en data/raw/ que coincida con el patrón."""
    if not RAW_DIR.exists():
        return None
    for archivo in RAW_DIR.iterdir():
        if archivo.is_file() and archivo.suffix.lower() == ".csv":
            nombre = archivo.stem.lower()
            if patron.lower() in nombre:
                return archivo
    return None


# ==========================================
# ALMACENAMIENTO DE RESULTADOS
# ==========================================

def guardar_eda_stats(dataset, stats):
    """
    Guarda las estadísticas EDA en reports/ de forma atómica.
    Escribe primero en un archivo temporal y luego lo renombra.
    """
    nombre_archivo = (
        DANE_EDA_FILE if dataset == "DANE" else RIPS_EDA_FILE
    )
    ruta_final = REPORTS_DIR / nombre_archivo

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Escribir en archivo temporal primero
    fd, temp_path = tempfile.mkstemp(
        suffix=".json",
        dir=str(REPORTS_DIR),
        prefix=".tmp_"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(
                _safe_dict(stats),
                f,
                ensure_ascii=False,
                indent=4
            )
        # Reemplazo atómico
        Path(temp_path).replace(ruta_final)
    except Exception:
        # Limpia el archivo temporal en caso de error
        try:
            Path(temp_path).unlink(missing_ok=True)
        except OSError:
            pass
        raise


def cargar_eda_stats(dataset):
    """
    Carga las estadísticas EDA desde reports/.
    Devuelve None si no existen o están corruptas.
    """
    nombre_archivo = (
        DANE_EDA_FILE if dataset == "DANE" else RIPS_EDA_FILE
    )
    ruta = REPORTS_DIR / nombre_archivo

    if not ruta.exists():
        return None

    try:
        with ruta.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def eliminar_eda_stats(dataset):
    """Elimina las estadísticas EDA de un dataset."""
    nombre_archivo = (
        DANE_EDA_FILE if dataset == "DANE" else RIPS_EDA_FILE
    )
    ruta = REPORTS_DIR / nombre_archivo
    try:
        ruta.unlink(missing_ok=True)
    except OSError:
        pass


# ==========================================
# VIGENCIA DE RESULTADOS
# ==========================================

def obtener_archivo_hash(ruta_archivo):
    """Calcula un hash simple del archivo para verificar cambios."""
    import hashlib
    if not ruta_archivo or not Path(ruta_archivo).exists():
        return None
    hasher = hashlib.md5()
    with Path(ruta_archivo).open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verificar_vigencia(dataset):
    """
    Verifica si las estadísticas EDA están vigentes respecto al archivo RAW actual.
    Devuelve un diccionario con el estado de vigencia.
    """
    stats = cargar_eda_stats(dataset)
    patron = DANE_RAW_PATTERN if dataset == "DANE" else RIPS_RAW_PATTERN
    archivo_raw = encontrar_archivo_raw(patron)

    if stats is None:
        return {
            "disponible": False,
            "vigente": False,
            "generado_en": None,
            "filas": None,
            "archivo_raw": archivo_raw.name if archivo_raw else None
        }

    # Verifica si el archivo RAW ha cambiado desde la generación
    archivo_hash_actual = obtener_archivo_hash(archivo_raw) if archivo_raw else None
    archivo_hash_guardado = stats.get("archivo_hash")

    vigente = (
        archivo_hash_actual is not None
        and archivo_hash_actual == archivo_hash_guardado
    )

    return {
        "disponible": True,
        "vigente": vigente,
        "generado_en": stats.get("generado_en"),
        "filas": stats.get("dimensiones", {}).get("filas"),
        "archivo_raw": archivo_raw.name if archivo_raw else None
    }


# ==========================================
# CÁLCULO DE FRECUENCIAS
# ==========================================

def calcular_frecuencias(series, top_n=TOP_N):
    """
    Calcula frecuencias de una serie categórica.
    Incluye valores NaN (dropna=False) como en los notebooks.
    Devuelve un diccionario con count y pct por categoría.
    """
    total = len(series)
    if total == 0:
        return {}

    counts = series.value_counts(dropna=False).head(top_n)
    result = {}
    for categoria, count in counts.items():
        if pd.isna(categoria):
            clave = "nan"
        else:
            clave = str(categoria)
        result[clave] = {
            "count": int(count),
            "pct": round(float(count) / total * 100, 2)
        }
    return result


def calcular_top_list(series, top_n=TOP_N, value_key="codigo"):
    """
    Calcula un top-N como lista ordenada.
    Incluye valores NaN (dropna=False) como en los notebooks.
    """
    total = len(series)
    if total == 0:
        return []

    counts = series.value_counts(dropna=False).head(top_n)
    result = []
    for valor, count in counts.items():
        if pd.isna(valor):
            val_str = "nan"
        else:
            val_str = str(valor)
        result.append({
            value_key: val_str,
            "count": int(count),
            "pct": round(float(count) / total * 100, 2)
        })
    return result


# ==========================================
# CALIDAD DE DATOS
# ==========================================

def calcular_calidad_dane(df):
    """
    Calcula métricas de calidad para DANE.
    Sigue el patrón del notebook: nulos, vacíos, solo espacios, espacios externos.
    """
    duplicados = int(df.duplicated().sum())

    nulos_por_columna = {}
    vacios_por_columna = {}
    solo_espacios_por_columna = {}
    espacios_ext_por_columna = {}

    for col in df.columns:
        serie = df[col]
        # Nulos (NaN reales)
        nulos = int(serie.isna().sum())
        # Cadenas vacías
        vacios = int(serie.eq("").sum())
        # Solo espacios (no vacío, pero strip() == "")
        texto = serie.astype(str)
        solo_espacios = int(
            ((serie != "") & texto.str.strip().eq("")).sum()
        )
        # Espacios externos (tiene leading/trailing whitespace y no es vacío después de strip)
        texto_limpio = texto.str.strip()
        espacios_ext = int(
            ((serie != "") &
             texto.str.len().gt(0) &
             texto.str.strip().ne(texto) &
             texto_limpio.ne("")
             ).sum()
        )

        if nulos > 0:
            nulos_por_columna[col] = nulos
        if vacios > 0:
            vacios_por_columna[col] = vacios
        if solo_espacios > 0:
            solo_espacios_por_columna[col] = solo_espacios
        if espacios_ext > 0:
            espacios_ext_por_columna[col] = espacios_ext

    return {
        "duplicados_exactos": duplicados,
        "nulos_por_columna": nulos_por_columna,
        "vacios_por_columna": vacios_por_columna,
        "solo_espacios_por_columna": solo_espacios_por_columna,
        "espacios_ext_por_columna": espacios_ext_por_columna
    }


def calcular_calidad_rips(df):
    """Calcula métricas de calidad para RIPS."""
    duplicados = int(df.duplicated().sum())

    nulos_por_columna = {}
    vacios_por_columna = {}
    espacios_por_columna = {}

    for col in df.columns:
        serie = df[col].astype(str)
        # Nulos
        nulos = int(df[col].isna().sum())
        # Cadenas vacías
        vacios = int(serie.str.strip().eq("").sum())
        # Espacios al inicio o final
        espacios = int(serie.ne(serie.str.strip()).sum())

        if nulos > 0:
            nulos_por_columna[col] = nulos
        if vacios > 0:
            vacios_por_columna[col] = vacios
        if espacios > 0:
            espacios_por_columna[col] = espacios

    return {
        "duplicados_exactos": duplicados,
        "nulos_por_columna": nulos_por_columna,
        "vacios_por_columna": vacios_por_columna,
        "espacios_por_columna": espacios_por_columna
    }


# ==========================================
# EDA DANE
# ==========================================

def generar_eda_dane(df):
    """
    Genera todas las estadísticas EDA para el dataset DANE.
    Sigue el patrón del notebook EDA_DANE_2021.ipynb.
    """
    ahora = datetime.now(timezone.utc).isoformat()

    # Dimensiones
    dimensiones = {
        "filas": int(len(df)),
        "columnas": int(len(df.columns))
    }

    # Calidad
    calidad = calcular_calidad_dane(df)

    # Demográfico
    demografico = {}
    for col in ["SEXO", "GRU_ED1", "GRU_ED2", "EST_CIVIL"]:
        if col in df.columns:
            clave = col.lower()
            demografico[clave] = calcular_frecuencias(df[col])

    # Geográfico
    geografico = {}
    for col in ["A_DEFUN", "SIT_DEFUN", "AREA_RES"]:
        if col in df.columns:
            clave = col.lower()
            geografico[clave] = calcular_frecuencias(df[col])

    # Top departamentos
    if "COD_DPTO" in df.columns:
        geografico["top_departamentos"] = calcular_top_list(
            df["COD_DPTO"], value_key="cod"
        )

    # Causas de muerte
    causas = {}
    for col in ["CAU_HOMOL", "C_BAS1", "CAUSA_667"]:
        if col in df.columns:
            clave = col.lower() + "_top10"
            causas[clave] = calcular_top_list(df[col])

    # Asistencia médica
    asistencia = {}
    if "ASIS_MED" in df.columns:
        asistencia["asis_med"] = calcular_frecuencias(df["ASIS_MED"])

    # Cruces: A_DEFUN × P_PMAN_IRIS (como en el notebook)
    cruces = {}
    if "A_DEFUN" in df.columns and "P_PMAN_IRIS" in df.columns:
        try:
            cruce = df.groupby(["A_DEFUN", "P_PMAN_IRIS"]).size()
            cruce_top = cruce.head(TOP_N)
            cruces["a_defun_x_p_pman_iris_top10"] = [
                {
                    "a_defun": str(row.name[0]),
                    "p_pman_iris": str(row.name[1]),
                    "count": int(row)
                }
                for row in cruce_top.iterrows()
            ]
        except Exception:
            cruces["a_defun_x_p_pman_iris_top10"] = []

    stats = {
        "dataset": "DANE",
        "generado_en": ahora,
        "dimensiones": dimensiones,
        "calidad": calidad,
        "demografico": demografico,
        "geografico": geografico,
        "causas": causas,
        "asistencia": asistencia,
        "cruces": cruces
    }

    return stats


# ==========================================
# EDA RIPS
# ==========================================

def generar_eda_rips(df):
    """
    Genera todas las estadísticas EDA para el dataset RIPS.
    Sigue el patrón del notebook EDA_RIPS_2021.ipynb.
    """
    ahora = datetime.now(timezone.utc).isoformat()

    # Dimensiones
    dimensiones = {
        "filas": int(len(df)),
        "columnas": int(len(df.columns))
    }

    # Calidad
    calidad = calcular_calidad_rips(df)

    # Estadísticas de NumeroAtenciones
    numero_atenciones = {}
    if "NumeroAtenciones" in df.columns:
        conteos = pd.to_numeric(df["NumeroAtenciones"], errors="coerce")
        validos = conteos.dropna()
        total_validos = int(len(validos))
        total_invalidos = int(len(conteos) - total_validos)

        if total_validos > 0:
            numero_atenciones = {
                "validos": total_validos,
                "invalidos": total_invalidos,
                "minimo": float(validos.min()),
                "p25": float(validos.quantile(0.25)),
                "mediana": float(validos.median()),
                "p75": float(validos.quantile(0.75)),
                "media": round(float(validos.mean()), 2),
                "desviacion_estandar": round(float(validos.std()), 2),
                "maximo": float(validos.max()),
                "suma": int(validos.sum())
            }
        else:
            numero_atenciones = {
                "validos": 0,
                "invalidos": total_invalidos,
                "minimo": None,
                "p25": None,
                "mediana": None,
                "p75": None,
                "media": None,
                "maximo": None
            }

    # Univariado
    univariado = {}

    # TipoAtencion con filas y suma de atenciones
    if "TipoAtencion" in df.columns:
        tipo_counts = df["TipoAtencion"].value_counts().head(TOP_N)
        tipo_atencion_dict = {}
        for tipo, filas in tipo_counts.items():
            tipo_mask = df["TipoAtencion"] == tipo
            atenciones_suma = 0
            if "NumeroAtenciones" in df.columns:
                conteos = pd.to_numeric(
                    df.loc[tipo_mask, "NumeroAtenciones"], errors="coerce"
                )
                atenciones_suma = int(conteos.sum())
            tipo_atencion_dict[str(tipo)] = {
                "filas": int(filas),
                "atenciones": atenciones_suma
            }
        univariado["tipo_atencion"] = tipo_atencion_dict

    # Diagnostico top-10
    if "Diagnostico" in df.columns:
        diag_counts = df["Diagnostico"].value_counts().head(TOP_N)
        diagnostico_list = []
        for diag, filas in diag_counts.items():
            diag_mask = df["Diagnostico"] == diag
            atenciones_suma = 0
            if "NumeroAtenciones" in df.columns:
                conteos = pd.to_numeric(
                    df.loc[diag_mask, "NumeroAtenciones"], errors="coerce"
                )
                atenciones_suma = int(conteos.sum())
            diagnostico_list.append({
                "codigo": str(diag),
                "filas": int(filas),
                "atenciones": atenciones_suma
            })
        univariado["diagnostico_top10"] = diagnostico_list

    # Geográfico
    geografico = {}

    if "Departamento" in df.columns:
        # Top departamentos por filas
        depto_filas = df["Departamento"].value_counts().head(TOP_N)
        geografico["top_departamentos_filas"] = [
            {
                "departamento": str(depto),
                "filas": int(count),
                "pct": round(float(count) / len(df) * 100, 2)
            }
            for depto, count in depto_filas.items()
        ]

        # Top departamentos por atenciones
        if "NumeroAtenciones" in df.columns:
            depto_atenciones = df.groupby("Departamento")["NumeroAtenciones"].apply(
                lambda x: pd.to_numeric(x, errors="coerce").sum()
            ).dropna().sort_values(ascending=False).head(TOP_N)
            geografico["top_departamentos_atenciones"] = [
                {
                    "departamento": str(depto),
                    "atenciones": int(atenciones)
                }
                for depto, atenciones in depto_atenciones.items()
            ]

        # Distintos
        geografico["departamentos_distintos"] = int(
            df["Departamento"].nunique()
        )

    if "Municipio" in df.columns:
        geografico["municipios_distintos"] = int(
            df["Municipio"].nunique()
        )

    # Cruces: Departamento × TipoAtencion
    cruces = {}
    if "Departamento" in df.columns and "TipoAtencion" in df.columns:
        try:
            cruce = df.groupby(["Departamento", "TipoAtencion"]).size()
            cruce_top = cruce.head(TOP_N)
            cruces["departamento_x_tipo_atencion_top10"] = [
                {
                    "departamento": str(row.name[0]),
                    "tipo_atencion": str(row.name[1]),
                    "count": int(row)
                }
                for row in cruce_top.iterrows()
            ]
        except Exception:
            cruces["departamento_x_tipo_atencion_top10"] = []

    stats = {
        "dataset": "RIPS",
        "generado_en": ahora,
        "dimensiones": dimensiones,
        "calidad": calidad,
        "numero_atenciones": numero_atenciones,
        "univariado": univariado,
        "geografico": geografico,
        "cruces": cruces
    }

    return stats


# ==========================================
# GENERACIÓN COMPLETA DEL EDA
# ==========================================

def generar_eda(dataset):
    """
    Genera el EDA completo para un dataset dado.
    Lee desde data/raw/, calcula estadísticas y guarda en reports/.
    Devuelve un diccionario con el resultado de la operación.
    """
    encoding_csv = None
    if dataset == "DANE":
        patron = DANE_RAW_PATTERN
        generador = generar_eda_dane
    elif dataset == "RIPS":
        patron = RIPS_RAW_PATTERN
        generador = generar_eda_rips
        encoding_csv = "utf-8"
    else:
        return {
            "estado": "error",
            "mensaje": f"Dataset desconocido: {dataset}"
        }

    # Buscar archivo RAW
    archivo_raw = encontrar_archivo_raw(patron)
    if archivo_raw is None:
        return {
            "estado": "no_disponible",
            "mensaje": f"No se encontró archivo RAW para {dataset}"
        }

    try:
        # Leer CSV sin modificar
        df = leer_csv_raw(archivo_raw, encoding=encoding_csv)

        # Calcular hash del archivo para vigencia
        archivo_hash = obtener_archivo_hash(archivo_raw)

        # Generar estadísticas
        stats = generador(df)

        # Agregar metadatos de vigencia
        stats["archivo_hash"] = archivo_hash
        stats["archivo_nombre"] = archivo_raw.name

        # Guardar de forma atómica
        guardar_eda_stats(dataset, stats)

        return {
            "estado": "generado",
            "filas": stats["dimensiones"]["filas"],
            "columnas": stats["dimensiones"]["columnas"],
            "generado_en": stats["generado_en"]
        }

    except Exception as error:
        return {
            "estado": "error",
            "mensaje": str(error)
        }


def regenerar_eda():
    """
    Regenera el EDA para ambos datasets (DANE y RIPS).
    Devuelve un diccionario con el resultado de cada uno.
    """
    resultados = {}

    for dataset in ["DANE", "RIPS"]:
        resultados[dataset.lower()] = generar_eda(dataset)

    return resultados


# ==========================================
# INVALIDACIÓN DE RESULTADOS
# ==========================================

def invalidar_eda(dataset):
    """
    Invalida las estadísticas EDA de un dataset eliminando el archivo JSON.
    Se llama cuando se sube un nuevo archivo RAW.
    """
    eliminar_eda_stats(dataset)


# ==========================================
# ESTADO GENERAL
# ==========================================

def obtener_estado_eda():
    """
    Devuelve el estado general del EDA para ambos datasets.
    """
    return {
        "dane": verificar_vigencia("DANE"),
        "rips": verificar_vigencia("RIPS")
    }
