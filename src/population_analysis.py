
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from src.auth import verificar_token
from src.eda import (
    leer_csv_raw,
    encontrar_archivo_raw,
    DANE_RAW_PATTERN,
)
from src.processing import procesar_dane, detectar_anio


router = APIRouter(
    prefix="/population",
    tags=["Análisis poblacional"]
)

ROOT = Path(__file__).resolve().parent.parent
POBLACION_FILE = ROOT / "data" / "raw" / "poblacion_municipal_2021.csv"


def obtener_analisis_poblacional():
    # 1. Verificar los archivos
    if not POBLACION_FILE.exists():
        raise FileNotFoundError(
            "No se ha cargado el CSV de población municipal."
        )

    archivo_dane = encontrar_archivo_raw(DANE_RAW_PATTERN)

    if archivo_dane is None:
        raise FileNotFoundError(
            "No se encontró el dataset original del DANE."
        )

    # 2. Leer población sin perder ceros iniciales
    poblacion = pd.read_csv(
        POBLACION_FILE,
        dtype=str,
        encoding="utf-8-sig",
        keep_default_na=False
    )

    requeridas = {
        "cod_municipio", "municipio",
        "departamento", "anio", "poblacion"
    }

    if not requeridas.issubset(poblacion.columns):
        raise ValueError(
            "El archivo de población no tiene las columnas requeridas."
        )

    if poblacion["anio"].ne("2021").any():
        raise ValueError(
            "El archivo de población debe corresponder a 2021."
        )

    if poblacion["cod_municipio"].duplicated().any():
        raise ValueError(
            "Existen códigos municipales duplicados."
        )

    if not poblacion["cod_municipio"].str.fullmatch(r"\d{5}").all():
        raise ValueError("Hay códigos municipales inválidos.")

    if not poblacion["poblacion"].str.fullmatch(r"\d+").all():
        raise ValueError("Hay valores de población inválidos.")

    poblacion["poblacion"] = poblacion["poblacion"].astype("int64")

    if poblacion["poblacion"].le(0).any():
        raise ValueError("Hay valores de población no positivos.")

    # 3. Leer DANE y verificar año
    dane = leer_csv_raw(archivo_dane)

    anio, errores = detectar_anio(dane, "ANO", "DANE")

    if errores or anio != 2021:
        raise ValueError(
            f"El archivo DANE debe corresponder a 2021: {errores}"
        )

    # 4. Reutilizar el procesamiento existente
    dane_procesado, estadisticas = procesar_dane(dane)

    # 5. Sumar defunciones por municipio
    resumen = (
        dane_procesado
        .groupby("cod_municipio", dropna=False)
        .agg(
            defunciones_sin_asistencia=(
                "dane_sin_asistencia", "sum"
            ),
            defunciones_con_respuesta_valida=(
                "dane_total_valido", "sum"
            )
        )
        .reset_index()
    )

    # 6. Relacionar población con DANE
    # Left join: conservar todos los municipios de población.
    resultado = poblacion.merge(
        resumen,
        on="cod_municipio",
        how="left",
        validate="one_to_one",
        indicator=True
    )

    # No convertir municipios sin datos DANE en cero.
    resultado["tasa_por_100000"] = (
        resultado["defunciones_sin_asistencia"]
        / resultado["poblacion"]
        * 100000
    )

    resultado["porcentaje_sin_asistencia_observado"] = (
        resultado["defunciones_sin_asistencia"]
        / resultado["defunciones_con_respuesta_valida"].replace(0, float("nan"))
        * 100
    )

    resultado["estado_dane"] = resultado["_merge"].map({
        "both": "con_datos",
        "left_only": "sin_datos_dane"
    }).astype(str)

    resultado = resultado.drop(columns=["_merge"])

    return resultado, estadisticas


@router.get("/municipios")
def listar_analisis_poblacional(
    usuario: dict = Depends(verificar_token)
):
    try:
        datos, estadisticas = obtener_analisis_poblacional()

        return {
            "anio": 2021,
            "tipo": "analisis_estadistico_observado",
            "entrenamiento_ml": False,
            "total_municipios": len(datos),
            "municipios": datos.where(
                pd.notna(datos), None
            ).to_dict(orient="records")
        }

    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))


@router.get("/municipios/{codigo}")
def consultar_analisis_municipio(
    codigo: str,
    usuario: dict = Depends(verificar_token)
):
    try:
        datos, estadisticas = obtener_analisis_poblacional()

        municipio = datos[
            datos["cod_municipio"] == codigo
        ]

        if municipio.empty:
            raise HTTPException(
                status_code=404,
                detail="Municipio no encontrado."
            )

        registro = municipio.iloc[0].to_dict()

        return {
            clave: None if pd.isna(valor) else (
                valor.item() if hasattr(valor, "item") else valor
            )
            for clave, valor in registro.items()
        }

    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))


# ==========================================
# COMPARACIÓN POBLACIONAL ENTRE MUNICIPIOS
# ==========================================

@router.get("/comparar")
def comparar_poblacion_municipios(
    codigos: str,
    usuario: dict = Depends(verificar_token)
):
    """
    Compara municipios usando población de 2021
    y defunciones observadas del DANE.

    """

    lista_codigos = [
        codigo.strip()
        for codigo in codigos.split(",")
    ]

    # Validar códigos
    if (
        len(lista_codigos) < 2
        or len(lista_codigos) > 10
        or any(
            not codigo.isdigit() or len(codigo) != 5
            for codigo in lista_codigos
        )
    ):
        raise HTTPException(
            status_code=400,
            detail="Debe proporcionar entre 2 y 10 códigos municipales válidos."
        )

    if len(lista_codigos) != len(set(lista_codigos)):
        raise HTTPException(
            status_code=400,
            detail="No se permiten códigos municipales repetidos."
        )

    try:
        datos, _ = obtener_analisis_poblacional()

        municipios = datos[
            datos["cod_municipio"].isin(lista_codigos)
        ].copy()

        encontrados = set(municipios["cod_municipio"])
        no_encontrados = [
            codigo for codigo in lista_codigos
            if codigo not in encontrados
        ]

        if no_encontrados:
            raise HTTPException(
                status_code=404,
                detail={
                    "mensaje": "Algunos municipios no fueron encontrados.",
                    "codigos": no_encontrados
                }
            )

        # Mantener el orden solicitado
        municipios["orden"] = municipios[
            "cod_municipio"
        ].map({
            codigo: indice
            for indice, codigo in enumerate(lista_codigos)
        })

        municipios = municipios.sort_values("orden")
        municipios = municipios.drop(columns=["orden"])

        # Convertir nulos a None para responder JSON
        municipios = municipios.astype(object).where(
            pd.notna(municipios), None
        )

        resultados = municipios.to_dict(orient="records")

        # Ordenar únicamente municipios con tasas disponibles
        ranking = sorted(
            [
                {
                    "cod_municipio": m["cod_municipio"],
                    "municipio": m["municipio"],
                    "tasa_por_100000": m["tasa_por_100000"]
                }
                for m in resultados
                if m["tasa_por_100000"] is not None
            ],
            key=lambda m: m["tasa_por_100000"],
            reverse=True
        )

        return {
            "anio": 2021,
            "tipo": "comparacion_estadistica_poblacional",
            "entrenamiento_ml": False,
            "total_municipios": len(resultados),
            "municipios": resultados,
            "ranking_por_tasa": ranking,
            "nota": (
                "Las tasas se calculan con defunciones observadas "
                "sin asistencia médica por cada 100.000 habitantes. "
                "No representan predicciones ni riesgo individual."
            )
        }

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error)
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error)
        )
