
import json
from pathlib import Path


# =====================================================
# RUTAS DEL PROYECTO
# =====================================================

BASE_DIR = Path(__file__).resolve().parent.parent

MODELOS_DIR = BASE_DIR / "models" / "reales"

METRICAS_PATH = MODELOS_DIR / "metricas.json"

EVALUACION_PATH = MODELOS_DIR / "evaluacion_final.json"


# =====================================================
# LEER ARCHIVOS JSON
# =====================================================

def leer_json(ruta):
    if not ruta.is_file():
        raise FileNotFoundError(
            f"No se encontró el archivo: {ruta.name}"
        )

    with ruta.open("r", encoding="utf-8") as archivo:
        return json.load(archivo)


# =====================================================
# CONSULTAR RESULTADOS DE AMBOS MODELOS
# =====================================================

def obtener_resultados_modelos():

    metricas = leer_json(METRICAS_PATH)
    evaluacion = leer_json(EVALUACION_PATH)

    if metricas["hash_dataset"] != evaluacion["hash_dataset"]:
        raise ValueError(
            "Las métricas y la evaluación no corresponden "
            "al mismo dataset."
        )

    resultados = metricas["metricas_validacion"]

    modelo_ganador = evaluacion["modelo_seleccionado"]

    if modelo_ganador not in resultados:
        raise ValueError(
            "El modelo seleccionado no aparece "
            "en las métricas de entrenamiento."
        )

    # Separar metricas de regresion y clasificacion por modelo
    modelo_rl = resultados["regresion_lineal"]
    modelo_rf = resultados["random_forest"]

    rl_regresion = {
        k: v for k, v in modelo_rl.items()
        if k != "metricas_clasificacion"
    }
    rf_regresion = {
        k: v for k, v in modelo_rf.items()
        if k != "metricas_clasificacion"
    }
    rl_clasif = modelo_rl.get("metricas_clasificacion")
    rf_clasif = modelo_rf.get("metricas_clasificacion")

    # Metricas de prueba del ganador
    metricas_prueba_raw = evaluacion.get("metricas_prueba", {})
    prueba_regresion = {
        k: v for k, v in metricas_prueba_raw.items()
        if k != "metricas_clasificacion"
    }
    prueba_clasif = metricas_prueba_raw.get("metricas_clasificacion")

    return {
        "tipo_datos": "reales",
        "variable_objetivo": metricas["variable_objetivo"],

        "modelos": {
            "regresion_lineal": {
                "nombre": "Regresión Lineal",
                "metricas_validacion": rl_regresion,
                "metricas_clasificacion_validacion": rl_clasif,
                "seleccionado": modelo_ganador == "regresion_lineal"
            },

            "random_forest": {
                "nombre": "Random Forest",
                "metricas_validacion": rf_regresion,
                "metricas_clasificacion_validacion": rf_clasif,
                "seleccionado": modelo_ganador == "random_forest"
            }
        },

        "modelo_seleccionado": modelo_ganador,

        "criterio_seleccion": evaluacion["criterio_seleccion"],

        "metricas_prueba": prueba_regresion,
        "metricas_clasificacion_prueba": prueba_clasif,

        "registros_entrenamiento": metricas["seleccion"]["registros_completos"],

        "municipios_disponibles": metricas["seleccion"]["municipios_disponibles"]
    }
