
from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    Depends
)

from pathlib import Path
import csv
import io
import os
import tempfile

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


# ==========================================
# CONFIGURACIÓN INICIAL DE FASTAPI
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
# CONFIGURACIÓN DE DIRECTORIOS
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent

RAW_DIR = BASE_DIR / "data" / "raw"

RAW_DIR.mkdir(parents=True, exist_ok=True)

# Tamaño máximo permitido: 20 MB
MAX_FILE_SIZE = 20 * 1024 * 1024


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

    # 2. Leer archivo con límite de tamaño
    contenido = await file.read(MAX_FILE_SIZE + 1)

    if len(contenido) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="El archivo supera el límite de 20 MB"
        )

    if not contenido:
        raise HTTPException(
            status_code=400,
            detail="El archivo está vacío"
        )

    # 3. Validar estructura básica del CSV
    try:
        texto = contenido.decode("utf-8-sig")

        lector = csv.reader(
            io.StringIO(texto),
            strict=True
        )

        encabezado = next(lector, None)

        if not encabezado or not any(
            columna.strip() for columna in encabezado
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

    except (UnicodeError, csv.Error, ValueError) as error:
        raise HTTPException(
            status_code=400,
            detail=f"Archivo CSV inválido: {error}"
        )

    # 4. Verificar si el archivo ya existe
    destino = RAW_DIR / nombre

    if destino.exists():
        raise HTTPException(
            status_code=409,
            detail="Ya existe un archivo con ese nombre"
        )

    # 5. Guardar archivo original sin modificarlo
    temporal = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=RAW_DIR,
            delete=False
        ) as archivo_temporal:

            temporal = Path(archivo_temporal.name)
            archivo_temporal.write(contenido)

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

    finally:
        if temporal is not None:
            temporal.unlink(missing_ok=True)

        await file.close()

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
        "ubicacion": f"data/raw/{nombre}",
        "estado": "cargado"
    }


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
