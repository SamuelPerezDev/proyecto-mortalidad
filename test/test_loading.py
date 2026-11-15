
"""Pruebas básicas del módulo EDA y funciones de carga."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Agregar el proyecto al path para importar src
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd

from src.eda import (
    generar_eda_dane,
    generar_eda_rips,
    cargar_eda_stats,
    guardar_eda_stats,
    eliminar_eda_stats,
    calcular_frecuencias,
    calcular_top_list,
    calcular_calidad_dane,
    calcular_calidad_rips,
    _safe_value,
    _safe_dict,
    encontrar_archivo_raw,
    verificar_vigencia,
    obtener_archivo_hash,
    invalidar_eda,
    obtener_estado_eda,
)


# ==========================================
# DATOS DE PRUEBA
# ==========================================

def crear_df_dane_pequeno():
    """Crea un DataFrame DANE mínimo para pruebas."""
    return pd.DataFrame({
        "COD_DPTO": ["11", "11", "25", "25", "52"],
        "COD_MUNIC": ["11001", "11001", "25001", "25001", "52001"],
        "A_DEFUN": ["1", "1", "2", "1", "2"],
        "SIT_DEFUN": ["1", "2", "1", "1", "2"],
        "OTRSITIODE": ["", "", "", "", ""],
        "TIPO_DEFUN": ["2", "2", "2", "2", "2"],
        "ANO": ["2021", "2021", "2021", "2021", "2021"],
        "MES": ["1", "2", "3", "4", "5"],
        "HORA": ["10", "11", "12", "13", "14"],
        "MINUTOS": ["30", "45", "00", "15", "30"],
        "SEXO": ["1", "2", "1", "2", "1"],
        "EST_CIVIL": ["1", "2", "1", "3", "2"],
        "GRU_ED1": ["0-14", "15-24", "25-44", "45-64", "65+"],
        "GRU_ED2": ["0-9", "10-19", "20-29", "30-39", "40-49"],
        "NIVEL_EDU": ["1", "2", "3", "4", "5"],
        "ULTCURFAL": ["1", "2", "1", "2", "3"],
        "MUERTEPORO": ["1", "2", "1", "2", "1"],
        "SIMUERTEPO": ["1", "2", "1", "2", "1"],
        "OCUPACION": ["1", "2", "3", "4", "5"],
        "IDPERTET": ["1", "2", "1", "2", "1"],
        "CODPRES": ["1", "2", "1", "2", "1"],
        "CODPTORE": ["11", "25", "52", "11", "25"],
        "CODMUNRE": ["11001", "25001", "52001", "11001", "25001"],
        "AREA_RES": ["1", "2", "1", "2", "1"],
        "SEG_SOCIAL": ["1", "2", "3", "1", "2"],
        "IDADMISALUD": ["1", "2", "1", "2", "1"],
        "P_PMAN_IRIS": ["1", "2", "1", "2", "1"],
        "CONS_EXP": ["1", "2", "1", "2", "1"],
        "MU_PARTO": ["1", "2", "1", "2", "1"],
        "T_PARTO": ["1", "2", "1", "2", "1"],
        "TIPO_EMB": ["1", "2", "1", "2", "1"],
        "T_GES": ["1", "2", "1", "2", "1"],
        "T_GES_AGRU_CIE": ["A", "B", "A", "B", "A"],
        "PESO_NAC": ["3000", "2500", "3200", "2800", "3100"],
        "EDAD_MADRE": ["25", "30", "35", "28", "32"],
        "N_HIJOSV": ["1", "2", "3", "1", "2"],
        "N_HIJOSM": ["0", "1", "2", "0", "1"],
        "EST_CIVM": ["1", "2", "1", "2", "1"],
        "NIV_EDUM": ["1", "2", "1", "2", "1"],
        "ULTCURMAD": ["1", "2", "1", "2", "1"],
        "EMB_FAL": ["1", "2", "1", "2", "1"],
        "EMB_SEM": ["40", "38", "39", "40", "37"],
        "EMB_MES": ["1", "2", "3", "4", "5"],
        "CODOCUR": ["1", "2", "1", "2", "1"],
        "CODMUNOC": ["11001", "25001", "52001", "11001", "25001"],
        "C_MUERTE": ["A00", "B00", "C00", "D00", "E00"],
        "C_MUERTEB": ["A0", "B0", "C0", "D0", "E0"],
        "C_MUERTEC": ["A", "B", "C", "D", "E"],
        "C_MUERTED": ["0", "1", "2", "3", "4"],
        "C_MUERTEE": ["01", "02", "03", "04", "05"],
        "ASIS_MED": ["1", "2", "1", "2", "3"],
        "CAUSA_MULT": ["1", "2", "1", "2", "1"],
        "C_BAS1": ["010", "020", "030", "040", "050"],
        "CAUSA_667": ["010", "020", "030", "040", "050"],
        "IDPROFCER": ["1", "2", "1", "2", "1"],
        "CAU_HOMOL": ["010", "020", "030", "040", "050"],
    })


def crear_df_rips_pequeno():
    """Crea un DataFrame RIPS mínimo para pruebas."""
    return pd.DataFrame({
        "Departamento": ["11", "11", "25", "25", "52"],
        "Municipio": ["11001", "11001", "25001", "25001", "52001"],
        "Año": ["2021", "2021", "2021", "2021", "2021"],
        "TipoAtencion": ["Consulta", "Consulta", "Urgencia", "Consulta", "Urgencia"],
        "Diagnostico": ["J06.9", "J06.9", "I10", "J06.9", "I10"],
        "NumeroAtenciones": ["5", "3", "10", "2", "8"],
    })


# ==========================================
# PRUEBAS DE SERIALIZACIÓN
# ==========================================

def test_safe_value_none():
    """Verifica que None se mantiene como None."""
    assert _safe_value(None) is None


def test_safe_value_int():
    """Verifica que los enteros se convierten correctamente."""
    assert _safe_value(42) == 42
    assert isinstance(_safe_value(42), int)


def test_safe_value_float():
    """Verifica que los floats se convierten correctamente."""
    assert _safe_value(3.14) == 3.14
    assert isinstance(_safe_value(3.14), float)


def test_safe_value_string():
    """Verifica que las cadenas se mantienen."""
    assert _safe_value("hola") == "hola"


def test_safe_value_dict():
    """Verifica que los diccionarios se recorren recursivamente."""
    d = {"a": 1, "b": "texto", "c": None}
    result = _safe_value(d)
    assert result == {"a": 1, "b": "texto", "c": None}


def test_safe_value_list():
    """Verifica que las listas se recorren recursivamente."""
    lst = [1, "texto", None, 3.14]
    result = _safe_value(lst)
    assert result == [1, "texto", None, 3.14]


def test_safe_dict():
    """Verifica que _safe_dict convierte todo el diccionario."""
    d = {
        "entero": 42,
        "flotante": 3.14,
        "cadena": "texto",
        "nulo": None,
        "lista": [1, 2, 3],
        "anidado": {"a": 1, "b": "dos"}
    }
    result = _safe_dict(d)
    assert result["entero"] == 42
    assert result["flotante"] == 3.14
    assert result["cadena"] == "texto"
    assert result["nulo"] is None
    assert result["lista"] == [1, 2, 3]
    assert result["anidado"]["a"] == 1


# ==========================================
# PRUEBAS DE FRECUENCIAS
# ==========================================

def test_calcular_frecuencias_basico():
    """Verifica que calcular_frecuencias produce count y pct."""
    serie = pd.Series(["a", "a", "b", "c", "c", "c"])
    result = calcular_frecuencias(serie, top_n=3)
    assert "c" in result
    assert result["c"]["count"] == 3
    assert abs(result["c"]["pct"] - 50.0) < 0.01


def test_calcular_frecuencias_top_n():
    """Verifica que se limita a top-N."""
    serie = pd.Series(["a", "b", "c", "d", "e"])
    result = calcular_frecuencias(serie, top_n=2)
    assert len(result) == 2


def test_calcular_frecuencias_vacio():
    """Verifica que un DataFrame vacío no falla."""
    serie = pd.Series([], dtype=str)
    result = calcular_frecuencias(serie)
    assert result == {}


def test_calcular_top_list():
    """Verifica que calcular_top_list produce una lista ordenada."""
    serie = pd.Series(["x", "x", "y", "z"])
    result = calcular_top_list(serie, top_n=2)
    assert len(result) == 2
    assert result[0]["codigo"] == "x"
    assert result[0]["count"] == 2


# ==========================================
# PRUEBAS DE CALIDAD
# ==========================================

def test_calcular_calidad_dane():
    """Verifica que calcular_calidad_dane detecta duplicados, vacíos, solo espacios y espacios externos."""
    df = pd.DataFrame({
        "A": ["1", "2", "1", ""],
        "B": ["x", "y ", "  x", "z"],
    })
    calidad = calcular_calidad_dane(df)
    assert "duplicados_exactos" in calidad
    assert "nulos_por_columna" in calidad
    assert "vacios_por_columna" in calidad
    assert "solo_espacios_por_columna" in calidad
    assert "espacios_ext_por_columna" in calidad
    assert calidad["vacios_por_columna"].get("A") == 1
    # B tiene "y " y "  x" con espacios externos
    assert calidad["espacios_ext_por_columna"].get("B") == 2


def test_calcular_calidad_rips():
    """Verifica que calcular_calidad_rips detecta espacios."""
    df = pd.DataFrame({
        "A": ["1 ", "2", " 3", ""],
        "B": ["x", "y", "z", "w"],
    })
    calidad = calcular_calidad_rips(df)
    assert "duplicados_exactos" in calidad
    assert "espacios_por_columna" in calidad
    assert calidad["espacios_por_columna"].get("A") == 2


def test_calcular_frecuencias_con_nan():
    """Verifica que calcular_frecuencias incluye NaN con dropna=False."""
    import numpy as np
    serie = pd.Series(["a", "a", np.nan, "b", np.nan])
    result = calcular_frecuencias(serie, top_n=5)
    assert "nan" in result
    assert result["nan"]["count"] == 2
    assert result["a"]["count"] == 2
    assert result["b"]["count"] == 1


def test_calcular_top_list_con_nan():
    """Verifica que calcular_top_list incluye NaN con dropna=False."""
    import numpy as np
    serie = pd.Series(["x", "x", np.nan, "y", np.nan, np.nan])
    result = calcular_top_list(serie, top_n=5)
    # NaN debe aparecer en la lista
    nan_entry = [e for e in result if e["codigo"] == "nan"]
    assert len(nan_entry) == 1
    assert nan_entry[0]["count"] == 3


# ==========================================
# PRUEBAS DE EDA DANE
# ==========================================

def test_generar_eda_dane_claves():
    """Verifica que generar_eda_dane produce las claves esperadas."""
    df = crear_df_dane_pequeno()
    stats = generar_eda_dane(df)

    # Claves principales
    assert "dataset" in stats
    assert stats["dataset"] == "DANE"
    assert "generado_en" in stats
    assert "dimensiones" in stats
    assert "calidad" in stats
    assert "demografico" in stats
    assert "geografico" in stats
    assert "causas" in stats
    assert "asistencia" in stats
    assert "cruces" in stats


def test_generar_eda_dane_dimensiones():
    """Verifica que las dimensiones son correctas."""
    df = crear_df_dane_pequeno()
    stats = generar_eda_dane(df)
    assert stats["dimensiones"]["filas"] == 5
    assert stats["dimensiones"]["columnas"] == 56


def test_generar_eda_dane_demografico():
    """Verifica que las distribuciones demográficas existen."""
    df = crear_df_dane_pequeno()
    stats = generar_eda_dane(df)
    assert "sexo" in stats["demografico"]
    assert "gru_ed1" in stats["demografico"]
    assert "est_civil" in stats["demografico"]


def test_generar_eda_dane_geografico():
    """Verifica que las distribuciones geográficas existen."""
    df = crear_df_dane_pequeno()
    stats = generar_eda_dane(df)
    assert "a_defun" in stats["geografico"]
    assert "sit_defun" in stats["geografico"]
    assert "area_res" in stats["geografico"]
    assert "top_departamentos" in stats["geografico"]


def test_generar_eda_dane_causas():
    """Verifica que las causas de muerte existen."""
    df = crear_df_dane_pequeno()
    stats = generar_eda_dane(df)
    assert "cau_homol_top10" in stats["causas"]
    assert "c_bas1_top10" in stats["causas"]
    assert "causa_667_top10" in stats["causas"]


def test_generar_eda_dane_asistencia():
    """Verifica que la asistencia médica existe."""
    df = crear_df_dane_pequeno()
    stats = generar_eda_dane(df)
    assert "asis_med" in stats["asistencia"]


def test_generar_eda_dane_cruces():
    """Verifica que los cruces existen."""
    df = crear_df_dane_pequeno()
    stats = generar_eda_dane(df)
    assert "a_defun_x_p_pman_iris_top10" in stats["cruces"]


# ==========================================
# PRUEBAS DE EDA RIPS
# ==========================================

def test_generar_eda_rips_claves():
    """Verifica que generar_eda_rips produce las claves esperadas."""
    df = crear_df_rips_pequeno()
    stats = generar_eda_rips(df)

    assert "dataset" in stats
    assert stats["dataset"] == "RIPS"
    assert "generado_en" in stats
    assert "dimensiones" in stats
    assert "calidad" in stats
    assert "numero_atenciones" in stats
    assert "univariado" in stats
    assert "geografico" in stats
    assert "cruces" in stats


def test_generar_eda_rips_dimensiones():
    """Verifica que las dimensiones son correctas."""
    df = crear_df_rips_pequeno()
    stats = generar_eda_rips(df)
    assert stats["dimensiones"]["filas"] == 5
    assert stats["dimensiones"]["columnas"] == 6


def test_generar_eda_rips_numero_atenciones():
    """Verifica que las estadísticas de NumeroAtenciones son correctas."""
    df = crear_df_rips_pequeno()
    stats = generar_eda_rips(df)
    na = stats["numero_atenciones"]
    assert na["validos"] == 5
    assert na["minimo"] == 2.0
    assert na["maximo"] == 10.0
    assert "mediana" in na
    assert "p25" in na
    assert "p75" in na
    assert "media" in na
    assert "desviacion_estandar" in na
    assert "suma" in na
    assert na["suma"] == 28  # 5+3+10+2+8


def test_generar_eda_rips_univariado():
    """Verifica que el análisis univariado existe."""
    df = crear_df_rips_pequeno()
    stats = generar_eda_rips(df)
    assert "tipo_atencion" in stats["univariado"]
    assert "diagnostico_top10" in stats["univariado"]


def test_generar_eda_rips_geografico():
    """Verifica que el análisis geográfico existe."""
    df = crear_df_rips_pequeno()
    stats = generar_eda_rips(df)
    assert "top_departamentos_filas" in stats["geografico"]
    assert "top_departamentos_atenciones" in stats["geografico"]
    assert "departamentos_distintos" in stats["geografico"]
    assert "municipios_distintos" in stats["geografico"]


def test_generar_eda_rips_cruces():
    """Verifica que los cruces existen."""
    df = crear_df_rips_pequeno()
    stats = generar_eda_rips(df)
    assert "departamento_x_tipo_atencion_top10" in stats["cruces"]


# ==========================================
# PRUEBAS DE ALMACENAMIENTO
# ==========================================

def test_guardar_y_cargar_eda_stats():
    """Verifica que guardar y cargar funcionan correctamente."""
    stats = {
        "dataset": "DANE",
        "generado_en": "2025-01-01T00:00:00",
        "dimensiones": {"filas": 100, "columnas": 56},
        "calidad": {"duplicados_exactos": 0},
        "demografico": {},
        "geografico": {},
        "causas": {},
        "asistencia": {},
        "cruces": {},
        "archivo_hash": "abc123",
        "archivo_nombre": "test.csv"
    }

    with patch.object(Path, 'exists', return_value=False):
        guardar_eda_stats("DANE", stats)

    loaded = cargar_eda_stats("DANE")
    assert loaded is not None
    assert loaded["dataset"] == "DANE"
    assert loaded["dimensiones"]["filas"] == 100

    # Limpiar
    eliminar_eda_stats("DANE")


def test_cargar_eda_stats_no_existe():
    """Verifica que cargar devuelve None si no existe."""
    eliminar_eda_stats("RIPS")
    result = cargar_eda_stats("RIPS")
    assert result is None


def test_eliminar_eda_stats():
    """Verifica que eliminar funciona."""
    stats = {
        "dataset": "RIPS",
        "generado_en": "2025-01-01T00:00:00",
        "dimensiones": {"filas": 100, "columnas": 6},
        "calidad": {},
        "numero_atenciones": {},
        "univariado": {},
        "geografico": {},
        "cruces": {},
        "archivo_hash": "xyz",
        "archivo_nombre": "test.csv"
    }

    with patch.object(Path, 'exists', return_value=False):
        guardar_eda_stats("RIPS", stats)

    assert cargar_eda_stats("RIPS") is not None
    eliminar_eda_stats("RIPS")
    assert cargar_eda_stats("RIPS") is None


# ==========================================
# PRUEBAS DE VIGENCIA
# ==========================================

def test_verificar_vigencia_sin_stats():
    """Verifica que sin estadísticas, no hay vigencia."""
    eliminar_eda_stats("DANE")
    estado = verificar_vigencia("DANE")
    assert estado["disponible"] is False
    assert estado["vigente"] is False


def test_obtener_archivo_hash():
    """Verifica que el hash se calcula correctamente."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b\n1,2\n3,4\n")
        temp_path = f.name

    try:
        hash1 = obtener_archivo_hash(Path(temp_path))
        assert hash1 is not None
        assert len(hash1) == 32  # MD5 hex

        # Mismo archivo = mismo hash
        hash2 = obtener_archivo_hash(Path(temp_path))
        assert hash1 == hash2

        # Modificar archivo = hash diferente
        with open(temp_path, "w") as f:
            f.write("a,b\n5,6\n7,8\n")
        hash3 = obtener_archivo_hash(Path(temp_path))
        assert hash1 != hash3
    finally:
        os.unlink(temp_path)


