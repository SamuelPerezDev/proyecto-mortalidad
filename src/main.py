
from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    Depends
)
from fastapi.middleware.cors import CORSMiddleware

from pathlib import Path
import csv
import os
import tempfile
from src.model_results import obtener_resultados_modelos
import json
import joblib

from src.training import dividir_datos

from src.model_training import (
    entrenar_modelos,
    guardar_modelos,
    evaluar_modelo_final,
    guardar_evaluacion_final
)

from src.synthetic_data import (
    generar_dataset_simulado,
    calcular_hash_dataset
)

# Autenticación con Keycloak
from src.auth import requiere_admin, verificar_token

# Módulo EDA
from src.eda import (
    cargar_eda_stats,
    regenerar_eda,
    invalidar_eda,
    obtener_estado_eda,
    encontrar_archivo_raw,
    DANE_RAW_PATTERN,
    RIPS_RAW_PATTERN
)

from src.predictions import (
    listar_municipios,
    consultar_municipio,
    comparar_municipios,
)

# Módulo Procesamiento
from src.processing import (
    ejecutar_procesamiento,
    verificar_vigencia_procesamiento,
)


# ==========================================
# CONFIGURACIÓN INICIAL DE FASTAPI
# ORIGINAL - SIN MODIFICACIONES
# ==========================================

app = FastAPI(
    title="API Proyecto Mortalidad",
    description=(
        "API para la carga y análisis de datos "
        "de mortalidad con autenticación Keycloak"
    ),
    version="1.0.0",
    swagger_ui_init_oauth={
        "clientId": "mortalidad-api",
        "usePkceWithAuthorizationCodeGrant": True
    }
)

# ==========================================
# CONFIGURACIÓN DE CORS
# ==========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# ==========================================
# CONFIGURACIÓN DE DIRECTORIOS
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent

RAW_DIR = BASE_DIR / "data" / "raw"

RAW_DIR.mkdir(parents=True, exist_ok=True)

# Tamaño máximo permitido: 600 MB
MAX_FILE_SIZE = 600 * 1024 * 1024

# Tamaño de lectura: 1 MB por bloque
CHUNK_SIZE = 1024 * 1024


# ==========================================
# RUTA PRINCIPAL
# ==========================================

@app.get("/")
def inicio():
    return {
        "mensaje": (
            "API Proyecto Mortalidad "
            "funcionando correctamente"
        )
    }


# ==========================================
# VERIFICAR ESTADO DE LA API
# ==========================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "message": "API activa"
    }


# ==========================================
# CARGA DE DATASETS CSV
# PROTEGIDA CON KEYCLOAK
# ==========================================

