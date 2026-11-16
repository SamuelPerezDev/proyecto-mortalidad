import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
from sklearn.base import clone
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)
import numpy as np

from src.algoritmos import MODELOS
from src.preprocessing import (
    preparar_variables,
    crear_preprocesador
)


def calcular_metricas(y_real, y_predicho):
    return {
        "MAE": float(mean_absolute_error(y_real, y_predicho)),
        "RMSE": float(
            np.sqrt(mean_squared_error(y_real, y_predicho))
        ),
        "R2": float(r2_score(y_real, y_predicho))
    }


def entrenar_modelos(datos_train, datos_val):
    """
    Entrena los dos modelos y evalua
    su rendimiento en validacion.
    """

    X_train, y_train = preparar_variables(datos_train)
    X_val, y_val = preparar_variables(datos_val)

    if y_train.isna().any() or y_val.isna().any():
        raise ValueError(
            "La variable objetivo contiene valores faltantes."
        )

    resultados = {}
    modelos_entrenados = {}

    for nombre, modelo in MODELOS.items():

        pipeline = Pipeline([
            ("preprocesador", crear_preprocesador()),
            ("modelo", clone(modelo))
        ])

        pipeline.fit(X_train, y_train)

        predicciones = pipeline.predict(X_val)

        resultados[nombre] = calcular_metricas(
            y_val,
            predicciones
        )

        modelos_entrenados[nombre] = pipeline

    return resultados, modelos_entrenados

# ==========================================
# GUARDADO DE MODELOS ENTRENADOS
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent

MODELOS_DIR = BASE_DIR / "models" / "simulados"


def guardar_modelos(modelos, resultados, datos_train, datos_val, datos_test,hash_dataset):
    """
    Guarda modelos entrenados y metricas
    utilizando datos simulados.
    """

    MODELOS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    archivos_guardados = {}

    # Guardar cada modelo con su preprocesamiento
    for nombre, modelo in modelos.items():

        ruta = MODELOS_DIR / f"{nombre}.joblib"

        joblib.dump(modelo, ruta)

        archivos_guardados[nombre] = str(
            ruta.relative_to(BASE_DIR)
        ).replace("\\", "/")

    # Crear reporte de entrenamiento
    
    reporte = {
        "tipo_datos": "simulados",
        "variable_objetivo": "dane_pct_sin_asistencia",
        "fecha_entrenamiento": datetime.now(
            timezone.utc
        ).isoformat(),

        "division": {
            "entrenamiento": 70,
            "validacion": 15,
            "prueba": 15
        },

        "random_state": 42,

        "hash_dataset": hash_dataset,

        "metricas_validacion": resultados,

        "modelos": archivos_guardados,

        "municipios_division": {
            "entrenamiento": sorted(
                datos_train["cod_municipio"].astype(str).unique().tolist()
            ),
            "validacion": sorted(
                datos_val["cod_municipio"].astype(str).unique().tolist()
            ),
            "prueba": sorted(
                datos_test["cod_municipio"].astype(str).unique().tolist()
            )
        }
    }


    ruta_metricas = MODELOS_DIR / "metricas.json"

    with open(
        ruta_metricas,
        "w",
        encoding="utf-8"
    ) as archivo:
        json.dump(
            reporte,
            archivo,
            indent=4,
            ensure_ascii=False
        )

    return {
        "modelos": archivos_guardados,
        "metricas": str(
            ruta_metricas.relative_to(BASE_DIR)
        ).replace("\\", "/")
    }


def evaluar_modelo_final(
    modelo_entrenado,
    datos_test
):
    """
    Evalua un modelo ya entrenado utilizando
    exclusivamente el conjunto de prueba.
    """

    X_test, y_test = preparar_variables(datos_test)

    if y_test.isna().any():
        raise ValueError(
            "La variable objetivo contiene valores faltantes."
        )

    predicciones = modelo_entrenado.predict(X_test)

    metricas = calcular_metricas(
        y_test,
        predicciones
    )

    return metricas

def guardar_evaluacion_final(
    modelo_seleccionado,
    metricas_validacion,
    metricas_prueba,
    hash_dataset,
    municipios_prueba,
    registros_prueba
):
    """
    Guarda los resultados de la evaluacion
    final del modelo seleccionado en JSON.
    """

    # Crear directorio si no existe
    MODELOS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # Construir reporte
    reporte = {
        "tipo_datos": "simulados",
        "variable_objetivo": "dane_pct_sin_asistencia",
        "modelo_seleccionado": modelo_seleccionado,
        "criterio_seleccion": "Menor RMSE de validacion",
        "fecha_evaluacion": datetime.now(
            timezone.utc
        ).isoformat(),
        "hash_dataset": hash_dataset,
        "division": {
            "entrenamiento": 70,
            "validacion": 15,
            "prueba": 15
        },
        "metricas_validacion": metricas_validacion,
        "metricas_prueba": metricas_prueba,
        "municipios_prueba": municipios_prueba,
        "registros_prueba": registros_prueba
    }

    # Ruta del archivo JSON
    ruta_reporte = MODELOS_DIR / "evaluacion_final.json"

    # Guardar temporalmente para evitar archivos incompletos
    ruta_temporal = ruta_reporte.with_suffix(".json.tmp")

    with open(
        ruta_temporal,
        "w",
        encoding="utf-8"
    ) as archivo:
        json.dump(
            reporte,
            archivo,
            indent=4,
            ensure_ascii=False
        )

    # Reemplazar archivo anterior
    ruta_temporal.replace(ruta_reporte)

    # Devolver ruta relativa
    return str(
        ruta_reporte.relative_to(BASE_DIR)
    ).replace("\\", "/")

