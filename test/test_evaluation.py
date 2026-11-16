
import joblib
import pandas as pd
import numpy as np

from pathlib import Path

from src.training import dividir_datos
from src.model_training import evaluar_modelo_final


# Reproducir los datos simulados utilizados
# durante el entrenamiento
rng = np.random.default_rng(42)

registros = []

for municipio in range(1, 101):
    for grupo in ["G01", "G02", "G03"]:

        total = int(rng.integers(100, 1000))
        proporciones = rng.dirichlet([4, 2, 2, 1])
        cantidades = rng.multinomial(
            total,
            proporciones
        )

        consultas, procedimientos, urgencias, hospitalizaciones = cantidades

        porcentaje = (
            5
            + 0.02 * urgencias
            + 0.03 * hospitalizaciones
            + rng.normal(0, 2)
        )

        porcentaje = float(
            np.clip(porcentaje, 0, 100)
        )

        registros.append({
            "cod_municipio": f"{municipio:05d}",
            "cod_grupo_diagnostico": grupo,
            "rips_total_atenciones": total,
            "rips_consultas": int(consultas),
            "rips_procedimientos": int(procedimientos),
            "rips_urgencias": int(urgencias),
            "rips_hospitalizaciones": int(hospitalizaciones),
            "rips_pct_consultas": consultas / total * 100,
            "rips_pct_procedimientos": procedimientos / total * 100,
            "rips_pct_urgencias": urgencias / total * 100,
            "rips_pct_hospitalizaciones": hospitalizaciones / total * 100,
            "dane_pct_sin_asistencia": porcentaje
        })


dataset = pd.DataFrame(registros)

# Recuperar el 15% de prueba reservado
_, _, test = dividir_datos(dataset)

# Cargar metricas de validacion
import json

ruta_metricas = Path("models/simulados/metricas.json")

with open(ruta_metricas, encoding="utf-8") as archivo:
    reporte = json.load(archivo)

# Elegir el mejor modelo utilizando solo validacion
mejor_nombre = min(
    reporte["metricas_validacion"],
    key=lambda nombre: reporte["metricas_validacion"][nombre]["RMSE"]
)

# Cargar el modelo seleccionado
ruta_modelo = Path("models/simulados") / f"{mejor_nombre}.joblib"

modelo = joblib.load(ruta_modelo)

# Evaluar una sola vez sobre el conjunto de prueba
metricas = evaluar_modelo_final(modelo, test)

print("EVALUACION FINAL")
print("Modelo seleccionado:", mejor_nombre)

for nombre, valor in metricas.items():
    print(f"{nombre}: {valor:.4f}")

print("Municipios de prueba:", test["cod_municipio"].nunique())
print("Registros de prueba:", len(test))
print("Evaluacion final completada.")