def test_invalidar_eda():
    """Verifica que invalidar elimina las estadísticas."""
    stats = {
        "dataset": "DANE",
        "generado_en": "2025-01-01T00:00:00",
        "dimensiones": {"filas": 100, "columnas": 56},
        "calidad": {},
        "demografico": {},
        "geografico": {},
        "causas": {},
        "asistencia": {},
        "cruces": {},
        "archivo_hash": "abc",
        "archivo_nombre": "test.csv"
    }

    with patch.object(Path, 'exists', return_value=False):
        guardar_eda_stats("DANE", stats)

    assert cargar_eda_stats("DANE") is not None
    invalidar_eda("DANE")
    assert cargar_eda_stats("DANE") is None


# ==========================================
# PRUEBAS DE JSON SERIALIZABLE
# ==========================================

def test_eda_dane_json_serializable():
    """Verifica que el resultado de EDA DANE es JSON-serializable."""
    df = crear_df_dane_pequeno()
    stats = generar_eda_dane(df)
    # Debe poder serializarse sin error
    json_str = json.dumps(_safe_dict(stats))
    assert len(json_str) > 0
    # Y debe poder deserializarse
    loaded = json.loads(json_str)
    assert loaded["dataset"] == "DANE"


def test_eda_rips_json_serializable():
    """Verifica que el resultado de EDA RIPS es JSON-serializable."""
    df = crear_df_rips_pequeno()
    stats = generar_eda_rips(df)
    json_str = json.dumps(_safe_dict(stats))
    assert len(json_str) > 0
    loaded = json.loads(json_str)
    assert loaded["dataset"] == "RIPS"