@app.post("/datasets/upload")
async def cargar_dataset(
    file: UploadFile = File(...),
    usuario: dict = Depends(requiere_admin)
):

    temporal = None

    try:

        # 1. Verificar extensión del archivo
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="Debe seleccionar un archivo CSV"
            )

        nombre = Path(
            file.filename.replace("\\", "/")
        ).name

        if Path(nombre).suffix.lower() != ".csv":
            raise HTTPException(
                status_code=400,
                detail="Solo se permiten archivos .csv"
            )

        # 2. Verificar si el archivo ya existe
        destino = RAW_DIR / nombre

        if destino.exists():
            raise HTTPException(
                status_code=409,
                detail="Ya existe un archivo con ese nombre"
            )

        # 3. Guardar temporalmente por bloques
        tamaño_total = 0

        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=RAW_DIR,
            delete=False
        ) as archivo_temporal:

            temporal = Path(archivo_temporal.name)

            while True:

                bloque = await file.read(CHUNK_SIZE)

                if not bloque:
                    break

                tamaño_total += len(bloque)

                if tamaño_total > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="El archivo supera el límite de 600 MB"
                    )

                archivo_temporal.write(bloque)

        if tamaño_total == 0:
            raise HTTPException(
                status_code=400,
                detail="El archivo está vacío"
            )

        # 4. Validar estructura básica del CSV
        cantidad_filas = 0
        cantidad_columnas = 0
        encoding_detectado = None

        for encoding in ("utf-8-sig", "latin-1"):

            try:

                with temporal.open(
                    "r",
                    encoding=encoding,
                    newline=""
                ) as archivo_csv:

                    lector = csv.reader(
                        archivo_csv,
                        strict=True
                    )

                    encabezado = next(lector, None)

                    if not encabezado or not any(
                        columna.strip()
                        for columna in encabezado
                    ):
                        raise ValueError(
                            "El archivo no contiene encabezados válidos"
                        )

                    cantidad_columnas = len(encabezado)
                    cantidad_filas = 0

                    for fila in lector:

                        if len(fila) != cantidad_columnas:
                            raise ValueError(
                                "El archivo contiene filas con "
                                "un número incorrecto de columnas"
                            )

                        cantidad_filas += 1

                encoding_detectado = encoding
                break

            except UnicodeError:
                continue

            except (csv.Error, ValueError) as error:
                raise HTTPException(
                    status_code=400,
                    detail=f"Archivo CSV inválido: {error}"
                )

        if encoding_detectado is None:
            raise HTTPException(
                status_code=400,
                detail="No fue posible leer el archivo CSV"
            )

        # 5. Guardar archivo original sin modificarlo
        try:

            os.link(temporal, destino)

        except FileExistsError:
            raise HTTPException(
                status_code=409,
                detail="Ya existe un archivo con ese nombre"
            )

        except OSError:
            raise HTTPException(
                status_code=500,
                detail="Error al guardar el archivo"
            )

        # 6. Invalidar estadísticas EDA
        nombre_lower = nombre.lower()

        if DANE_RAW_PATTERN.lower() in nombre_lower:
            invalidar_eda("DANE")

        elif RIPS_RAW_PATTERN.lower() in nombre_lower:
            invalidar_eda("RIPS")

        # 7. Respuesta de la API
        return {
            "mensaje": "Dataset CSV cargado correctamente",
            "archivo": nombre,
            "filas": cantidad_filas,
            "columnas": cantidad_columnas,
            "tamaño_mb": round(
                tamaño_total / (1024 * 1024),
                2
            ),
            "codificacion": encoding_detectado,
            "ubicacion": f"data/raw/{nombre}",
            "estado": "cargado"
        }

    finally:

        if temporal is not None:
            temporal.unlink(missing_ok=True)

        await file.close()


# ==========================================
# ENDPOINTS EDA
# ==========================================

@app.get("/eda/status")
def eda_status(
    usuario: dict = Depends(verificar_token)
):
    """Devuelve el estado del EDA para DANE y RIPS."""
    try:
        return obtener_estado_eda()

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener el estado del EDA: {error}"
        )


@app.get("/eda/dane")
def eda_dane(
    usuario: dict = Depends(verificar_token)
):
    """Devuelve las estadísticas EDA de DANE."""

    stats = cargar_eda_stats("DANE")

    if stats is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Las estadísticas EDA de DANE "
                "no están disponibles."
            )
        )

    archivo_raw = encontrar_archivo_raw(DANE_RAW_PATTERN)

    if archivo_raw is None:
        raise HTTPException(
            status_code=404,
            detail="No se encontró el archivo RAW de DANE."
        )

    from src.eda import obtener_archivo_hash

    hash_actual = obtener_archivo_hash(archivo_raw)
    hash_guardado = stats.get("archivo_hash")

    if hash_actual != hash_guardado:
        raise HTTPException(
            status_code=404,
            detail=(
                "Las estadísticas EDA de DANE están "
                "desactualizadas. Use POST /eda/regenerate."
            )
        )

    return {
        k: v
        for k, v in stats.items()
        if k not in ("archivo_hash", "archivo_nombre")
    }


