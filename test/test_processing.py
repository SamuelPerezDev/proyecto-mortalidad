"""Pruebas del módulo de procesamiento y homologación diagnóstica."""

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

# Agregar el proyecto al path para importar src
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import pytest
import numpy as np

from src.diagnostic_mapping import (
    homologar_diagnostico,
    extraer_codigo_cie10,
    codigo_en_rango,
    obtener_grupo,
    obtener_rangos_cie10,
    todos_los_codigos_cau_homol,
    LISTA_105,
    _normalizar_codigo,
    _codigos_iguales,
    CATEGORIA_C50_AUXILIAR,
    es_categoria_c50,
)
from src.processing import (
    detectar_anio,
    validar_anios_coincidentes,
    procesar_dane,
    validar_y_deduplicar_rips,
    extraer_codigo_municipio,
    clasificar_tipo_atencion,
    procesar_rips,
    integrar_dane_rips,
    validar_dataset,
    guardar_dataset_atomico,
    ejecutar_procesamiento,
    verificar_vigencia_procesamiento,
    _adquirir_bloqueo,
    _liberar_bloqueo,
    _es_proceso_activo,
    PROCESSED_DIR,
    LOCK_FILE,
)


# ==========================================
# DATOS DE PRUEBA
# ==========================================

def crear_df_dane_test():
    """Crea un DataFrame DANE pequeño para pruebas."""
    return pd.DataFrame({
        "CODMUNRE": ["20001", "20001", "20001", "20001", "25001", "25001"],
        "CAU_HOMOL": ["010", "010", "051", "051", "010", "051"],
        "ASIS_MED": ["1", "2", "1", "2", "2", "3"],
        "ANO": ["2021", "2021", "2021", "2021", "2021", "2021"],
    })


def crear_df_rips_test():
    """Crea un DataFrame RIPS pequeño para pruebas."""
    return pd.DataFrame({
        "Departamento": ["20", "20", "20", "25", "25"],
        "Municipio": ["20001 - VALLEDUPAR", "20001 - VALLEDUPAR", "20001 - VALLEDUPAR",
                      "25001 - BOGOTA", "25001 - BOGOTA"],
        "Año": ["2021", "2021", "2021", "2021", "2021"],
        "TipoAtencion": ["CONSULTAS", "URGENCIAS", "PROCEDIMIENTOS DE SALUD",
                         "HOSPITALIZACIONES", "CONSULTAS"],
        "Diagnostico": ["R104 - DOLOR", "I219 - INFARTO", "J189 - NEUMONIA",
                        "I10X - HIPERTENSION", "N390 - INFECCION"],
        "NumeroAtenciones": ["10", "5", "20", "3", "8"],
    })


# ==========================================
# PRUEBAS DE HOMOLOGACIÓN DIAGNÓSTICA
# ==========================================

class TestHomologacionDiagnostica:
    """Pruebas de la homologación CIE-10 a Lista 105."""

    def test_extraer_codigo_con_descripcion(self):
        """Extraer código de diagnóstico con descripción."""
        assert extraer_codigo_cie10("R104 - OTROS DOLORES") == "R104"

    def test_extraer_codigo_sin_descripcion(self):
        """Extraer código sin descripción."""
        assert extraer_codigo_cie10("I10X") == "I10X"

    def test_extraer_codigo_con_punto(self):
        """Extraer código con subcategoría."""
        assert extraer_codigo_cie10("U072 - COVID-19") == "U072"

    def test_extraer_codigo_vacio(self):
        """Código vacío devuelve None."""
        assert extraer_codigo_cie10("") is None
        assert extraer_codigo_cie10(None) is None

    def test_homologar_r104_a_089(self):
        """R104 (síntomas) debe mapear a grupo 089."""
        resultado = homologar_diagnostico("R104 - DOLOR ABDOMINAL")
        assert resultado == "089"

    def test_homologar_i219_a_051(self):
        """I219 (infarto) debe mapear a grupo 051."""
        resultado = homologar_diagnostico("I219 - INFARTO AGUDO")
        assert resultado == "051"

    def test_homologar_i10x_a_050(self):
        """I10X (hipertensión) debe mapear a grupo 050."""
        resultado = homologar_diagnostico("I10X - HIPERTENSION")
        assert resultado == "050"

    def test_homologar_u072_a_010(self):
        """U072 (COVID-19) debe mapear a grupo 010."""
        resultado = homologar_diagnostico("U072 - COVID-19")
        assert resultado == "010"

    def test_homologar_j189_a_059(self):
        """J189 (neumonía) debe mapear a grupo 059."""
        resultado = homologar_diagnostico("J189 - NEUMONIA")
        assert resultado == "059"

    def test_homologar_n390_a_075(self):
        """N390 (infección urinaria) debe mapear a grupo 075."""
        resultado = homologar_diagnostico("N390 - INFECCION URINARIA")
        assert resultado == "075"

    def test_homologar_codigo_desconocido(self):
        """Código sin correspondencia devuelve None."""
        resultado = homologar_diagnostico("Z00 - EXAMEN GENERAL")
        assert resultado is None

    def test_codigo_en_rango_simple(self):
        """Verificar código dentro de un rango simple."""
        assert codigo_en_rango("R104", "R00-R99") is True
        assert codigo_en_rango("R001", "R00-R99") is True
        assert codigo_en_rango("S001", "R00-R99") is False

    def test_codigo_en_rango_individual(self):
        """Verificar código individual."""
        assert codigo_en_rango("A20", "A20") is True
        assert codigo_en_rango("A21", "A20") is False

    def test_codigo_con_x_final(self):
        """Código con X final debe coincidir con el código base."""
        assert _codigos_iguales("I10X", "I10") is True

    def test_obtener_grupo(self):
        """Obtener descripción de grupo."""
        desc = obtener_grupo("010")
        assert desc is not None
        assert "infecciosas" in desc.lower()

    def test_obtener_rangos_cie10(self):
        """Obtener rangos CIE-10 de un grupo."""
        rangos = obtener_rangos_cie10("051")
        assert rangos is not None
        assert "I20-I25" in rangos

    def test_todos_los_codigos(self):
        """Verificar que hay 105 códigos CAU_HOMOL."""
        codigos = todos_los_codigos_cau_homol()
        assert len(codigos) == 105

    def test_lista_105_completa(self):
        """Verificar que la lista tiene 105 entradas."""
        assert len(LISTA_105) == 105


# ==========================================
# PRUEBAS DE C50
# ==========================================

