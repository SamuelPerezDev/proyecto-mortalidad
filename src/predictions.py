
import json
from pathlib import Path

import joblib
import pandas as pd

from src.preprocessing import (
    VARIABLES_NUMERICAS,
    VARIABLES_CATEGORICAS,
    VARIABLE_OBJETIVO,
)


# ============================================================
# RUTAS DEL PROYECTO
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATASET_PATH = (
    BASE_DIR / "data" / "processed" / "dataset_entrenamiento.csv"
)

MODELOS_DIR = BASE_DIR / "models" / "reales"

EVALUACION_PATH = MODELOS_DIR / "evaluacion_final.json"

MODELOS_DISPONIBLES = {
    "regresion_lineal": "regresion_lineal.joblib",
    "random_forest": "random_forest.joblib",
}

VARIABLES_MODELO = (
    VARIABLES_NUMERICAS + VARIABLES_CATEGORICAS
)


# ============================================================
# 1. OBTENER EL MODELO GANADOR
# ============================================================

def obtener_modelo_seleccionado():
    """
    Consulta evaluacion_final.json para identificar
    el modelo seleccionado durante la evaluación.
    """

    if not EVALUACION_PATH.is_file():
        raise FileNotFoundError(
            "No existe evaluacion_final.json. "
            "Primero debes entrenar y evaluar los modelos."
        )

    with EVALUACION_PATH.open(
        "r", encoding="utf-8"
    ) as archivo:
        evaluacion = json.load(archivo)

    modelo = evaluacion.get("modelo_seleccionado")

    if modelo not in MODELOS_DISPONIBLES:
        raise ValueError(
            f"Modelo seleccionado no válido: {modelo}"
        )

    return modelo


# ============================================================
# 2. CARGAR AUTOMÁTICAMENTE EL MEJOR MODELO
# ============================================================

def cargar_modelo():
    """
    Carga el modelo ganador.

    No se utiliza un modelo fijo.
    La selección depende de evaluacion_final.json.
    """

    modelo_seleccionado = obtener_modelo_seleccionado()

    ruta_modelo = (
        MODELOS_DIR
        / MODELOS_DISPONIBLES[modelo_seleccionado]
    )

    if not ruta_modelo.is_file():
        raise FileNotFoundError(
            f"No existe el modelo entrenado: {ruta_modelo}"
        )

    return joblib.load(ruta_modelo)


# ============================================================
# 3. CARGAR DATASET PROCESADO
# ============================================================

def cargar_dataset():
    """
    Carga el dataset procesado sin modificar
    el archivo original.
    """

    if not DATASET_PATH.is_file():
        raise FileNotFoundError(
            "No existe dataset_entrenamiento.csv. "
            "Primero debes ejecutar el procesamiento."
        )

    dataset = pd.read_csv(
        DATASET_PATH,
        dtype={
            "cod_municipio": "string",
            "cod_grupo_diagnostico": "string",
        },
        keep_default_na=True,
    )

    columnas_requeridas = [
        "cod_municipio",
        "cod_grupo_diagnostico",
        VARIABLE_OBJETIVO,
        *VARIABLES_NUMERICAS,
    ]

    faltantes = [
        columna
        for columna in columnas_requeridas
        if columna not in dataset.columns
    ]

    if faltantes:
        raise ValueError(
            "Faltan columnas en el dataset: "
            + ", ".join(faltantes)
        )

    dataset["cod_municipio"] = (
        dataset["cod_municipio"]
        .astype("string")
        .str.strip()
        .str.zfill(5)
    )

    for columna in VARIABLES_NUMERICAS:
        dataset[columna] = pd.to_numeric(
            dataset[columna],
            errors="coerce",
        )

    dataset[VARIABLE_OBJETIVO] = pd.to_numeric(
        dataset[VARIABLE_OBJETIVO],
        errors="coerce",
    )

    return dataset


# ============================================================
# 4. GENERAR PREDICCIONES
# ============================================================

def generar_predicciones():
    """
    Genera predicciones utilizando exclusivamente
    el modelo seleccionado.

    Las filas incompletas no se modifican ni
    se eliminan del archivo original.

    Las predicciones no disponibles se mantienen
    como valores nulos.
    """

    dataset = cargar_dataset()

    modelo = cargar_modelo()

    resultado = dataset.copy()

    resultado["prediccion"] = float("nan")

    filas_validas = resultado[
        VARIABLES_MODELO
    ].notna().all(axis=1)

    if filas_validas.any():

        X = resultado.loc[
            filas_validas,
            VARIABLES_MODELO,
        ]

        predicciones = modelo.predict(X)

        resultado.loc[
            filas_validas,
            "prediccion",
        ] = predicciones

    return resultado