@app.get("/eda/rips")
def eda_rips(
    usuario: dict = Depends(verificar_token)
):
    """Devuelve las estadísticas EDA de RIPS."""

    stats = cargar_eda_stats("RIPS")

    if stats is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Las estadísticas EDA de RIPS "
                "no están disponibles."
            )
        )

    archivo_raw = encontrar_archivo_raw(RIPS_RAW_PATTERN)

    if archivo_raw is None:
        raise HTTPException(
            status_code=404,
            detail="No se encontró el archivo RAW de RIPS."
        )

    from src.eda import obtener_archivo_hash

    hash_actual = obtener_archivo_hash(archivo_raw)
    hash_guardado = stats.get("archivo_hash")

    if hash_actual != hash_guardado:
        raise HTTPException(
            status_code=404,
            detail=(
                "Las estadísticas EDA de RIPS están "
                "desactualizadas. Use POST /eda/regenerate."
            )
        )

    return {
        k: v
        for k, v in stats.items()
        if k not in ("archivo_hash", "archivo_nombre")
    }


@app.post("/eda/regenerate")
def eda_regenerate(
    usuario: dict = Depends(requiere_admin)
):
    """Regenera las estadísticas EDA de DANE y RIPS."""

    try:
        resultados = regenerar_eda()

        return {
            "mensaje": (
                "Regeneración de estadísticas EDA completada"
            ),
            "dane": resultados.get("dane", {}),
            "rips": resultados.get("rips", {})
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Error al regenerar las estadísticas EDA: "
                f"{error}"
            )
        )


# ==========================================
# ENDPOINT DIVISIÓN DE DATOS
# ==========================================

