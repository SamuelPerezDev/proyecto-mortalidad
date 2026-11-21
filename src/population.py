
import csv
import os
import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile


router = APIRouter(prefix="/datasets", tags=["Datasets"])

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

ARCHIVO_POBLACION = RAW_DIR / "poblacion_municipal_2021.csv"

COLUMNAS_REQUERIDAS = {
    "cod_municipio",
    "municipio",
    "departamento",
    "anio",
    "poblacion",
}

MAX_SIZE = 20 * 1024 * 1024


def validar_poblacion(ruta):
    errores = []
    advertencias = []
    codigos = set()
    registros = 0

    with ruta.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)

        if not lector.fieldnames:
            raise ValueError("El CSV no tiene encabezados")

        columnas = set(lector.fieldnames)
        faltantes = COLUMNAS_REQUERIDAS - columnas

        if faltantes:
            raise ValueError(
                f"Faltan columnas: {sorted(faltantes)}"
            )

        for numero, fila in enumerate(lector, start=2):
            registros += 1

            codigo = fila["cod_municipio"].strip()
            anio = fila["anio"].strip()
            poblacion = fila["poblacion"].strip()

            if not re.fullmatch(r"\d{5}", codigo):
                errores.append(
                    f"Fila {numero}: código municipal inválido"
                )

            if codigo in codigos:
                errores.append(
                    f"Fila {numero}: municipio duplicado {codigo}"
                )

            codigos.add(codigo)

            if anio != "2021":
                errores.append(
                    f"Fila {numero}: año diferente de 2021"
                )

            try:
                valor = int(poblacion)
                if valor <= 0:
                    errores.append(
                        f"Fila {numero}: población no positiva"
                    )
            except ValueError:
                errores.append(
                    f"Fila {numero}: población no es un entero"
                )

            if not fila["municipio"].strip():
                errores.append(
                    f"Fila {numero}: nombre de municipio vacío"
                )

            if not fila["departamento"].strip():
                errores.append(
                    f"Fila {numero}: departamento vacío"
                )

    if registros == 0:
        errores.append("El CSV no contiene registros")

    return {
        "valido": len(errores) == 0,
        "registros": registros,
        "errores": errores,
        "advertencias": advertencias,
    }


@router.post("/population/upload")
async def cargar_poblacion(
    file: UploadFile = File(...),
    
):
    """
    Carga población municipal de 2021.
    No procesa ni entrena modelos de Machine Learning.
    """

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Debe seleccionar un archivo CSV",
        )

    if ARCHIVO_POBLACION.exists():
        raise HTTPException(
            status_code=409,
            detail="Ya existe un dataset de población cargado",
        )

    temporal = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=RAW_DIR,
            delete=False,
        ) as archivo:
            temporal = Path(archivo.name)
            tamaño = 0

            while bloque := await file.read(1024 * 1024):
                tamaño += len(bloque)

                if tamaño > MAX_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="El archivo supera los 20 MB",
                    )

                archivo.write(bloque)

        if tamaño == 0:
            raise HTTPException(
                status_code=400,
                detail="El archivo está vacío",
            )

        try:
            resultado = validar_poblacion(temporal)
        except (UnicodeError, csv.Error, ValueError) as error:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )

        if not resultado["valido"]:
            raise HTTPException(
                status_code=422,
                detail=resultado,
            )

        try:
            os.link(temporal, ARCHIVO_POBLACION)
        except FileExistsError:
            raise HTTPException(
                status_code=409,
                detail="El dataset de población ya existe",
            )

        return {
            "mensaje": "Población municipal cargada correctamente",
            "tipo": "informacion_complementaria",
            "archivo": ARCHIVO_POBLACION.name,
            "anio": 2021,
            "registros": resultado["registros"],
            "entrenamiento": False,
            "procesamiento_ml": False,
        }

    finally:
        await file.close()

        if temporal is not None:
            temporal.unlink(missing_ok=True)
