
import pandas as pd
from sklearn.model_selection import train_test_split


def dividir_datos(
    dataset: pd.DataFrame,
    entrenamiento: float = 70,
    validacion: float = 15,
    prueba: float = 15,
    random_state: int = 42
):
    """
    Divide el dataset por municipios en tres conjuntos:
    entrenamiento, validación y prueba.

    Los porcentajes son configurables.
    """

    # 1. Validar porcentajes
    porcentajes = (entrenamiento, validacion, prueba)

    if any(p <= 0 or p >= 100 for p in porcentajes):
        raise ValueError(
            "Cada porcentaje debe ser mayor que 0 y menor que 100."
        )

    if abs(sum(porcentajes) - 100) > 1e-8:
        raise ValueError(
            "Los porcentajes deben sumar exactamente 100."
        )

    # 2. Verificar columna de municipios
    if "cod_municipio" not in dataset.columns:
        raise ValueError(
            "El dataset debe contener la columna cod_municipio."
        )

    if dataset.empty:
        raise ValueError("El dataset está vacío.")

    if dataset["cod_municipio"].isna().any():
        raise ValueError(
            "Existen registros sin código de municipio."
        )

    # 3. Obtener municipios únicos
    municipios = dataset["cod_municipio"].unique()

    if len(municipios) < 3:
        raise ValueError(
            "Se necesitan al menos tres municipios para dividir."
        )

    # 4. Separar municipios de entrenamiento
    #    del conjunto temporal (validación + prueba)
    municipios_train, municipios_temp = train_test_split(
        municipios,
        train_size=entrenamiento / 100,
        random_state=random_state
    )

    # 5. Dividir el conjunto temporal
    proporcion_validacion = validacion / (validacion + prueba)

    municipios_val, municipios_test = train_test_split(
        municipios_temp,
        train_size=proporcion_validacion,
        random_state=random_state
    )

    # 6. Seleccionar filas por municipio
    datos_train = dataset[
        dataset["cod_municipio"].isin(municipios_train)
    ].copy()

    datos_val = dataset[
        dataset["cod_municipio"].isin(municipios_val)
    ].copy()

    datos_test = dataset[
        dataset["cod_municipio"].isin(municipios_test)
    ].copy()

    return datos_train, datos_val, datos_test