@app.post("/training/split")
def training_split(
    usuario: dict = Depends(requiere_admin)
):
    """
    Divide datos simulados por municipio:
    70% entrenamiento, 15% validación y 15% prueba.
    """

    dataset = generar_dataset_simulado()

    try:
        train, val, test = dividir_datos(dataset)

        municipios_train = set(train["cod_municipio"])
        municipios_val = set(val["cod_municipio"])
        municipios_test = set(test["cod_municipio"])

        sin_repeticiones = (
            municipios_train.isdisjoint(municipios_val)
            and municipios_train.isdisjoint(municipios_test)
            and municipios_val.isdisjoint(municipios_test)
        )

        return {
            "mensaje": "División realizada correctamente",
            "tipo_datos": "simulados",
            "configuracion": {
                "entrenamiento": 70,
                "validacion": 15,
                "prueba": 15
            },
            "resultados": {
                "entrenamiento": {
                    "municipios": len(municipios_train),
                    "registros": len(train)
                },
                "validacion": {
                    "municipios": len(municipios_val),
                    "registros": len(val)
                },
                "prueba": {
                    "municipios": len(municipios_test),
                    "registros": len(test)
                }
            },
            "municipios_sin_repetir": sin_repeticiones
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


# ==========================================
# ENDPOINT ENTRENAMIENTO DE MODELOS
# ==========================================

@app.post("/training/train")
def training_train(
    usuario: dict = Depends(requiere_admin)
):
    """
    Entrena Regresión Lineal y Random Forest
    utilizando datos simulados.

    Guarda modelos, métricas, municipios
    y hash del dataset.
    """

    # 1. Generar dataset reproducible
    dataset = generar_dataset_simulado()

    # 2. Calcular huella digital del dataset
    hash_dataset = calcular_hash_dataset(dataset)

    try:
        # 3. Dividir los datos 70/15/15
        train, val, test = dividir_datos(dataset)

        # 4. Entrenar y evaluar en validación
        resultados, modelos = entrenar_modelos(
            train,
            val
        )

        # 5. Guardar modelos y metadatos
        archivos = guardar_modelos(
            modelos,
            resultados,
            train,
            val,
            test,
            hash_dataset
        )

        # 6. Respuesta de la API
        return {
            "mensaje": "Modelos entrenados correctamente",
            "tipo_datos": "simulados",
            "variable_objetivo": "dane_pct_sin_asistencia",
            "hash_dataset": hash_dataset,
            "division": {
                "entrenamiento": 70,
                "validacion": 15,
                "prueba": 15
            },
            "modelos_entrenados": list(modelos.keys()),
            "metricas_validacion": resultados,
            "archivos_guardados": archivos,
            "registros": {
                "entrenamiento": len(train),
                "validacion": len(val),
                "prueba_reservada": len(test)
            }
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


# ==========================================
# ENDPOINT EVALUACION FINAL
# ==========================================

@app.post("/training/evaluate")
def training_evaluate(
    usuario: dict = Depends(requiere_admin)
):
    """
    Evalua el mejor modelo con el 15%
    de prueba reservado.

    Guarda los resultados en un archivo JSON.
    No vuelve a entrenar los modelos.
    """

    ruta_metricas = (
        BASE_DIR / "models" / "simulados" / "metricas.json"
    )

    # 1. Comprobar que existe el reporte
    if not ruta_metricas.is_file():
        raise HTTPException(
            status_code=404,
            detail="No existe un entrenamiento guardado."
        )

    try:
        # 2. Leer reporte de entrenamiento
        with open(
            ruta_metricas,
            encoding="utf-8"
        ) as archivo:
            reporte = json.load(archivo)

        # 3. Reconstruir dataset simulado
        dataset = generar_dataset_simulado()

        # 4. Comprobar integridad del dataset
        hash_actual = calcular_hash_dataset(dataset)
        hash_guardado = reporte.get("hash_dataset")

        if not hash_guardado or hash_actual != hash_guardado:
            raise HTTPException(
                status_code=409,
                detail=(
                    "El dataset no coincide con el utilizado "
                    "durante el entrenamiento."
                )
            )

        # 5. Recuperar la division por municipios
        train, val, test = dividir_datos(dataset)

        municipios_actuales = {
            "entrenamiento": sorted(
                train["cod_municipio"].astype(str).unique().tolist()
            ),
            "validacion": sorted(
                val["cod_municipio"].astype(str).unique().tolist()
            ),
            "prueba": sorted(
                test["cod_municipio"].astype(str).unique().tolist()
            )
        }

        if municipios_actuales != reporte.get("municipios_division"):
            raise HTTPException(
                status_code=409,
                detail=(
                    "La division de municipios no coincide "
                    "con la registrada durante el entrenamiento."
                )
            )

        # 6. Seleccionar mejor modelo segun validacion
        metricas_validacion = reporte["metricas_validacion"]

        mejor_nombre = min(
            metricas_validacion,
            key=lambda nombre: metricas_validacion[nombre]["RMSE"]
        )

        # 7. Verificar modelo permitido
        modelos_permitidos = {
            "regresion_lineal",
            "random_forest"
        }

        if mejor_nombre not in modelos_permitidos:
            raise HTTPException(
                status_code=409,
                detail="El modelo registrado no es valido."
            )

        ruta_modelo = (
            BASE_DIR / "models" / "simulados"
            / f"{mejor_nombre}.joblib"
        )

        if not ruta_modelo.is_file():
            raise HTTPException(
                status_code=404,
                detail="No se encontro el modelo entrenado."
            )

        # 8. Cargar modelo entrenado
        modelo = joblib.load(ruta_modelo)

        # 9. Evaluar con el 15% de prueba
        metricas_prueba = evaluar_modelo_final(
            modelo,
            test
        )

        # 10. Guardar evaluacion final en JSON
        ruta_evaluacion = guardar_evaluacion_final(
            modelo_seleccionado=mejor_nombre,
            metricas_validacion=metricas_validacion[mejor_nombre],
            metricas_prueba=metricas_prueba,
            hash_dataset=hash_actual,
            municipios_prueba=int(
                test["cod_municipio"].nunique()
            ),
            registros_prueba=len(test)
        )

        # 11. Respuesta de la API
        return {
            "mensaje": "Evaluacion final completada",
            "tipo_datos": "simulados",
            "modelo_seleccionado": mejor_nombre,
            "criterio_seleccion": "Menor RMSE de validacion",
            "hash_verificado": True,
            "municipios_verificados": True,
            "metricas_validacion": metricas_validacion[mejor_nombre],
            "metricas_prueba": metricas_prueba,
            "municipios_prueba": int(
                test["cod_municipio"].nunique()
            ),
            "registros_prueba": len(test),
            "archivo_evaluacion": ruta_evaluacion
        }

    except HTTPException:
        raise

    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "No fue posible evaluar el entrenamiento "
                "guardado. Verifique sus archivos y metadatos."
            )
        )


