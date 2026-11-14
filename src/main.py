
from fastapi import FastAPI

# Configuración inicial de FastAPI
app = FastAPI(
    title="API Proyecto Mortalidad",
    description="API para el análisis de datos de mortalidad",
    version="1.0.0"
)

# Ruta principal
@app.get("/")
def inicio():
    return {
        "mensaje": "API Proyecto Mortalidad funcionando correctamente"
    }

# Ruta para verificar el estado de la API
@app.get("/health")
def health():
    return {
        "status": "ok",
        "message": "API activa"
    }