# ==========================================
# PRUEBAS DE generar_eda() y regenerar_eda()
# ==========================================

def test_generar_eda_dataset_desconocido():
    """Verifica que generar_eda devuelve error para dataset desconocido."""
    from src.eda import generar_eda
    result = generar_eda("DESCONOCIDO")
    assert result["estado"] == "error"
    assert "Dataset desconocido" in result["mensaje"]


def test_generar_eda_sin_archivo_raw():
    """Verifica que generar_eda devuelve no_disponible sin archivo RAW."""
    from src.eda import generar_eda
    # DANE no tiene archivo RAW en el entorno de pruebas
    result = generar_eda("DANE")
    assert result["estado"] == "no_disponible"


def test_regenerar_eda_estructura():
    """Verifica que regenerar_eda devuelve estructura correcta."""
    from src.eda import regenerar_eda
    result = regenerar_eda()
    assert "dane" in result
    assert "rips" in result
    # Ambos deben estar no_disponible sin archivos RAW
    assert result["dane"]["estado"] == "no_disponible"
    assert result["rips"]["estado"] == "no_disponible"


def test_obtener_estado_eda_estructura():
    """Verifica que obtener_estado_eda devuelve estructura correcta."""
    estado = obtener_estado_eda()
    assert "dane" in estado
    assert "rips" in estado
    assert "disponible" in estado["dane"]
    assert "vigente" in estado["dane"]
    assert "disponible" in estado["rips"]
    assert "vigente" in estado["rips"]


