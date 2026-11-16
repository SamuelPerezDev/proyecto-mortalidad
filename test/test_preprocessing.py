
import pandas as pd

from src.preprocessing import (
    preparar_variables,
    crear_preprocesador
)

# Datos simulados
dataset = pd.DataFrame({
    "rips_total_atenciones": [100, 200, 150, 300],
    "rips_consultas": [50, 100, 75, 150],
    "rips_procedimientos": [20, 40, 30, 60],
    "rips_urgencias": [20, 40, 30, 60],
    "rips_hospitalizaciones": [10, 20, 15, 30],
    "rips_pct_consultas": [50, 50, 50, 50],
    "rips_pct_procedimientos": [20, 20, 20, 20],
    "rips_pct_urgencias": [20, 20, 20, 20],
    "rips_pct_hospitalizaciones": [10, 10, 10, 10],
    "cod_grupo_diagnostico": ["G01", "G02", "G01", "G03"],
    "dane_pct_sin_asistencia": [10, 15, 12, 20]
})

# Conservar una copia para verificar que no cambie
original = dataset.copy(deep=True)

# Separar variables
X, y = preparar_variables(dataset)

print("Variables predictoras:", X.shape[1])
print("Registros:", len(X))
print("Variable objetivo:", y.name)

# Crear y ajustar preprocesador con datos simulados
preprocesador = crear_preprocesador()
X_transformado = preprocesador.fit_transform(X)

print("Columnas después del preprocesamiento:", X_transformado.shape[1])

# Comprobar que el dataset original no cambió
assert dataset.equals(original)

# Comprobar que la variable objetivo no está en X
assert "dane_pct_sin_asistencia" not in X.columns

print("Prueba superada: preprocesamiento correcto.")