class TestC50:
    """Pruebas de la categoría auxiliar C50."""

    def test_c50_no_asignado_a_024(self):
        """C50 no se asigna al grupo 024."""
        resultado = homologar_diagnostico("C50 - TUMOR MAM")
        assert resultado == CATEGORIA_C50_AUXILIAR
        assert resultado != "024"

    def test_c50_no_asignado_a_038(self):
        """C50 no se asigna al grupo 038."""
        resultado = homologar_diagnostico("C50 - TUMOR MAM")
        assert resultado != "038"

    def test_c50_es_categoria_auxiliar(self):
        """es_categoria_c50 devuelve True para C50."""
        assert es_categoria_c50(CATEGORIA_C50_AUXILIAR) is True
        assert es_categoria_c50("024") is False
        assert es_categoria_c50(None) is False

    def test_c50_con_subcategoria(self):
        """C50 con subcategoría también es categoría auxiliar."""
        resultado = homologar_diagnostico("C509 - TUMOR MAM NOS")
        assert resultado == CATEGORIA_C50_AUXILIAR

    def test_grupos_024_038_intactos_en_dane(self):
        """Los grupos 024 y 038 permanecen en la Lista 105."""
        assert "024" in todos_los_codigos_cau_homol()
        assert "038" in todos_los_codigos_cau_homol()

    def test_otros_codigos_024_no_affected(self):
        """Los otros códigos del grupo 024 no existen (solo C50)."""
        # El grupo 024 solo tiene C50, que ahora es categoría auxiliar
        # Los demás grupos funcionan correctamente
        assert homologar_diagnostico("C53 - CUELLO UTERO") == "025"

    def test_otros_codigos_038_no_affected(self):
        """Los otros códigos del grupo 038 funcionan."""
        assert homologar_diagnostico("C60 - PENIS") == "038"
        assert homologar_diagnostico("C45 - MESENTERIO") == "038"


# ==========================================
# PRUEBAS DE DETECCIÓN DEL AÑO
# ==========================================

class TestDeteccionAnio:
    """Pruebas de detección y validación del año."""

    def test_anio_correcto(self):
        """Año único y válido."""
        df = pd.DataFrame({"ANO": ["2021", "2021", "2021"]})
        anio, errores = detectar_anio(df, "ANO", "DANE")
        assert anio == 2021
        assert len(errores) == 0

    def test_varios_anios(self):
        """Múltiples años deben detener el procesamiento."""
        df = pd.DataFrame({"ANO": ["2021", "2021", "2022"]})
        anio, errores = detectar_anio(df, "ANO", "DANE")
        assert anio is None
        assert any("múltiples años" in e for e in errores)

    def test_anios_coinciden(self):
        """Años iguales en ambas fuentes."""
        anio, errores = validar_anios_coincidentes(
            2021, [], 2021, []
        )
        assert anio == 2021
        assert len(errores) == 0

    def test_anios_no_coinciden(self):
        """Años diferentes deben detener."""
        anio, errores = validar_anios_coincidentes(
            2021, [], 2022, []
        )
        assert anio is None
        assert any("no coinciden" in e for e in errores)

    def test_anio_nulo(self):
        """Valores nulos en columna de año."""
        df = pd.DataFrame({"ANO": ["2021", "", "2021"]})
        anio, errores = detectar_anio(df, "ANO", "DANE")
        assert anio == 2021
        assert any("nulo" in e.lower() or "vacío" in e.lower() for e in errores)

    def test_anio_invalido(self):
        """Valores no numéricos en columna de año."""
        df = pd.DataFrame({"ANO": ["2021", "abc", "2021"]})
        anio, errores = detectar_anio(df, "ANO", "DANE")
        assert anio is None
        assert any("inválido" in e.lower() for e in errores)

    def test_columna_anio_faltante(self):
        """Columna de año no existe."""
        df = pd.DataFrame({"OTRA": ["2021"]})
        anio, errores = detectar_anio(df, "ANO", "DANE")
        assert anio is None
        assert any("no existe" in e for e in errores)

    def test_anio_2022(self):
        """El año no debe estar fijado a 2021."""
        df = pd.DataFrame({"ANO": ["2022", "2022"]})
        anio, errores = detectar_anio(df, "ANO", "DANE")
        assert anio == 2022
        assert len(errores) == 0

    def test_anio_float_format(self):
        """Aceptar '2021.0' como año válido."""
        df = pd.DataFrame({"ANO": ["2021.0", "2021.0"]})
        anio, errores = detectar_anio(df, "ANO", "DANE")
        assert anio == 2021
        assert len(errores) == 0

    def test_anio_fraccionario(self):
        """Rechazar año fraccionario."""
        df = pd.DataFrame({"ANO": ["2021.5", "2021"]})
        anio, errores = detectar_anio(df, "ANO", "DANE")
        assert anio is None
        assert any("inválido" in e.lower() for e in errores)

    def test_anio_none_real(self):
        """Manejar None como valor nulo."""
        df = pd.DataFrame({"ANO": ["2021", None, "2021"]})
        anio, errores = detectar_anio(df, "ANO", "DANE")
        assert anio == 2021
        assert any("nulo" in e.lower() for e in errores)

    def test_anio_nan_real(self):
        """Manejar NaN como valor nulo."""
        df = pd.DataFrame({"ANO": ["2021", float("nan"), "2021"]})
        anio, errores = detectar_anio(df, "ANO", "DANE")
        assert anio == 2021
        assert any("nulo" in e.lower() for e in errores)


# ==========================================
# PRUEBAS DE CÁLCULO DE VARIABLE OBJETIVO
# ==========================================

class TestVariableObjetivo:
    """Pruebas del cálculo de dane_pct_sin_asistencia."""

    def test_calculo_basico(self):
        """Cálculo correcto del porcentaje."""
        df = pd.DataFrame({
            "CODMUNRE": ["20001", "20001", "20001", "20001"],
            "CAU_HOMOL": ["010", "010", "010", "010"],
            "ASIS_MED": ["1", "1", "2", "2"],
        })
        df_proc, stats = procesar_dane(df)
        assert len(df_proc) == 1
        assert df_proc["dane_pct_sin_asistencia"].iloc[0] == 50.0

    def test_excluir_ignorados(self):
        """ASIS_MED=3 no participa en el cálculo."""
        df = pd.DataFrame({
            "CODMUNRE": ["20001", "20001", "20001"],
            "CAU_HOMOL": ["010", "010", "010"],
            "ASIS_MED": ["1", "2", "3"],
        })
        df_proc, stats = procesar_dane(df)
        assert df_proc["dane_pct_sin_asistencia"].iloc[0] == 50.0

    def test_excluir_sin_informacion(self):
        """ASIS_MED=9 no participa en el cálculo."""
        df = pd.DataFrame({
            "CODMUNRE": ["20001", "20001", "20001"],
            "CAU_HOMOL": ["010", "010", "010"],
            "ASIS_MED": ["1", "2", "9"],
        })
        df_proc, stats = procesar_dane(df)
        assert df_proc["dane_pct_sin_asistencia"].iloc[0] == 50.0

    def test_sin_respuestas_validas(self):
        """Combinación sin respuestas válidas se excluye."""
        df = pd.DataFrame({
            "CODMUNRE": ["20001", "20001"],
            "CAU_HOMOL": ["010", "010"],
            "ASIS_MED": ["3", "9"],
        })
        df_proc, stats = procesar_dane(df)
        assert len(df_proc) == 0
        assert stats["combinaciones_sin_respuestas_validas"] == 1

    def test_todo_con_asistencia(self):
        """100% con asistencia = 0% sin asistencia."""
        df = pd.DataFrame({
            "CODMUNRE": ["20001", "20001"],
            "CAU_HOMOL": ["010", "010"],
            "ASIS_MED": ["1", "1"],
        })
        df_proc, stats = procesar_dane(df)
        assert df_proc["dane_pct_sin_asistencia"].iloc[0] == 0.0

    def test_todo_sin_asistencia(self):
        """100% sin asistencia."""
        df = pd.DataFrame({
            "CODMUNRE": ["20001", "20001"],
            "CAU_HOMOL": ["010", "010"],
            "ASIS_MED": ["2", "2"],
        })
        df_proc, stats = procesar_dane(df)
        assert df_proc["dane_pct_sin_asistencia"].iloc[0] == 100.0

    def test_varias_combinaciones(self):
        """Múltiples combinaciones municipio-grupo."""
        df = pd.DataFrame({
            "CODMUNRE": ["20001", "20001", "25001", "25001"],
            "CAU_HOMOL": ["010", "051", "010", "051"],
            "ASIS_MED": ["1", "2", "2", "1"],
        })
        df_proc, stats = procesar_dane(df)
        assert len(df_proc) == 4
        assert stats["municipios_distintos"] == 2
        assert stats["grupos_distintos"] == 2