# ============================================================
# 5. LIMPIAR VALORES PARA RESPUESTAS JSON
# ============================================================

def limpiar_valor(valor):
    """
    Convierte valores de pandas y numpy
    a tipos compatibles con JSON.
    """

    if pd.isna(valor):
        return None

    if hasattr(valor, "item"):
        valor = valor.item()

    if isinstance(valor, float):
        return round(valor, 4)

    return valor


# ============================================================
# 6. LISTAR MUNICIPIOS DISPONIBLES
# ============================================================

def listar_municipios():
    """
    Devuelve los códigos de municipios presentes
    en el dataset procesado.
    """

    dataset = cargar_dataset()

    municipios = (
        dataset["cod_municipio"]
        .dropna()
        .unique()
        .tolist()
    )

    municipios = sorted(
        str(codigo)
        for codigo in municipios
        if str(codigo).strip()
    )

    return {
        "total_municipios": len(municipios),
        "municipios": municipios,
    }


# ============================================================
# 7. CONSULTAR RESULTADOS DE UN MUNICIPIO
# ============================================================

def consultar_municipio(codigo):
    """
    Consulta los resultados de un municipio,
    agrupados por código de diagnóstico.

    Incluye el valor observado y la predicción
    cuando estén disponibles.
    """

    codigo = str(codigo).strip().zfill(5)

    dataset = generar_predicciones()

    municipio = dataset[
        dataset["cod_municipio"] == codigo
    ].copy()

    if municipio.empty:
        return {
            "codigo_municipio": codigo,
            "encontrado": False,
            "modelo_utilizado": obtener_modelo_seleccionado(),
            "total_registros": 0,
            "resultados": [],
        }

    resultados = []

    for _, fila in municipio.iterrows():

        resultados.append({
            "cod_grupo_diagnostico": limpiar_valor(
                fila["cod_grupo_diagnostico"]
            ),
            "valor_observado": limpiar_valor(
                fila[VARIABLE_OBJETIVO]
            ),
            "valor_predicho": limpiar_valor(
                fila["prediccion"]
            ),
        })

    return {
        "codigo_municipio": codigo,
        "encontrado": True,
        "modelo_utilizado": obtener_modelo_seleccionado(),
        "total_registros": len(resultados),
        "resultados": resultados,
    }


# ============================================================
# 8. COMPARAR MUNICIPIOS
# ============================================================

def comparar_municipios(codigos):
    """
    Compara entre 2 y 10 municipios utilizando
    las predicciones del modelo ganador.
    """

    if not isinstance(codigos, (list, tuple)):
        raise ValueError(
            "Debes proporcionar una lista de municipios."
        )

    codigos = list(dict.fromkeys(
        str(codigo).strip().zfill(5)
        for codigo in codigos
    ))

    if len(codigos) < 2 or len(codigos) > 10:
        raise ValueError(
            "Debes seleccionar entre 2 y 10 municipios."
        )

    dataset = generar_predicciones()

    comparacion = []

    for codigo in codigos:

        municipio = dataset[
            dataset["cod_municipio"] == codigo
        ]

        resultados = []

        for _, fila in municipio.iterrows():

            resultados.append({
                "cod_grupo_diagnostico": limpiar_valor(
                    fila["cod_grupo_diagnostico"]
                ),
                "valor_observado": limpiar_valor(
                    fila[VARIABLE_OBJETIVO]
                ),
                "valor_predicho": limpiar_valor(
                    fila["prediccion"]
                ),
            })

        comparacion.append({
            "codigo_municipio": codigo,
            "encontrado": not municipio.empty,
            "total_registros": len(resultados),
            "resultados": resultados,
        })

    return {
        "modelo_utilizado": obtener_modelo_seleccionado(),
        "total_municipios": len(comparacion),
        "municipios": comparacion,
    }


# ============================================================
# 9. RESUMEN AGREGADO POR MUNICIPIO
# ============================================================

