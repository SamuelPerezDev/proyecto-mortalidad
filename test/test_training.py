
import pandas as pd

from src.training import dividir_datos


# Crear datos simulados de 100 municipios
dataset = pd.DataFrame({
    "cod_municipio": [
        f"{i:05d}" for i in range(1, 101)
        for _ in range(3)
    ],
    "cod_grupo_diagnostico": [
        grupo for _ in range(100)
        for grupo in ["G01", "G02", "G03"]
    ],
    "rips_total_atenciones": [100] * 300,
    "dane_pct_sin_asistencia": [15.0] * 300
})


# Probar división predeterminada 70/15/15
train, val, test = dividir_datos(dataset)

print("DIVISIÓN 70/15/15")
print("Municipios entrenamiento:", train["cod_municipio"].nunique())
print("Municipios validación:", val["cod_municipio"].nunique())
print("Municipios prueba:", test["cod_municipio"].nunique())


# Probar división personalizada 80/10/10
train, val, test = dividir_datos(
    dataset,
    entrenamiento=80,
    validacion=10,
    prueba=10
)

print("\nDIVISIÓN 80/10/10")
print("Municipios entrenamiento:", train["cod_municipio"].nunique())
print("Municipios validación:", val["cod_municipio"].nunique())
print("Municipios prueba:", test["cod_municipio"].nunique())


# Verificar que ningún municipio se repita
municipios_train = set(train["cod_municipio"])
municipios_val = set(val["cod_municipio"])
municipios_test = set(test["cod_municipio"])

assert municipios_train.isdisjoint(municipios_val)
assert municipios_train.isdisjoint(municipios_test)
assert municipios_val.isdisjoint(municipios_test)

print("\nPrueba superada: no hay municipios repetidos.")
