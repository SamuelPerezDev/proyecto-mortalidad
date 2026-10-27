
import pandas as pd

from src.schemas import DANE_COLUMNS, RIPS_COLUMNS
from src.quality import revisar_calidad


def validar_dane(df):
    return validar_dataset(df, "DANE")


def validar_rips(df):
    return validar_dataset(df, "RIPS")


def validar_dataset(df, dataset):
    columnas_esperadas = (
        DANE_COLUMNS if dataset == "DANE" else RIPS_COLUMNS
    )

    errores = []
    advertencias = []
    df_validado = df.copy()

    faltantes = [
        col for col in columnas_esperadas
        if col not in df.columns
    ]
    extras = [
        col for col in df.columns
        if col not in columnas_esperadas
    ]

    if faltantes:
        errores.append({
            "codigo": "COLUMNAS_FALTANTES",
            "mensaje": f"Faltan columnas: {faltantes}"
        })

    if extras:
        errores.append({
            "codigo": "COLUMNAS_EXTRA",
            "mensaje": f"Hay columnas no esperadas: {extras}"
        })

    if errores:
        return None, crear_reporte(
            dataset, "RECHAZADO", errores, advertencias
        )

    # Estandariza el orden en memoria, sin eliminar columnas.
    df_validado = df_validado.loc[:, columnas_esperadas].copy()

    if dataset == "DANE":
        validar_valor(
            df_validado, "ANO", "2021", errores,
            "El año debe ser 2021."
        )
        validar_valor(
            df_validado, "TIPO_DEFUN", "2", errores,
            "Se esperaban defunciones no fetales (código 2)."
        )

        columnas_revisar = [
            col for col in DANE_COLUMNS
            if col not in ["ANO", "TIPO_DEFUN"]
        ]

        vacios = df_validado[columnas_revisar].apply(
            lambda columna: columna.astype(str).str.strip().eq("")
        ).sum()

        total_vacios = int(vacios.sum())

        if total_vacios:
            advertencias.append({
                "codigo": "VALORES_VACIOS",
                "cantidad": total_vacios,
                "mensaje": (
                    "Hay campos vacíos en DANE. "
                    "No se imputaron ni modificaron."
                )
            })

    else:
        for columna in RIPS_COLUMNS:
            vacios = df_validado[columna].astype(str).str.strip().eq("")
            cantidad = int(vacios.sum())

            if cantidad:
                errores.append({
                    "codigo": "VALORES_VACIOS",
                    "columna": columna,
                    "cantidad": cantidad,
                    "mensaje": f"La columna {columna} contiene vacíos."
                })

        validar_valor(
            df_validado, "Año", "2021", errores,
            "El año debe ser 2021."
        )

        conteos = pd.to_numeric(
            df_validado["NumeroAtenciones"], errors="coerce"
        )

        invalidos = (
            conteos.isna()
            | (conteos <= 0)
            | (conteos % 1 != 0)
        )

        cantidad_invalidos = int(invalidos.sum())

        if cantidad_invalidos:
            errores.append({
                "codigo": "NUMERO_ATENCIONES_INVALIDO",
                "cantidad": cantidad_invalidos,
                "mensaje": (
                    "NumeroAtenciones debe ser un entero positivo."
                )
            })

    hallazgos = revisar_calidad(df_validado, dataset)
    advertencias.extend(hallazgos)

    estado = (
        "RECHAZADO" if errores
        else "CARGADO_CON_ADVERTENCIAS" if advertencias
        else "CARGADO"
    )

    return df_validado, crear_reporte(
        dataset, estado, errores, advertencias
    )


def validar_valor(df, columna, esperado, errores, mensaje):
    valores = df[columna].astype(str).str.strip()
    incorrectos = valores.ne(esperado)

    if incorrectos.any():
        errores.append({
            "codigo": "VALOR_INVALIDO",
            "columna": columna,
            "cantidad": int(incorrectos.sum()),
            "mensaje": mensaje
        })


def crear_reporte(dataset, estado, errores, advertencias):
    return {
        "dataset": dataset,
        "estado": estado,
        "errores": errores,
        "advertencias": advertencias
    }