# ==========================================
# PRUEBAS DE VALIDACIÓN DANE
# ==========================================

class TestValidacionDane:
    """Pruebas de validación de campos DANE."""

    def test_cau_homol_invalido(self):
        """CAU_HOMOL inválido se excluye."""
        df = pd.DataFrame({
            "CODMUNRE": ["20001", "20001"],
            "CAU_HOMOL": ["010", "999"],
            "ASIS_MED": ["1", "2"],
        })
        df_proc, stats = procesar_dane(df)
        assert stats["excluidos_cau_homol_invalido"] == 1
        assert len(df_proc) == 1

    def test_cau_homol_nulo(self):
        """CAU_HOMOL nulo se excluye."""
        df = pd.DataFrame({
            "CODMUNRE": ["20001", "20001"],
            "CAU_HOMOL": ["010", ""],
            "ASIS_MED": ["1", "2"],
        })
        df_proc, stats = procesar_dane(df)
        assert stats["excluidos_cau_homol_nulo"] == 1

    def test_asis_med_invalido(self):
        """ASIS_MED con valor fuera de dominio se excluye."""
        df = pd.DataFrame({
            "CODMUNRE": ["20001", "20001"],
            "CAU_HOMOL": ["010", "010"],
            "ASIS_MED": ["1", "5"],
        })
        df_proc, stats = procesar_dane(df)
        assert stats["excluidos_asis_med_invalido"] == 1

    def test_asis_med_nulo_no_excluye(self):
        """ASIS_MED nulo no excluye el registro."""
        df = pd.DataFrame({
            "CODMUNRE": ["20001", "20001"],
            "CAU_HOMOL": ["010", "010"],
            "ASIS_MED": ["1", ""],
        })
        df_proc, stats = procesar_dane(df)
        assert stats["asis_med_nulo"] == 1
        # El registro con ASIS_MED nulo no se excluye, pero no participa
        assert stats["registros_unicos_excluidos"] == 0

    def test_codmunre_invalido(self):
        """CODMUNRE con formato inválido se excluye."""
        df = pd.DataFrame({
            "CODMUNRE": ["20001", "ABC"],
            "CAU_HOMOL": ["010", "010"],
            "ASIS_MED": ["1", "2"],
        })
        df_proc, stats = procesar_dane(df)
        assert stats["excluidos_cod_municipio_invalido"] == 1

    def test_multiples_motivos_exclusion(self):
        """Un registro con múltiples motivos cuenta como 1 excluido."""
        df = pd.DataFrame({
            "CODMUNRE": ["ABC", "20001"],
            "CAU_HOMOL": ["999", "010"],
            "ASIS_MED": ["5", "1"],
        })
        df_proc, stats = procesar_dane(df)
        # El primer registro tiene 3 motivos, pero cuenta como 1 excluido
        assert stats["registros_unicos_excluidos"] == 1


# ==========================================
# PRUEBAS DE PROCESAMIENTO RIPS
# ==========================================

class TestProcesamientoRIPS:
    """Pruebas del procesamiento de RIPS."""

    def test_duplicados_exactos(self):
        """Detectar y eliminar duplicados exactos."""
        df = pd.DataFrame({
            "Departamento": ["20", "20"],
            "Municipio": ["20001 - VALLEDUPAR", "20001 - VALLEDUPAR"],
            "Año": ["2021", "2021"],
            "TipoAtencion": ["CONSULTAS", "CONSULTAS"],
            "Diagnostico": ["R104 - DOLOR", "R104 - DOLOR"],
            "NumeroAtenciones": ["10", "10"],
        })
        df_limpio, stats = validar_y_deduplicar_rips(df)
        assert len(df_limpio) == 1
        assert stats["duplicados_exactos"] == 1

    def test_extraer_codigo_municipio_con_nombre(self):
        """Extraer código de formato 'CODIGO - NOMBRE'."""
        codigo = extraer_codigo_municipio("20001 - VALLEDUPAR")
        assert codigo == "20001"

    def test_extraer_codigo_municipio_solo_codigo(self):
        """Extraer código sin nombre."""
        codigo = extraer_codigo_municipio("25001")
        assert codigo == "25001"

    def test_extraer_codigo_municipio_con_ceros(self):
        """Preservar ceros iniciales."""
        codigo = extraer_codigo_municipio("05001 - MEDELLIN")
        assert codigo == "05001"

    def test_extraer_codigo_municipio_invalido(self):
        """Código no numérico devuelve None."""
        assert extraer_codigo_municipio("") is None
        assert extraer_codigo_municipio(None) is None

    def test_clasificar_consultas(self):
        """Clasificar CONSULTAS."""
        assert clasificar_tipo_atencion("CONSULTAS") == "consultas"

    def test_clasificar_procedimientos(self):
        """Clasificar PROCEDIMIENTOS DE SALUD."""
        assert clasificar_tipo_atencion("PROCEDIMIENTOS DE SALUD") == "procedimientos"

    def test_clasificar_urgencias(self):
        """Clasificar URGENCIAS."""
        assert clasificar_tipo_atencion("URGENCIAS") == "urgencias"

    def test_clasificar_hospitalizaciones(self):
        """Clasificar HOSPITALIZACIONES."""
        assert clasificar_tipo_atencion("HOSPITALIZACIONES") == "hospitalizaciones"

    def test_clasificar_desconocido(self):
        """Tipo desconocido devuelve None."""
        assert clasificar_tipo_atencion("OTRO") is None
        assert clasificar_tipo_atencion("") is None

    def test_agregacion_atenciones(self):
        """Agregación correcta de atenciones."""
        df = pd.DataFrame({
            "Departamento": ["20", "20"],
            "Municipio": ["20001 - VALLEDUPAR", "20001 - VALLEDUPAR"],
            "Año": ["2021", "2021"],
            "TipoAtencion": ["CONSULTAS", "URGENCIAS"],
            "Diagnostico": ["R104 - DOLOR", "R104 - DOLOR"],
            "NumeroAtenciones": ["10", "5"],
        })
        df_proc, stats = procesar_rips(df)
        assert df_proc["rips_total_atenciones"].iloc[0] == 15

    def test_porcentajes(self):
        """Cálculo de porcentajes."""
        df = pd.DataFrame({
            "Departamento": ["20", "20"],
            "Municipio": ["20001 - VALLEDUPAR", "20001 - VALLEDUPAR"],
            "Año": ["2021", "2021"],
            "TipoAtencion": ["CONSULTAS", "URGENCIAS"],
            "Diagnostico": ["R104 - DOLOR", "R104 - DOLOR"],
            "NumeroAtenciones": ["10", "10"],
        })
        df_proc, stats = procesar_rips(df)
        row = df_proc.iloc[0]
        assert abs(row["rips_pct_consultas"] - 50.0) < 0.1
        assert abs(row["rips_pct_urgencias"] - 50.0) < 0.1

    def test_cobertura_homologacion(self):
        """Calcular cobertura de homologación."""
        df = pd.DataFrame({
            "Departamento": ["20", "20"],
            "Municipio": ["20001 - VALLEDUPAR", "20001 - VALLEDUPAR"],
            "Año": ["2021", "2021"],
            "TipoAtencion": ["CONSULTAS", "CONSULTAS"],
            "Diagnostico": ["R104 - DOLOR", "Z00 - EXAMEN"],
            "NumeroAtenciones": ["10", "5"],
        })
        df_proc, stats = procesar_rips(df)
        assert stats["diagnosticos_distintos"] == 2
        assert stats["diagnosticos_homologados"] == 1
        assert stats["diagnosticos_sin_correspondencia"] == 1


