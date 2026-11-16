
import numpy as np
import pandas as pd
import hashlib

def generar_dataset_simulado():
    """
    Genera un dataset reproducible
    para probar el entrenamiento.
    """

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

    return pd.DataFrame(registros)

def calcular_hash_dataset(dataset):
    """
    Calcula una huella SHA-256 del dataset,
    incluyendo columnas, tipos, indice y valores.
    """

    contenido = dataset.to_json(
        orient="table",
        index=True,
        date_format="iso",
        double_precision=15
    )

    return hashlib.sha256(
        contenido.encode("utf-8")
    ).hexdigest()
