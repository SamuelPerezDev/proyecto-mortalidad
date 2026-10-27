
import pandas as pd


def revisar_calidad(df, dataset):
    """Detecta posibles problemas sin modificar ni eliminar datos."""
    hallazgos = []

    duplicados = int(df.duplicated().sum())

    if duplicados > 0:
        hallazgos.append({
            "codigo": "DUPLICADOS",
            "nivel": "ADVERTENCIA",
            "cantidad": duplicados,
            "mensaje": "Se encontraron filas duplicadas. No se eliminaron."
        })

    if dataset == "RIPS" and "Diagnostico" in df.columns:
        espacios = df["Diagnostico"].astype(str).ne(
            df["Diagnostico"].astype(str).str.strip()
        )

        cantidad = int(espacios.sum())

        if cantidad > 0:
            hallazgos.append({
                "codigo": "ESPACIOS_DIAGNOSTICO",
                "nivel": "ADVERTENCIA",
                "cantidad": cantidad,
                "mensaje": (
                    "Hay diagnósticos con espacios al inicio o al final. "
                    "No se modificaron."
                )
            })

    return hallazgos