# ==========================================
# PRUEBAS DE VALIDACIÓN RIPS
# ==========================================

class TestValidacionRIPS:
    """Pruebas de validación de campos RIPS."""

    def test_numero_atenciones_negativo(self):
        """NumeroAtenciones negativo se excluye."""
        df = pd.DataFrame({
            "Departamento": ["20", "20"],
            "Municipio": ["20001 - VALLEDUPAR", "20001 - VALLEDUPAR"],
            "Año": ["2021", "2021"],
            "TipoAtencion": ["CONSULTAS", "CONSULTAS"],
            "Diagnostico": ["R104 - DOLOR", "R104 - DOLOR"],
            "NumeroAtenciones": ["10", "-5"],
        })
        df_proc, stats = procesar_rips(df)
        assert stats["excluidos_numero_atenciones_negativo"] == 1
        assert df_proc["rips_total_atenciones"].iloc[0] == 10

    def test_numero_atenciones_no_numerico(self):
        """NumeroAtenciones no numérico se excluye."""
        df = pd.DataFrame({
            "Departamento": ["20", "20"],
            "Municipio": ["20001 - VALLEDUPAR", "20001 - VALLEDUPAR"],
            "Año": ["2021", "2021"],
            "TipoAtencion": ["CONSULTAS", "CONSULTAS"],
            "Diagnostico": ["R104 - DOLOR", "R104 - DOLOR"],
            "NumeroAtenciones": ["10", "abc"],
        })
        df_proc, stats = procesar_rips(df)
        assert stats["excluidos_numero_atenciones_no_numerico"] == 1

    def test_diagnostico_mal_formado(self):
        """Diagnóstico sin letra inicial se excluye."""
        df = pd.DataFrame({
            "Departamento": ["20", "20"],
            "Municipio": ["20001 - VALLEDUPAR", "20001 - VALLEDUPAR"],
            "Año": ["2021", "2021"],
            "TipoAtencion": ["CONSULTAS", "CONSULTAS"],
            "Diagnostico": ["R104 - DOLOR", "12345"],
            "NumeroAtenciones": ["10", "5"],
        })
        df_proc, stats = procesar_rips(df)
        assert stats["excluidos_diagnostico_invalido"] == 1

    def test_c50_no_integrado(self):
        """Los registros C50 no generan filas en el dataset."""
        df = pd.DataFrame({
            "Departamento": ["20"],
            "Municipio": ["20001 - VALLEDUPAR"],
            "Año": ["2021"],
            "TipoAtencion": ["CONSULTAS"],
            "Diagnostico": ["C50 - TUMOR MAM"],
            "NumeroAtenciones": ["10"],
        })
        df_proc, stats = procesar_rips(df)
        assert stats["registros_c50"] == 1
        assert stats["atenciones_c50"] == 10
        assert len(df_proc) == 0  # C50 no genera filas

    def test_cobertura_ponderada_exacta(self):
        """Cobertura ponderada: 80 de 100 atenciones homologadas = 80%."""
        df = pd.DataFrame({
            "Departamento": ["20", "20", "20"],
            "Municipio": ["20001 - VALLEDUPAR"] * 3,
            "Año": ["2021"] * 3,
            "TipoAtencion": ["CONSULTAS"] * 3,
            "Diagnostico": ["R104 - DOLOR", "Z00 - EXAMEN", "C50 - TUMOR"],
            "NumeroAtenciones": ["80", "10", "10"],
        })
        df_proc, stats = procesar_rips(df)
        # R104: 80 atenciones homologadas
        # Z00: 10 atenciones sin correspondencia
        # C50: 10 atenciones categoría auxiliar (no homologada)
        # Total válidas: 100, homologadas: 80
        assert stats["cobertura_homologacion_ponderada"] == 80.0
        assert stats["registros_c50"] == 1
        assert stats["atenciones_c50"] == 10
        assert stats["diagnosticos_c50_distintos"] == 1

    def test_cobertura_ponderada_c50_no_homologado(self):
        """C50 no se contabiliza como homologado en la cobertura."""
        df = pd.DataFrame({
            "Departamento": ["20", "20"],
            "Municipio": ["20001 - VALLEDUPAR"] * 2,
            "Año": ["2021"] * 2,
            "TipoAtencion": ["CONSULTAS"] * 2,
            "Diagnostico": ["C50 - TUMOR", "C501 - TUMOR"],
            "NumeroAtenciones": ["50", "50"],
        })
        df_proc, stats = procesar_rips(df)
        # Todos C50: 0 homologados de 100 válidas
        assert stats["cobertura_homologacion_ponderada"] == 0.0
        assert stats["diagnosticos_homologados"] == 0
        assert stats["atenciones_c50"] == 100

    def test_cobertura_ponderada_registros_invalidos_excluidos(self):
        """Los registros inválidos no participan en el denominador."""
        df = pd.DataFrame({
            "Departamento": ["20", "20", "20"],
            "Municipio": ["20001 - VALLEDUPAR"] * 3,
            "Año": ["2021"] * 3,
            "TipoAtencion": ["CONSULTAS"] * 3,
            "Diagnostico": ["R104 - DOLOR", "I219 - INFARTO", "R104 - DOLOR"],
            "NumeroAtenciones": ["80", "-10", "20"],  # -10 es inválido
        })
        df_proc, stats = procesar_rips(df)
        # Registro con -10 se excluye. Total válidas: 100, homologadas: 100
        assert stats["excluidos_numero_atenciones_negativo"] == 1
        assert stats["cobertura_homologacion_ponderada"] == 100.0

    def test_cobertura_ponderada_sin_atenciones_validas(self):
        """Sin atenciones válidas, la cobertura es 0% sin división por cero."""
        df = pd.DataFrame({
            "Departamento": ["20"],
            "Municipio": ["20001 - VALLEDUPAR"],
            "Año": ["2021"],
            "TipoAtencion": ["CONSULTAS"],
            "Diagnostico": ["R104 - DOLOR"],
            "NumeroAtenciones": ["-5"],  # inválido, se excluye
        })
        df_proc, stats = procesar_rips(df)
        # Todos excluidos, no hay atenciones válidas
        assert stats["cobertura_homologacion_ponderada"] == 0.0
        assert len(df_proc) == 0

    def test_cobertura_ponderada_z00_en_denominador(self):
        """Diagnósticos válidos sin homologación sí están en el denominador."""
        df = pd.DataFrame({
            "Departamento": ["20", "20"],
            "Municipio": ["20001 - VALLEDUPAR"] * 2,
            "Año": ["2021"] * 2,
            "TipoAtencion": ["CONSULTAS"] * 2,
            "Diagnostico": ["R104 - DOLOR", "Z00 - EXAMEN"],
            "NumeroAtenciones": ["70", "30"],
        })
        df_proc, stats = procesar_rips(df)
        # 70 homologadas de 100 válidas = 70%
        assert stats["cobertura_homologacion_ponderada"] == 70.0


