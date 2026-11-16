
import numpy as np
import pandas as pd

from src.training import dividir_datos
from src.model_training import entrenar_modelos


# Generador reproducible de datos simulados
rng = np.random.default_rng(42)

registros = []

# 100 municipios, cada uno con 3 grupos diagnosticos
for municipio in range(1, 101):
    for grupo in ["G01", "G02", "G03"]:

        total = int(rng.integers(100, 1000))

        proporciones = rng.dirichlet([4, 2, 2, 1])

        cantidades = rng.multinomial(
            total,
            proporciones
        )

        consultas, procedimientos, urgencias, hospitalizaciones = (
            cantidades
        )

        # Variable objetivo simulada
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

# Division 70/15/15 por municipios
train, val, test = dividir_datos(dataset)

# Entrenar y evaluar con validacion
resultados, modelos = entrenar_modelos(train, val)

print("RESULTADOS DEL ENTRENAMIENTO")

for nombre, metricas in resultados.items():
    print(f"\nModelo: {nombre}")

    for metrica, valor in metricas.items():
        print(f"{metrica}: {valor:.4f}")

assert len(modelos) == 2
assert set(resultados) == {
    "regresion_lineal",
    "random_forest"
}

print("\nPrueba superada: ambos modelos entrenados.")

print(
    "Registros de prueba reservados:",
    len(test)
)

# ==========================================
# GUARDAR EVALUACION FINAL
# ==========================================

def guardar_evaluacion_final(
    modelo_seleccionado,
    metricas_validacion,
    metricas_prueba,
    hash_dataset,
    municipios_prueba,
    registros_prueba
):
    """
    Guarda las metricas de evaluacion final
    del modelo seleccionado.
    """

    MODELOS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    reporte = {
        "tipo_datos": "simulados",
        "variable_objetivo": "dane_pct_sin_asistencia",
        "modelo_seleccionado": modelo_seleccionado,
        "criterio_seleccion": "Menor RMSE de validacion",
        "fecha_evaluacion": datetime.now(
            timezone.utc
        ).isoformat(),
        "hash_dataset": hash_dataset,
        "division": {
            "entrenamiento": 70,
            "validacion": 15,
            "prueba": 15
        },
        "metricas_validacion": metricas_validacion,
        "metricas_prueba": metricas_prueba,
        "municipios_prueba": municipios_prueba,
        "registros_prueba": registros_prueba
    }

    ruta_reporte = MODELOS_DIR / "evaluacion_final.json"

    # Guardar primero en un archivo temporal
    # para evitar dejar un JSON incompleto.
    ruta_temporal = ruta_reporte.with_suffix(".json.tmp")

    with open(
        ruta_temporal,
        "w",
        encoding="utf-8"
    ) as archivo:
        json.dump(
            reporte,
            archivo,
            indent=4,
            ensure_ascii=False
        )

    ruta_temporal.replace(ruta_reporte)

    return str(
        ruta_reporte.relative_to(BASE_DIR)
    ).replace("\\", "/")
