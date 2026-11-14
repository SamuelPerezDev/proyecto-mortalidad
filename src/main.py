
from fastapi import FastAPI, UploadFile, File, HTTPException
from pathlib import Path
import csv
import io
import os
import tempfile


# ==========================================
# CONFIGURACIÓN INICIAL DE FASTAPI
# ==========================================

app = FastAPI(
    title="API Proyecto Mortalidad",
    description="API para la carga y análisis de datos de mortalidad",
    version="1.0.0"
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
        "mensaje": "API Proyecto Mortalidad funcionando correctamente"
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
# ==========================================

@app.post("/datasets/upload")
async def cargar_dataset(file: UploadFile = File(...)):

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

    # 6. Respuesta de la API
    return {
        "mensaje": "Dataset CSV cargado correctamente",
        "archivo": nombre,
        "filas": cantidad_filas,
        "columnas": cantidad_columnas,
        "ubicacion": f"data/raw/{nombre}",
        "estado": "cargado"
    }