# ==========================================
# ENDPOINTS DE PROCESAMIENTO
# ==========================================

@app.get("/processing/status")
def processing_status(
    usuario: dict = Depends(verificar_token)
):
    """Devuelve el estado del dataset procesado."""
    try:
        estado = verificar_vigencia_procesamiento()
        return estado
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener el estado del procesamiento: {error}"
        )


@app.post("/processing/run")
def processing_run(
    usuario: dict = Depends(requiere_admin)
):
    """Ejecuta el procesamiento de datos DANE y RIPS. Requiere rol admin.

    Solo una ejecución puede estar activa a la vez. Las solicitudes
    concurrentes se rechazan con HTTP 409.
    """
    try:
        resultado = ejecutar_procesamiento()

        if resultado["estado"] == "error":
            errores = resultado["errores"]

            # Detectar ejecución concurrente
            if any("activa" in e.lower() for e in errores):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "mensaje": "Ya hay una ejecución de procesamiento activa.",
                        "errores": errores,
                    }
                )

            raise HTTPException(
                status_code=422,
                detail={
                    "mensaje": "El procesamiento falló.",
                    "errores": errores,
                    "advertencias": resultado.get("advertencias", [])
                }
            )

        anio = resultado["estadisticas"].get("anio", "desconocido")
        observaciones = resultado["estadisticas"].get(
            "observaciones_finales", 0
        )

        return {
            "mensaje": (
                f"Dataset generado correctamente. "
                f"Año de los datos: {anio}."
            ),
            "observaciones": observaciones,
            "estadisticas": resultado["estadisticas"],
            "advertencias": resultado.get("advertencias", [])
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error inesperado durante el procesamiento: {error}"
        )

# ==========================================
# ENTRENAMIENTO CON DATOS REALES DANE + RIPS
# ==========================================

import hashlib
from datetime import datetime, timezone

import pandas as pd

from src.preprocessing import (
    VARIABLES_NUMERICAS,
    VARIABLES_CATEGORICAS,
    VARIABLE_OBJETIVO
)


REAL_DATASET_PATH = (
    BASE_DIR / "data" / "processed" / "dataset_entrenamiento.csv"
)

REAL_MODELS_DIR = BASE_DIR / "models" / "reales"

REAL_SPLIT_CONFIG = {
    "entrenamiento": 70,
    "validacion": 15,
    "prueba": 15
}


def calcular_hash_archivo_real(ruta):
    """Calcula SHA256 sin modificar el archivo."""
    hash_sha256 = hashlib.sha256()

    with open(ruta, "rb") as archivo:
        for bloque in iter(
            lambda: archivo.read(1024 * 1024),
            b""
        ):
            hash_sha256.update(bloque)

    return hash_sha256.hexdigest()


