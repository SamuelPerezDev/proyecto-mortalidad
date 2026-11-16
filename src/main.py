
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

# Autenticación con Keycloak
from src.auth import requiere_admin, verificar_token

# Módulo EDA
from src.eda import (
    cargar_eda_stats,
    generar_eda,
    regenerar_eda,
    invalidar_eda,
    obtener_estado_eda,
    encontrar_archivo_raw,
    DANE_RAW_PATTERN,
    RIPS_RAW_PATTERN
)

# Módulo Procesamiento
from src.processing import (
    ejecutar_procesamiento,
    verificar_vigencia_procesamiento,
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

        # Crear archivo sin sobrescribir existentes
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

    # 6. Invalidar estadísticas EDA si el archivo corresponde a un dataset conocido
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
        estado = obtener_estado_eda()
        return estado
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener el estado del EDA: {error}"
        )


@app.get("/eda/dane")
def eda_dane(
    usuario: dict = Depends(verificar_token)
):
    """Devuelve las estadísticas EDA de DANE si están vigentes."""
    stats = cargar_eda_stats("DANE")
    if stats is None:
        raise HTTPException(
            status_code=404,
            detail="Las estadísticas EDA de DANE no están disponibles."
        )

    # Verificar vigencia
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
            detail="Las estadísticas EDA de DANE están desactualizadas. Use POST /eda/regenerate para actualizarlas."
        )

    # Quitar metadatos internos antes de devolver
    stats_publica = {k: v for k, v in stats.items() if k not in ("archivo_hash", "archivo_nombre")}
    return stats_publica


@app.get("/eda/rips")
def eda_rips(
    usuario: dict = Depends(verificar_token)
):
    """Devuelve las estadísticas EDA de RIPS si están vigentes."""
    stats = cargar_eda_stats("RIPS")
    if stats is None:
        raise HTTPException(
            status_code=404,
            detail="Las estadísticas EDA de RIPS no están disponibles."
        )

    # Verificar vigencia
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
            detail="Las estadísticas EDA de RIPS están desactualizadas. Use POST /eda/regenerate para actualizarlas."
        )

    # Quitar metadatos internos antes de devolver
    stats_publica = {k: v for k, v in stats.items() if k not in ("archivo_hash", "archivo_nombre")}
    return stats_publica


@app.post("/eda/regenerate")
def eda_regenerate(
    usuario: dict = Depends(requiere_admin)
):
    """Regenera las estadísticas EDA para DANE y RIPS. Requiere rol admin."""
    try:
        resultados = regenerar_eda()
        return {
            "mensaje": "Regeneración de estadísticas EDA completada",
            "dane": resultados.get("dane", {}),
            "rips": resultados.get("rips", {})
        }
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error al regenerar las estadísticas EDA: {error}"
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