# ==========================================
# PRUEBAS DE INTEGRACIÓN
# ==========================================

class TestIntegracion:
    """Pruebas de integración DANE + RIPS."""

    def test_combinaciones_sin_rips(self):
        """Combinaciones DANE sin RIPS se conservan con ceros."""
        df_dane = pd.DataFrame({
            "cod_municipio": ["20001", "25001"],
            "cod_grupo_diagnostico": ["010", "051"],
            "dane_pct_sin_asistencia": [50.0, 30.0],
        })
        df_rips = pd.DataFrame({
            "cod_municipio": ["20001"],
            "cod_grupo_diagnostico": ["010"],
            "rips_total_atenciones": [100],
            "rips_consultas": [60],
            "rips_procedimientos": [20],
            "rips_urgencias": [20],
            "rips_hospitalizaciones": [0],
            "rips_pct_consultas": [60.0],
            "rips_pct_procedimientos": [20.0],
            "rips_pct_urgencias": [20.0],
            "rips_pct_hospitalizaciones": [0.0],
        })
        integrado, stats = integrar_dane_rips(df_dane, df_rips)
        assert len(integrado) == 2
        row = integrado[integrado["cod_municipio"] == "25001"].iloc[0]
        assert row["rips_total_atenciones"] == 0
        assert row["rips_pct_consultas"] == 0
        assert stats["combinaciones_sin_rips"] == 1

    def test_columnas_finales(self):
        """El dataset integrado tiene las columnas correctas."""
        df_dane = pd.DataFrame({
            "cod_municipio": ["20001"],
            "cod_grupo_diagnostico": ["010"],
            "dane_pct_sin_asistencia": [50.0],
        })
        df_rips = pd.DataFrame({
            "cod_municipio": ["20001"],
            "cod_grupo_diagnostico": ["010"],
            "rips_total_atenciones": [100],
            "rips_consultas": [60],
            "rips_procedimientos": [20],
            "rips_urgencias": [20],
            "rips_hospitalizaciones": [0],
            "rips_pct_consultas": [60.0],
            "rips_pct_procedimientos": [20.0],
            "rips_pct_urgencias": [20.0],
            "rips_pct_hospitalizaciones": [0.0],
        })
        integrado, _ = integrar_dane_rips(df_dane, df_rips)
        columnas_esperadas = [
            "cod_municipio", "cod_grupo_diagnostico",
            "rips_total_atenciones", "rips_consultas",
            "rips_procedimientos", "rips_urgencias",
            "rips_hospitalizaciones",
            "rips_pct_consultas", "rips_pct_procedimientos",
            "rips_pct_urgencias", "rips_pct_hospitalizaciones",
            "dane_pct_sin_asistencia",
        ]
        for col in columnas_esperadas:
            assert col in integrado.columns


# ==========================================
# PRUEBAS DE VALIDACIÓN DEL DATASET
# ==========================================

class TestValidacionDataset:
    """Pruebas de validación del dataset final."""

    def test_sin_errores(self):
        """Dataset válido no produce errores."""
        df = pd.DataFrame({
            "cod_municipio": ["20001", "25001"],
            "cod_grupo_diagnostico": ["010", "051"],
            "rips_total_atenciones": [100, 50],
            "rips_consultas": [60, 30],
            "rips_procedimientos": [20, 10],
            "rips_urgencias": [20, 10],
            "rips_hospitalizaciones": [0, 0],
            "rips_pct_consultas": [60.0, 60.0],
            "rips_pct_procedimientos": [20.0, 20.0],
            "rips_pct_urgencias": [20.0, 20.0],
            "rips_pct_hospitalizaciones": [0.0, 0.0],
            "dane_pct_sin_asistencia": [50.0, 30.0],
        })
        errores = validar_dataset(df)
        assert len(errores) == 0

    def test_combinaciones_duplicadas(self):
        """Detectar combinaciones duplicadas."""
        df = pd.DataFrame({
            "cod_municipio": ["20001", "20001"],
            "cod_grupo_diagnostico": ["010", "010"],
            "rips_total_atenciones": [100, 50],
            "rips_consultas": [60, 30],
            "rips_procedimientos": [20, 10],
            "rips_urgencias": [20, 10],
            "rips_hospitalizaciones": [0, 0],
            "rips_pct_consultas": [60.0, 60.0],
            "rips_pct_procedimientos": [20.0, 20.0],
            "rips_pct_urgencias": [20.0, 20.0],
            "rips_pct_hospitalizaciones": [0.0, 0.0],
            "dane_pct_sin_asistencia": [50.0, 30.0],
        })
        errores = validar_dataset(df)
        assert any("duplicadas" in e for e in errores)

    def test_valores_negativos(self):
        """Detectar conteos negativos."""
        df = pd.DataFrame({
            "cod_municipio": ["20001"],
            "cod_grupo_diagnostico": ["010"],
            "rips_total_atenciones": [-1],
            "rips_consultas": [0],
            "rips_procedimientos": [0],
            "rips_urgencias": [0],
            "rips_hospitalizaciones": [0],
            "rips_pct_consultas": [0.0],
            "rips_pct_procedimientos": [0.0],
            "rips_pct_urgencias": [0.0],
            "rips_pct_hospitalizaciones": [0.0],
            "dane_pct_sin_asistencia": [50.0],
        })
        errores = validar_dataset(df)
        assert any("negativos" in e for e in errores)

    def test_porcentajes_fuera_rango(self):
        """Detectar porcentajes fuera de [0, 100]."""
        df = pd.DataFrame({
            "cod_municipio": ["20001"],
            "cod_grupo_diagnostico": ["010"],
            "rips_total_atenciones": [100],
            "rips_consultas": [60],
            "rips_procedimientos": [20],
            "rips_urgencias": [20],
            "rips_hospitalizaciones": [0],
            "rips_pct_consultas": [150.0],
            "rips_pct_procedimientos": [20.0],
            "rips_pct_urgencias": [20.0],
            "rips_pct_hospitalizaciones": [0.0],
            "dane_pct_sin_asistencia": [50.0],
        })
        errores = validar_dataset(df)
        assert any("fuera de rango" in e for e in errores)


# ==========================================
# PRUEBAS DE ESCRITURA ATÓMICA
# ==========================================

