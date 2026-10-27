
import json
from pathlib import Path

import pandas as pd

from src.schemas import DANE_FILE, RIPS_FILE
from src.validation import validar_dane, validar_rips


ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"
REPORTS_DIR = ROOT / "reports"


def leer_csv(ruta):
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


def guardar_reporte(nombre, reporte):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ruta = REPORTS_DIR / f"{nombre}_validation_report.json"

    with ruta.open("w", encoding="utf-8") as archivo:
        json.dump(
            reporte,
            archivo,
            ensure_ascii=False,
            indent=4
        )


def cargar_dataset(nombre, archivo, validador):
    ruta = PROCESSED_DIR / archivo

    if not ruta.exists():
        reporte = {
            "dataset": nombre,
            "estado": "RECHAZADO",
            "errores": [{
                "codigo": "FILE_NOT_FOUND",
                "mensaje": f"No se encontró el archivo: {ruta}"
            }],
            "advertencias": []
        }
        guardar_reporte(nombre.lower(), reporte)
        return None, reporte

    try:
        df = leer_csv(ruta)
        df_validado, reporte = validador(df)
        guardar_reporte(nombre.lower(), reporte)
        return df_validado, reporte

    except Exception as error:
        reporte = {
            "dataset": nombre,
            "estado": "RECHAZADO",
            "errores": [{
                "codigo": "ERROR_LECTURA",
                "mensaje": str(error)
            }],
            "advertencias": []
        }
        guardar_reporte(nombre.lower(), reporte)
        return None, reporte


def cargar_dane():
    return cargar_dataset("DANE", DANE_FILE, validar_dane)


def cargar_rips():
    return cargar_dataset("RIPS", RIPS_FILE, validar_rips)


if __name__ == "__main__":
    for funcion in (cargar_dane, cargar_rips):
        df, reporte = funcion()
        print(f"\n{reporte['dataset']}: {reporte['estado']}")

        if df is not None:
            print(f"Filas cargadas: {len(df)}")

        print(json.dumps(
            reporte,
            ensure_ascii=False,
            indent=2
        ))