def cargar_dataset_real_entrenable():
    """
    Lee el dataset real y selecciona registros completos.

    No modifica el CSV procesado.
    No imputa valores.
    Devuelve también estadísticas de selección.
    """

    if not REAL_DATASET_PATH.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                "No existe dataset_entrenamiento.csv. "
                "Ejecute primero POST /processing/run."
            )
        )

    dataset = pd.read_csv(
        REAL_DATASET_PATH,
        dtype={
            "cod_municipio": "string",
            "cod_grupo_diagnostico": "string"
        }
    )

    columnas_requeridas = (
        ["cod_municipio"]
        + VARIABLES_NUMERICAS
        + VARIABLES_CATEGORICAS
        + [VARIABLE_OBJETIVO]
    )

    faltantes = [
        columna
        for columna in columnas_requeridas
        if columna not in dataset.columns
    ]

    if faltantes:
        raise HTTPException(
            status_code=422,
            detail=f"Faltan columnas: {faltantes}"
        )

    # Comprobar que las variables numéricas sean válidas.
    import numpy as np

    for columna in (
        VARIABLES_NUMERICAS + [VARIABLE_OBJETIVO]
    ):
        serie = pd.to_numeric(
            dataset[columna],
            errors="coerce"
        )

        valores_invalidos = (
            dataset[columna].notna()
            & (
                serie.isna()
                | ~np.isfinite(serie)
            )
        )

        if valores_invalidos.any():
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Existen valores numéricos inválidos "
                    f"en {columna}."
                )
            )

        dataset[columna] = serie

    # Selección explícita para entrenamiento.
    mascara_completos = (
        dataset[columnas_requeridas]
        .notna()
        .all(axis=1)
    )

    datos_completos = dataset.loc[
        mascara_completos
    ].copy()

    estadisticas = {
        "registros_originales": int(len(dataset)),
        "registros_completos": int(
            mascara_completos.sum()
        ),
        "registros_no_utilizados": int(
            (~mascara_completos).sum()
        ),
        "municipios_disponibles": int(
            datos_completos["cod_municipio"].nunique()
        ),
        "nulos_por_columna": {
            columna: int(cantidad)
            for columna, cantidad in (
                dataset[columnas_requeridas]
                .isna()
                .sum()
                .items()
            )
        }
    }

    if datos_completos.empty:
        raise HTTPException(
            status_code=422,
            detail="No existen registros completos para entrenar."
        )

    if datos_completos["cod_municipio"].nunique() < 3:
        raise HTTPException(
            status_code=422,
            detail="Se necesitan al menos tres municipios."
        )

    return datos_completos, estadisticas


def dividir_dataset_real():
    """Aplica la división existente por municipios."""
    dataset, estadisticas = cargar_dataset_real_entrenable()

    train, val, test = dividir_datos(
        dataset,
        entrenamiento=70,
        validacion=15,
        prueba=15,
        random_state=42
    )

    return train, val, test, estadisticas


def municipios_de_conjunto(datos):
    return sorted(
        datos["cod_municipio"]
        .astype(str)
        .unique()
        .tolist()
    )


# ==========================================
# 1. DIVISIÓN DE DATOS REALES
# ==========================================