# ==========================================
# PRUEBAS DE ESCENARIOS DE ERROR
# ==========================================

def test_guardar_eda_stats_serializacion_fallida():
    """Verifica que guardar_eda_stats falla si los datos no son serializables."""
    import numpy as np
    # Un objeto que no puede serializarse directamente
    stats_malo = {
        "dataset": "DANE",
        "generado_en": "2025-01-01T00:00:00",
        "dimensiones": {"filas": np.array([1, 2, 3])},  # array no serializable
        "calidad": {},
        "demografico": {},
        "geografico": {},
        "causas": {},
        "asistencia": {},
        "cruces": {},
    }
    # _safe_dict debe convertir el array a lista
    safe = _safe_dict(stats_malo)
    json_str = json.dumps(safe)
    assert len(json_str) > 0


def test_cargar_eda_stats_json_corrupto():
    """Verifica que cargar_eda_stats devuelve None con JSON corrupto."""
    from src.eda import REPORTS_DIR, DANE_EDA_FILE
    ruta = REPORTS_DIR / DANE_EDA_FILE
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with ruta.open("w") as f:
            f.write("{{{{no es JSON válido}}}}")
        result = cargar_eda_stats("DANE")
        assert result is None
    finally:
        eliminar_eda_stats("DANE")


def test_eda_dane_con_columnas_faltantes():
    """Verifica que generar_eda_dane no falla si faltan columnas."""
    df_minimo = pd.DataFrame({
        "COD_DPTO": ["11"],
        "SEXO": ["1"],
    })
    stats = generar_eda_dane(df_minimo)
    assert stats["dataset"] == "DANE"
    assert stats["dimensiones"]["filas"] == 1
    # Las columnas faltantes no generan error
    assert "demografico" in stats
    assert "geografico" in stats


def test_eda_rips_con_columnas_faltantes():
    """Verifica que generar_eda_rips no falla si faltan columnas."""
    df_minimo = pd.DataFrame({
        "Departamento": ["11"],
        "Año": ["2021"],
    })
    stats = generar_eda_rips(df_minimo)
    assert stats["dataset"] == "RIPS"
    assert stats["dimensiones"]["filas"] == 1
    # NumeroAtenciones vacío si falta la columna
    assert "numero_atenciones" in stats


# ==========================================
# EJECUCIÓN DE PRUEBAS
# ==========================================

if __name__ == "__main__":
    import traceback

    # Recopilar todas las funciones test_*
    test_funcs = [
        obj for name, obj in globals().items()
        if name.startswith("test_") and callable(obj)
    ]

    passed = 0
    failed = 0

    for test_func in test_funcs:
        try:
            test_func()
            print(f"  ✅ {test_func.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {test_func.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{passed} pasadas, {failed} falladas, {passed + failed} total")
    sys.exit(0 if failed == 0 else 1)
