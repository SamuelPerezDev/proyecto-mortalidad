
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder


# Variable que queremos predecir
VARIABLE_OBJETIVO = "dane_pct_sin_asistencia"


# Variables predictoras de RIPS
VARIABLES_NUMERICAS = [
    "rips_total_atenciones",
    "rips_consultas",
    "rips_procedimientos",
    "rips_urgencias",
    "rips_hospitalizaciones",
    "rips_pct_consultas",
    "rips_pct_procedimientos",
    "rips_pct_urgencias",
    "rips_pct_hospitalizaciones"
]


# Variable categorica
VARIABLES_CATEGORICAS = [
    "cod_grupo_diagnostico"
]


def preparar_variables(dataset):
    """
    Separa las variables predictoras (X)
    de la variable objetivo (y).

    No modifica el dataset original.
    """

    columnas = (
        VARIABLES_NUMERICAS
        + VARIABLES_CATEGORICAS
        + [VARIABLE_OBJETIVO]
    )

    faltantes = [
        columna
        for columna in columnas
        if columna not in dataset.columns
    ]

    if faltantes:
        raise ValueError(
            f"Faltan columnas requeridas: {faltantes}"
        )

    X = dataset[
        VARIABLES_NUMERICAS + VARIABLES_CATEGORICAS
    ].copy()

    y = dataset[VARIABLE_OBJETIVO].copy()

    return X, y


def crear_preprocesador():
    """
    Crea el transformador de variables.

    Se ajustara exclusivamente con los
    datos de entrenamiento.
    """

    preprocesador = ColumnTransformer(
        transformers=[
            (
                "categoricas",
                OneHotEncoder(
                    handle_unknown="ignore"
                ),
                VARIABLES_CATEGORICAS
            ),
            (
                "numericas",
                "passthrough",
                VARIABLES_NUMERICAS
            )
        ]
    )

    return preprocesador