@app.post("/training/real/split")
def training_real_split(
    usuario: dict = Depends(requiere_admin)
):
    try:
        train, val, test, estadisticas = (
            dividir_dataset_real()
        )

        municipios_train = set(
            municipios_de_conjunto(train)
        )
        municipios_val = set(
            municipios_de_conjunto(val)
        )
        municipios_test = set(
            municipios_de_conjunto(test)
        )

        return {
            "mensaje": "División de datos reales completada",
            "tipo_datos": "reales",
            "configuracion": REAL_SPLIT_CONFIG,
            "seleccion": estadisticas,
            "resultados": {
                "entrenamiento": {
                    "municipios": len(municipios_train),
                    "registros": len(train)
                },
                "validacion": {
                    "municipios": len(municipios_val),
                    "registros": len(val)
                },
                "prueba": {
                    "municipios": len(municipios_test),
                    "registros": len(test)
                }
            },
            "municipios_sin_repetir": (
                municipios_train.isdisjoint(municipios_val)
                and municipios_train.isdisjoint(municipios_test)
                and municipios_val.isdisjoint(municipios_test)
            )
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


# ==========================================
# 2. ENTRENAMIENTO DE MODELOS REALES
# ==========================================

@app.post("/training/real/train")
def training_real_train(
    usuario: dict = Depends(requiere_admin)
):
    try:
        train, val, test, estadisticas = (
            dividir_dataset_real()
        )

        hash_dataset = calcular_hash_archivo_real(
            REAL_DATASET_PATH
        )

        # Reutilizar el entrenamiento existente.
        resultados, modelos = entrenar_modelos(
            train,
            val
        )

        REAL_MODELS_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        archivos_guardados = {}

        for nombre, modelo in modelos.items():
            ruta = REAL_MODELS_DIR / f"{nombre}.joblib"

            joblib.dump(modelo, ruta)

            archivos_guardados[nombre] = str(
                ruta.relative_to(BASE_DIR)
            ).replace("\\", "/")

        reporte = {
            "tipo_datos": "reales",
            "variable_objetivo": VARIABLE_OBJETIVO,
            "fecha_entrenamiento": datetime.now(
                timezone.utc
            ).isoformat(),
            "division": REAL_SPLIT_CONFIG,
            "random_state": 42,
            "hash_dataset": hash_dataset,
            "seleccion": estadisticas,
            "metricas_validacion": resultados,
            "modelos": archivos_guardados,
            "municipios_division": {
                "entrenamiento": municipios_de_conjunto(train),
                "validacion": municipios_de_conjunto(val),
                "prueba": municipios_de_conjunto(test)
            }
        }

        ruta_metricas = (
            REAL_MODELS_DIR / "metricas.json"
        )

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
            "mensaje": "Modelos reales entrenados correctamente",
            "tipo_datos": "reales",
            "variable_objetivo": VARIABLE_OBJETIVO,
            "hash_dataset": hash_dataset,
            "modelos_entrenados": list(modelos.keys()),
            "metricas_validacion": resultados,
            "seleccion": estadisticas,
            "archivos_guardados": {
                "modelos": archivos_guardados,
                "metricas": str(
                    ruta_metricas.relative_to(BASE_DIR)
                ).replace("\\", "/")
            },
            "registros": {
                "entrenamiento": len(train),
                "validacion": len(val),
                "prueba_reservada": len(test)
            }
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


# ==========================================
# 3. EVALUACIÓN FINAL DE MODELOS REALES
# ==========================================

@app.post("/training/real/evaluate")
def training_real_evaluate(
    usuario: dict = Depends(requiere_admin)
):
    ruta_metricas = (
        REAL_MODELS_DIR / "metricas.json"
    )

    if not ruta_metricas.is_file():
        raise HTTPException(
            status_code=404,
            detail="No existe entrenamiento real guardado."
        )

    try:
        with open(
            ruta_metricas,
            encoding="utf-8"
        ) as archivo:
            reporte = json.load(archivo)

        hash_actual = calcular_hash_archivo_real(
            REAL_DATASET_PATH
        )

        if hash_actual != reporte.get("hash_dataset"):
            raise HTTPException(
                status_code=409,
                detail=(
                    "El dataset real cambió desde "
                    "el entrenamiento."
                )
            )

        train, val, test, estadisticas = (
            dividir_dataset_real()
        )

        municipios_actuales = {
            "entrenamiento": municipios_de_conjunto(train),
            "validacion": municipios_de_conjunto(val),
            "prueba": municipios_de_conjunto(test)
        }

        if municipios_actuales != reporte.get(
            "municipios_division"
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "La división de municipios no coincide "
                    "con la del entrenamiento."
                )
            )

        metricas_validacion = reporte[
            "metricas_validacion"
        ]

        mejor_nombre = min(
            metricas_validacion,
            key=lambda nombre: (
                metricas_validacion[nombre]["RMSE"]
            )
        )

        modelos_permitidos = {
            "regresion_lineal",
            "random_forest"
        }

        if mejor_nombre not in modelos_permitidos:
            raise HTTPException(
                status_code=409,
                detail="El modelo seleccionado no es válido."
            )

        ruta_modelo = (
            REAL_MODELS_DIR / f"{mejor_nombre}.joblib"
        )

        if not ruta_modelo.is_file():
            raise HTTPException(
                status_code=404,
                detail="No existe el modelo real entrenado."
            )

        modelo = joblib.load(ruta_modelo)

        metricas_prueba = evaluar_modelo_final(
            modelo,
            test
        )

        evaluacion = {
            "tipo_datos": "reales",
            "variable_objetivo": VARIABLE_OBJETIVO,
            "modelo_seleccionado": mejor_nombre,
            "criterio_seleccion": (
                "Menor RMSE de validacion"
            ),
            "fecha_evaluacion": datetime.now(
                timezone.utc
            ).isoformat(),
            "hash_dataset": hash_actual,
            "division": REAL_SPLIT_CONFIG,
            "metricas_validacion": (
                metricas_validacion[mejor_nombre]
            ),
            "metricas_prueba": metricas_prueba,
            "municipios_prueba": int(
                test["cod_municipio"].nunique()
            ),
            "registros_prueba": len(test),
            "seleccion": estadisticas
        }

        ruta_evaluacion = (
            REAL_MODELS_DIR / "evaluacion_final.json"
        )

        ruta_temporal = ruta_evaluacion.with_suffix(
            ".json.tmp"
        )

        with open(
            ruta_temporal,
            "w",
            encoding="utf-8"
        ) as archivo:
            json.dump(
                evaluacion,
                archivo,
                indent=4,
                ensure_ascii=False
            )

        ruta_temporal.replace(ruta_evaluacion)

        return {
            "mensaje": "Evaluación real completada",
            "tipo_datos": "reales",
            "modelo_seleccionado": mejor_nombre,
            "criterio_seleccion": (
                "Menor RMSE de validacion"
            ),
            "hash_verificado": True,
            "municipios_verificados": True,
            "metricas_validacion": (
                metricas_validacion[mejor_nombre]
            ),
            "metricas_prueba": metricas_prueba,
            "municipios_prueba": int(
                test["cod_municipio"].nunique()
            ),
            "registros_prueba": len(test),
            "archivo_evaluacion": str(
                ruta_evaluacion.relative_to(BASE_DIR)
            ).replace("\\", "/")
        }

    except HTTPException:
        raise

    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError
    ) as error:
        raise HTTPException(
            status_code=409,
            detail=(
                "No fue posible evaluar el entrenamiento "
                f"real guardado: {error}"
            )
        )