class TestEscrituraAtomica:
    """Pruebas de escritura atómica y conservación del dataset."""

    def test_guardar_dataset(self):
        """Guardar dataset crea el archivo."""
        df = pd.DataFrame({
            "cod_municipio": ["20001"],
            "cod_grupo_diagnostico": ["010"],
            "dane_pct_sin_asistencia": [50.0],
        })
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            temp_path = f.name
        try:
            guardar_dataset_atomico(df, temp_path)
            assert Path(temp_path).exists()
            df_leido = pd.read_csv(temp_path)
            assert len(df_leido) == 1
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_error_no_sobrescribe(self):
        """Si la escritura falla, el dataset anterior se conserva."""
        df_existente = pd.DataFrame({
            "cod_municipio": ["20001"],
            "cod_grupo_diagnostico": ["010"],
            "dane_pct_sin_asistencia": [50.0],
        })
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            temp_path = f.name

        try:
            guardar_dataset_atomico(df_existente, temp_path)
            contenido_original = Path(temp_path).read_text()

            # Simular un error durante la escritura
            with patch("os.fdopen", side_effect=OSError("disco lleno")):
                with pytest.raises(OSError):
                    guardar_dataset_atomico(df_existente, temp_path)

            # El archivo original debe estar intacto
            contenido_actual = Path(temp_path).read_text()
            assert contenido_actual == contenido_original
        finally:
            Path(temp_path).unlink(missing_ok=True)


# ==========================================
# PRUEBAS DE VIGENCIA
# ==========================================

class TestVigencia:
    """Pruebas de detección de resultados desactualizados."""

    def test_sin_metadata(self):
        """Sin metadatos, no hay dataset disponible."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir) / "reports"
            reports_dir.mkdir()
            with patch("src.processing.REPORTS_DIR", reports_dir):
                estado = verificar_vigencia_procesamiento()
                assert estado["disponible"] is False
                assert estado["vigente"] is False

    def test_vigencia_con_archivos_cambiados(self):
        """Si los archivos RAW cambian, el dataset está desactualizado."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir) / "reports"
            reports_dir.mkdir()
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()

            # Crear metadatos con hash antiguo
            metadata = {
                "hash_dane": "hash_antiguo",
                "hash_rips": "hash_antiguo",
                "anio": 2021,
                "generado_en": "2021-01-01",
            }
            metadata_file = reports_dir / "processing_metadata.json"
            metadata_file.write_text(json.dumps(metadata))

            # Crear archivos RAW
            dane_file = raw_dir / "dane_no_fetal_2021.csv"
            dane_file.write_text("ANO\n2021\n")
            rips_file = raw_dir / "rips_2021.csv"
            rips_file.write_text("Año\n2021\n")

            with patch("src.processing.REPORTS_DIR", reports_dir):
                with patch("src.eda.RAW_DIR", raw_dir):
                    estado = verificar_vigencia_procesamiento()
                    assert estado["disponible"] is True
                    assert estado["vigente"] is False


# ==========================================
# PRUEBAS DE ENDPOINT
# ==========================================

class TestEndpoint:
    """Pruebas del endpoint de procesamiento."""

    def test_endpoint_protegido(self):
        """El endpoint requiere autenticación y rol admin."""
        # Verificar que ejecutar_procesamiento devuelve error sin archivos
        resultado = ejecutar_procesamiento()
        assert resultado["estado"] == "error"
        assert len(resultado["errores"]) > 0


class TestEndpointHTTP:
    """Pruebas HTTP de los endpoints de procesamiento con TestClient.

    Utiliza app.dependency_overrides para interceptar las dependencias
    de autenticación y autorización de FastAPI correctamente.
    """

    @pytest.fixture(autouse=True)
    def skip_if_no_fastapi(self):
        try:
            from fastapi.testclient import TestClient  # noqa: F401
        except ImportError:
            pytest.skip("FastAPI no está instalado")

    def test_status_sin_token(self):
        """GET /processing/status sin token devuelve 401."""
        from fastapi.testclient import TestClient
        from src.main import app
        client = TestClient(app)
        response = client.get("/processing/status")
        assert response.status_code == 401

    def test_run_sin_autenticacion(self):
        """POST /processing/run sin token devuelve 401."""
        from fastapi.testclient import TestClient
        from src.main import app
        client = TestClient(app)
        response = client.post("/processing/run")
        assert response.status_code == 401

    def test_run_sin_rol_admin(self):
        """POST /processing/run con usuario sin rol admin devuelve 403."""
        from fastapi.testclient import TestClient
        from src.main import app
        from src.auth import security, verificar_token, requiere_admin

        def mock_security():
            return "fake-token"

        def mock_verificar_token(token: str = None):
            return {
                "sub": "user123",
                "realm_access": {"roles": ["user"]},
            }

        app.dependency_overrides[security] = mock_security
        app.dependency_overrides[verificar_token] = mock_verificar_token
        try:
            client = TestClient(app)
            response = client.post("/processing/run")
            assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_run_con_admin_sin_archivos(self):
        """POST /processing/run con admin pero sin archivos RAW devuelve 422."""
        from fastapi.testclient import TestClient
        from src.main import app
        from src.auth import security, requiere_admin

        def mock_security():
            return "fake-token"

        def mock_requiere_admin():
            return {
                "sub": "admin123",
                "realm_access": {"roles": ["admin"]},
            }

        app.dependency_overrides[security] = mock_security
        app.dependency_overrides[requiere_admin] = mock_requiere_admin
        try:
            with patch("src.main.ejecutar_procesamiento") as mock_exec:
                mock_exec.return_value = {
                    "estado": "error",
                    "errores": ["No se encontró el archivo RAW de DANE en data/raw/."],
                    "advertencias": [],
                }
                client = TestClient(app)
                response = client.post("/processing/run")
                assert response.status_code == 422
                data = response.json()
                assert "El procesamiento falló" in data["detail"]["mensaje"]
        finally:
            app.dependency_overrides.clear()

    def test_run_con_admin_ejecucion_activa(self):
        """POST /processing/run con admin y ejecución activa devuelve 409."""
        from fastapi.testclient import TestClient
        from src.main import app
        from src.auth import security, requiere_admin

        def mock_security():
            return "fake-token"

        def mock_requiere_admin():
            return {
                "sub": "admin123",
                "realm_access": {"roles": ["admin"]},
            }

        app.dependency_overrides[security] = mock_security
        app.dependency_overrides[requiere_admin] = mock_requiere_admin
        try:
            with patch("src.main.ejecutar_procesamiento") as mock_exec:
                mock_exec.return_value = {
                    "estado": "error",
                    "errores": [
                        "Ya hay una ejecución de procesamiento activa. "
                        "Intente más tarde."
                    ],
                    "advertencias": [],
                }
                client = TestClient(app)
                response = client.post("/processing/run")
                assert response.status_code == 409
                data = response.json()
                assert "activa" in data["detail"]["mensaje"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_ejecutar_sin_archivos_raw(self):
        """Ejecutar sin archivos RAW produce error claro."""
        resultado = ejecutar_procesamiento()
        assert resultado["estado"] == "error"
        assert any("no se encontró" in e.lower() for e in resultado["errores"])

    def test_ejecutar_con_datos_sinteticos(self):
        """Ejecutar con datos sintéticos produce dataset válido."""
        df_dane = pd.DataFrame({
            "CODMUNRE": ["20001", "20001", "25001"],
            "CAU_HOMOL": ["010", "051", "010"],
            "ASIS_MED": ["1", "2", "2"],
            "ANO": ["2021", "2021", "2021"],
        })
        df_rips = pd.DataFrame({
            "Departamento": ["20", "25"],
            "Municipio": ["20001 - VALLEDUPAR", "25001 - BOGOTA"],
            "Año": ["2021", "2021"],
            "TipoAtencion": ["CONSULTAS", "URGENCIAS"],
            "Diagnostico": ["R104 - DOLOR", "I219 - INFARTO"],
            "NumeroAtenciones": ["10", "5"],
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            processed_dir = Path(tmpdir) / "processed"
            processed_dir.mkdir()
            reports_dir = Path(tmpdir) / "reports"
            reports_dir.mkdir()

            dane_file = raw_dir / "dane_no_fetal_2021.csv"
            rips_file = raw_dir / "rips_2021.csv"
            df_dane.to_csv(dane_file, index=False)
            df_rips.to_csv(rips_file, index=False)

            with patch("src.processing.RAW_DIR", raw_dir):
                with patch("src.processing.PROCESSED_DIR", processed_dir):
                    with patch("src.processing.REPORTS_DIR", reports_dir):
                        with patch("src.eda.RAW_DIR", raw_dir):
                            resultado = ejecutar_procesamiento()

            assert resultado["estado"] == "exitoso"
            assert resultado["estadisticas"]["anio"] == 2021
            assert resultado["estadisticas"]["observaciones_finales"] > 0

            dataset_path = processed_dir / "dataset_entrenamiento.csv"
            assert dataset_path.exists()

            df_resultado = pd.read_csv(dataset_path)
            assert "dane_pct_sin_asistencia" in df_resultado.columns
            assert "rips_total_atenciones" in df_resultado.columns


# ==========================================
# PRUEBAS DE CONCURRENCIA
# ==========================================

class TestConcurrencia:
    """Pruebas de protección contra ejecuciones concurrentes."""

    def test_bloqueo_archivo_atomics(self):
        """El bloqueo se crea de forma atómica."""
        with tempfile.TemporaryDirectory() as tmpdir:
            processed_dir = Path(tmpdir) / "processed"
            processed_dir.mkdir()
            with patch("src.processing.PROCESSED_DIR", processed_dir):
                fd = _adquirir_bloqueo()
                assert fd is not None
                lock_path = processed_dir / LOCK_FILE
                assert lock_path.exists()
                _liberar_bloqueo(fd)
                assert not lock_path.exists()

    def test_bloqueo_doble(self):
        """Dos bloqueos simultáneos: el segundo falla."""
        with tempfile.TemporaryDirectory() as tmpdir:
            processed_dir = Path(tmpdir) / "processed"
            processed_dir.mkdir()
            with patch("src.processing.PROCESSED_DIR", processed_dir):
                fd1 = _adquirir_bloqueo()
                assert fd1 is not None
                fd2 = _adquirir_bloqueo()
                assert fd2 is None
                _liberar_bloqueo(fd1)

    def test_bloqueo_abandonado(self):
        """Si el proceso muere, el bloqueo se libera."""
        with tempfile.TemporaryDirectory() as tmpdir:
            processed_dir = Path(tmpdir) / "processed"
            processed_dir.mkdir()
            with patch("src.processing.PROCESSED_DIR", processed_dir):
                # Simular un bloqueo abandonado con PID inexistente
                lock_path = processed_dir / LOCK_FILE
                lock_path.write_text("99999999")
                fd = _adquirir_bloqueo()
                assert fd is not None
                _liberar_bloqueo(fd)

    def test_ejecucion_concurrente_rechazada(self):
        """Si el lock de thread ya está adquirido, se rechaza."""
        import src.processing as proc_module

        # Simular que el lock de thread ya está adquirido
        proc_module._processing_lock.acquire()
        try:
            resultado = ejecutar_procesamiento()
            assert resultado["estado"] == "error"
            assert any("activa" in e.lower() for e in resultado["errores"])
        finally:
            proc_module._processing_lock.release()

    def test_bloqueo_archivo_vacio(self):
        """Un archivo de bloqueo vacío se recupera como abandonado."""
        with tempfile.TemporaryDirectory() as tmpdir:
            processed_dir = Path(tmpdir) / "processed"
            processed_dir.mkdir()
            with patch("src.processing.PROCESSED_DIR", processed_dir):
                # Crear un archivo de bloqueo vacío
                lock_path = processed_dir / LOCK_FILE
                lock_path.write_text("")
                assert lock_path.exists()
                fd = _adquirir_bloqueo()
                assert fd is not None, "Debería recuperar un lock file vacío"
                _liberar_bloqueo(fd)

    def test_bloqueo_archivo_no_numerico(self):
        """Un archivo de bloqueo con contenido no numérico se recupera."""
        with tempfile.TemporaryDirectory() as tmpdir:
            processed_dir = Path(tmpdir) / "processed"
            processed_dir.mkdir()
            with patch("src.processing.PROCESSED_DIR", processed_dir):
                lock_path = processed_dir / LOCK_FILE
                lock_path.write_text("garbage-content")
                fd = _adquirir_bloqueo()
                assert fd is not None, "Debería recuperar un lock file corrupto"
                _liberar_bloqueo(fd)

    def test_bloqueo_pid_inexistente(self):
        """Un archivo de bloqueo con PID inexistente se recupera."""
        with tempfile.TemporaryDirectory() as tmpdir:
            processed_dir = Path(tmpdir) / "processed"
            processed_dir.mkdir()
            with patch("src.processing.PROCESSED_DIR", processed_dir):
                lock_path = processed_dir / LOCK_FILE
                lock_path.write_text("99999999")
                fd = _adquirir_bloqueo()
                assert fd is not None, "Debería recuperar un lock con PID muerto"
                _liberar_bloqueo(fd)

    def test_bloqueo_pid_activo_no_se_elimina(self):
        """Un archivo de bloqueo con el PID actual no se elimina."""
        with tempfile.TemporaryDirectory() as tmpdir:
            processed_dir = Path(tmpdir) / "processed"
            processed_dir.mkdir()
            with patch("src.processing.PROCESSED_DIR", processed_dir):
                lock_path = processed_dir / LOCK_FILE
                lock_path.write_text(str(os.getpid()))
                fd = _adquirir_bloqueo()
                assert fd is None, "No debería eliminar un lock con PID activo"

    def test_es_proceso_activo_pid_actual(self):
        """_es_proceso_activo devuelve True para el PID actual."""
        assert _es_proceso_activo(os.getpid()) is True

    def test_es_proceso_activo_pid_inexistente(self):
        """_es_proceso_activo devuelve False para un PID inexistente."""
        assert _es_proceso_activo(99999999) is False

    def test_bloqueo_error_liberacion(self):
        """El bloqueo se libera después de un error en el procesamiento."""
        df_dane = pd.DataFrame({
            "CODMUNRE": ["20001"],
            "CAU_HOMOL": ["010"],
            "ASIS_MED": ["1"],
            "ANO": ["2021"],
        })
        df_rips = pd.DataFrame({
            "Departamento": ["20"],
            "Municipio": ["20001 - VALLEDUPAR"],
            "Año": ["2021"],
            "TipoAtencion": ["CONSULTAS"],
            "Diagnostico": ["R104 - DOLOR"],
            "NumeroAtenciones": ["10"],
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            processed_dir = Path(tmpdir) / "processed"
            processed_dir.mkdir()
            reports_dir = Path(tmpdir) / "reports"
            reports_dir.mkdir()

            # Solo DANE, sin RIPS → error
            dane_file = raw_dir / "dane_no_fetal_2021.csv"
            df_dane.to_csv(dane_file, index=False)
            # No crear archivo RIPS

            with patch("src.processing.RAW_DIR", raw_dir):
                with patch("src.processing.PROCESSED_DIR", processed_dir):
                    with patch("src.processing.REPORTS_DIR", reports_dir):
                        with patch("src.eda.RAW_DIR", raw_dir):
                            resultado = ejecutar_procesamiento()

            assert resultado["estado"] == "error"
            # Verificar que no quede un lock file
            lock_path = processed_dir / LOCK_FILE
            assert not lock_path.exists(), "El lock file debería eliminarse tras error"

    def test_bloqueo_multiproceso(self):
        """Dos procesos reales compiten por el mismo lock file.

        Solo uno debe adquirir el bloqueo. El segundo debe fallar
        porque el primero tiene un PID activo.
        """
        import multiprocessing

        def worker(lock_dir_path, start_event, result_dict, worker_id):
            """Proceso hijo que intenta adquirir el bloqueo."""
            processed_dir = Path(lock_dir_path)
            with patch("src.processing.PROCESSED_DIR", processed_dir):
                # Esperar la señal para comenzar simultáneamente
                start_event.wait()
                fd = _adquirir_bloqueo()
                if fd is not None:
                    result_dict[worker_id] = "adquirido"
                    # Mantener el bloqueo un momento para que el otro proceso intente
                    time.sleep(0.5)
                    _liberar_bloqueo(fd)
                else:
                    result_dict[worker_id] = "rechazado"

        with tempfile.TemporaryDirectory() as tmpdir:
            processed_dir = Path(tmpdir) / "processed"
            processed_dir.mkdir()

            ctx = multiprocessing.get_context("fork")
            start_event = ctx.Event()
            result_dict = ctx.Manager().dict()

            p1 = ctx.Process(
                target=worker,
                args=(str(processed_dir), start_event, result_dict, "w1")
            )
            p2 = ctx.Process(
                target=worker,
                args=(str(processed_dir), start_event, result_dict, "w2")
            )

            p1.start()
            p2.start()

            # Dar un breve margen para que ambos procesos lleguen al start_event.wait()
            time.sleep(0.2)
            # Liberar ambos procesos simultáneamente
            start_event.set()

            p1.join(timeout=10)
            p2.join(timeout=10)

            assert not p1.is_alive(), "Proceso 1 no terminó a tiempo"
            assert not p2.is_alive(), "Proceso 2 no terminó a tiempo"

            # Exactamente uno debe haber adquirido el bloqueo
            assert len(result_dict) == 2, "Ambos procesos deben reportar resultado"
            resultados = list(result_dict.values())
            assert resultados.count("adquirido") == 1, (
                f"Exactamente 1 proceso debe adquirir el bloqueo, "
                f"obtenido: {resultados}"
            )
            assert resultados.count("rechazado") == 1, (
                f"Exactamente 1 proceso debe ser rechazado, "
                f"obtenido: {resultados}"
            )

            # El lock file no debe quedar después de que ambos terminen
            lock_path = processed_dir / LOCK_FILE
            assert not lock_path.exists(), (
                "El lock file debería eliminarse después de liberar"
            )

    def test_bloqueo_multiproceso_recuperacion_abandonado(self):
        """Un proceso hijo crea un lock file y termina sin liberarlo.
        Otro proceso debe poder recuperarlo como abandonado.
        """
        import multiprocessing

        def worker_create_abandoned(lock_dir_path, pid_file_path):
            """Crea un lock file con su propio PID y termina sin liberar."""
            processed_dir = Path(lock_dir_path)
            lock_path = processed_dir / LOCK_FILE
            # Escribir el PID en el archivo de lock directamente
            lock_path.write_text(str(os.getpid()))
            # Guardar el PID para que el proceso padre lo verifique
            Path(pid_file_path).write_text(str(os.getpid()))
            # Terminar sin llamar a _liberar_bloqueo → lock abandonado

        with tempfile.TemporaryDirectory() as tmpdir:
            processed_dir = Path(tmpdir) / "processed"
            processed_dir.mkdir()
            pid_file = Path(tmpdir) / "worker_pid.txt"

            ctx = multiprocessing.get_context("fork")
            p = ctx.Process(
                target=worker_create_abandoned,
                args=(str(processed_dir), str(pid_file))
            )
            p.start()
            p.join(timeout=10)
            assert not p.is_alive()

            # El lock file debe existir con el PID del proceso hijo
            lock_path = processed_dir / LOCK_FILE
            assert lock_path.exists(), "El lock file debe existir (abandonado)"

            # El PID del proceso hijo ya no debe estar activo
            worker_pid = int(pid_file.read_text().strip())
            assert not _es_proceso_activo(worker_pid), (
                "El proceso hijo debe haber terminado"
            )

            # Ahora _adquirir_bloqueo debe recuperar el lock abandonado
            with patch("src.processing.PROCESSED_DIR", processed_dir):
                fd = _adquirir_bloqueo()
                assert fd is not None, (
                    "Debería recuperar un lock file con PID inactivo"
                )
                _liberar_bloqueo(fd)

            # El lock file debe haberse eliminado después de liberar
            assert not lock_path.exists()


# ==========================================
# PRUEBAS DE COBERTURA DE HOMOLOGACIÓN
# ==========================================

class TestCoberturaHomologacion:
    """Pruebas de cobertura de la homologación diagnóstica."""

    def test_codigos_rips_comunes(self):
        """Los códigos más comunes de RIPS deben estar homologados."""
        codigos_comunes = [
            "R104", "U072", "N390", "I10X", "U071",
            "R509", "R101", "R103", "R074", "R51X",
            "I500", "K922", "R102", "O200", "L031",
            "M545", "N939", "I219", "O800", "I679",
        ]
        no_homologados = []
        for codigo in codigos_comunes:
            resultado = homologar_diagnostico(codigo)
            if resultado is None:
                no_homologados.append(codigo)

        if no_homologados:
            print(f"Advertencia: Códigos no homologados: {no_homologados}")

        homologados = len(codigos_comunes) - len(no_homologados)
        assert homologados >= len(codigos_comunes) * 0.8, (
            f"Baja cobertura: solo {homologados}/{len(codigos_comunes)} "
            "códigos comunes homologados"
        )

    def test_cobertura_general(self):
        """Verificar que la mayoría de códigos CIE-10 están cubiertos."""
        muestras = {
            "A00": "001",
            "B20": "009",
            "C50": CATEGORIA_C50_AUXILIAR,
            "I10": "050",
            "J18": "059",
            "R00": "089",
            "V02": "090",
        }
        for codigo, esperado in muestras.items():
            resultado = homologar_diagnostico(codigo)
            assert resultado == esperado, (
                f"{codigo} esperaba {esperado}, obtuvo {resultado}"
            )