def resumen_municipio(codigo):
    """
    Calcula un resumen agregado de un municipio,
    promediando las predicciones y valores observados
    de todos sus diagnósticos.

    Devuelve un solo valor por municipio en lugar
    de resultados por diagnóstico.
    """

    codigo = str(codigo).strip().zfill(5)

    dataset = generar_predicciones()

    municipio = dataset[
        dataset["cod_municipio"] == codigo
    ].copy()

    if municipio.empty:
        return {
            "codigo_municipio": codigo,
            "encontrado": False,
            "modelo_utilizado": obtener_modelo_seleccionado(),
            "promedio_predicho": None,
            "promedio_observado": None,
            "total_diagnosticos": 0,
        }

    filas_validas = municipio.dropna(subset=["prediccion"])

    if filas_validas.empty:
        return {
            "codigo_municipio": codigo,
            "encontrado": True,
            "modelo_utilizado": obtener_modelo_seleccionado(),
            "promedio_predicho": None,
            "promedio_observado": None,
            "total_diagnosticos": 0,
        }

    promedio_predicho = filas_validas["prediccion"].mean()
    promedio_observado = filas_validas[VARIABLE_OBJETIVO].mean()
    total_diagnosticos = len(filas_validas)

    return {
        "codigo_municipio": codigo,
        "encontrado": True,
        "modelo_utilizado": obtener_modelo_seleccionado(),
        "promedio_predicho": round(float(promedio_predicho), 4),
        "promedio_observado": round(float(promedio_observado), 4),
        "total_diagnosticos": total_diagnosticos,
    }


# ============================================================
# 10. RESUMEN AGREGADO DE TODOS LOS MUNICIPIOS
# ============================================================

def resumen_todos_municipios():
    """
    Calcula un resumen agregado de todos los municipios,
    promediando las predicciones y valores observados
    por cada municipio.

    Devuelve una lista de municipios con sus valores
    agregados para cargar el mapa completo.
    """

    dataset = generar_predicciones()

    filas_validas = dataset.dropna(subset=["prediccion"])

    if filas_validas.empty:
        return {
            "total_municipios": 0,
            "modelo_utilizado": obtener_modelo_seleccionado(),
            "municipios": [],
        }

    agrupado = (
        filas_validas
        .groupby("cod_municipio")
        .agg(
            promedio_predicho=("prediccion", "mean"),
            promedio_observado=(VARIABLE_OBJETIVO, "mean"),
            total_diagnosticos=("prediccion", "count"),
        )
        .reset_index()
    )

    municipios = []

    for _, fila in agrupado.iterrows():
        municipios.append({
            "codigo_municipio": str(fila["cod_municipio"]),
            "promedio_predicho": round(float(fila["promedio_predicho"]), 4),
            "promedio_observado": round(float(fila["promedio_observado"]), 4),
            "total_diagnosticos": int(fila["total_diagnosticos"]),
        })

    return {
        "total_municipios": len(municipios),
        "modelo_utilizado": obtener_modelo_seleccionado(),
        "municipios": municipios,
    }


# ============================================================
# 11. COMPARAR RESUMEN AGREGADO DE MUNICIPIOS
# ============================================================

def comparar_resumen_municipios(codigos):
    """
    Compara entre 2 y 10 municipios utilizando
    los resúmenes agregados (promedio de todos
    los diagnósticos por municipio).
    """

    if not isinstance(codigos, (list, tuple)):
        raise ValueError(
            "Debes proporcionar una lista de municipios."
        )

    codigos = list(dict.fromkeys(
        str(codigo).strip().zfill(5)
        for codigo in codigos
    ))

    if len(codigos) < 2 or len(codigos) > 10:
        raise ValueError(
            "Debes seleccionar entre 2 y 10 municipios."
        )

    dataset = generar_predicciones()

    comparacion = []

    for codigo in codigos:

        municipio = dataset[
            dataset["cod_municipio"] == codigo
        ].copy()

        if municipio.empty:
            comparacion.append({
                "codigo_municipio": codigo,
                "encontrado": False,
                "promedio_predicho": None,
                "promedio_observado": None,
                "total_diagnosticos": 0,
            })
            continue

        filas_validas = municipio.dropna(subset=["prediccion"])

        if filas_validas.empty:
            comparacion.append({
                "codigo_municipio": codigo,
                "encontrado": True,
                "promedio_predicho": None,
                "promedio_observado": None,
                "total_diagnosticos": 0,
            })
            continue

        promedio_predicho = filas_validas["prediccion"].mean()
        promedio_observado = filas_validas[VARIABLE_OBJETIVO].mean()
        total_diagnosticos = len(filas_validas)

        comparacion.append({
            "codigo_municipio": codigo,
            "encontrado": True,
            "promedio_predicho": round(float(promedio_predicho), 4),
            "promedio_observado": round(float(promedio_observado), 4),
            "total_diagnosticos": total_diagnosticos,
        })

    return {
        "modelo_utilizado": obtener_modelo_seleccionado(),
        "total_municipios": len(comparacion),
        "municipios": comparacion,
    }