@app.get(
    "/admin/models/comparison",
    tags=["Administrador - Modelos"]
)
def consultar_comparacion_modelos(
    usuario=Depends(requiere_admin)
):
    try:
        return obtener_resultados_modelos()

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Primero debes entrenar y evaluar los modelos."
        )

    except (ValueError, KeyError) as error:
        raise HTTPException(
            status_code=409,
            detail=str(error)
        )


# ============================================================
# PREDICCIONES PÚBLICAS - ACCESO COMO INVITADO
# ============================================================

@app.get(
    "/predictions/municipios",
    tags=["Predicciones públicas"]
)
def obtener_municipios():
    return listar_municipios()


@app.get(
    "/predictions/municipios/{codigo}",
    tags=["Predicciones públicas"]
)
def obtener_prediccion_municipio(codigo: str):

    resultado = consultar_municipio(codigo)

    if not resultado["encontrado"]:
        raise HTTPException(
            status_code=404,
            detail="No se encontró el municipio solicitado."
        )

    return resultado


@app.get(
    "/predictions/comparar",
    tags=["Predicciones públicas"]
)
def obtener_comparacion_municipios(codigos: str):

    lista_codigos = [
        codigo.strip()
        for codigo in codigos.split(",")
        if codigo.strip()
    ]

    try:
        return comparar_municipios(lista_codigos)

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )
