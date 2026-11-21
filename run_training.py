import sys
import hashlib
import pandas as pd

sys.path.insert(0, '.')

from src.training import dividir_datos
from src.model_training import (
    entrenar_modelos,
    guardar_modelos,
    evaluar_modelo_final,
    guardar_evaluacion_final
)

# 1. Cargar dataset
print("=" * 60)
print("CARGANDO DATASET")
print("=" * 60)
df = pd.read_csv("data/processed/dataset_entrenamiento.csv")
print(f"Registros totales: {len(df)}")

# 2. Filtrar registros completos
df_completos = df.dropna()
print(f"Registros completos: {len(df_completos)}")

if len(df_completos) == 0:
    print("ERROR: No hay registros completos para entrenar.")
    sys.exit(1)

# 3. Dividir por municipio
print("\n" + "=" * 60)
print("DIVIDIENDO DATOS POR MUNICIPIO")
print("=" * 60)
datos_train, datos_val, datos_test = dividir_datos(df_completos)
print(f"Entrenamiento: {len(datos_train)} registros")
print(f"Validacion: {len(datos_val)} registros")
print(f"Prueba: {len(datos_test)} registros")

# 4. Entrenar modelos
print("\n" + "=" * 60)
print("ENTRENANDO MODELOS")
print("=" * 60)
resultados, modelos = entrenar_modelos(datos_train, datos_val)

print("\nMETRICAS DE VALIDACION:")
for nombre, metricas in resultados.items():
    print(f"  {nombre}:")
    print(f"    MAE:  {metricas['MAE']:.4f}")
    print(f"    RMSE: {metricas['RMSE']:.4f}")
    print(f"    R2:   {metricas['R2']:.4f}")

# 5. Calcular hash del dataset
hash_ds = hashlib.sha256(
    open("data/processed/dataset_entrenamiento.csv", "rb").read()
).hexdigest()

# 6. Guardar modelos
print("\n" + "=" * 60)
print("GUARDANDO MODELOS")
print("=" * 60)
guardados = guardar_modelos(modelos, resultados, datos_train, datos_val, datos_test, hash_ds)
print(f"Archivos guardados: {guardados}")

# 7. Evaluar modelo mejor (menor RMSE en validacion)
print("\n" + "=" * 60)
print("EVALUACION FINAL CON DATOS DE PRUEBA")
print("=" * 60)

mejor_modelo = min(resultados.keys(), key=lambda k: resultados[k]["RMSE"])
print(f"Mejor modelo (menor RMSE validacion): {mejor_modelo}")

metricas_prueba = evaluar_modelo_final(modelos[mejor_modelo], datos_test)
print(f"\nMetricas de prueba ({mejor_modelo}):")
print(f"  MAE:  {metricas_prueba['MAE']:.4f}")
print(f"  RMSE: {metricas_prueba['RMSE']:.4f}")
print(f"  R2:   {metricas_prueba['R2']:.4f}")

# 8. Guardar evaluacion final
municipios_prueba = sorted(datos_test["cod_municipio"].astype(str).unique().tolist())
ruta_eval = guardar_evaluacion_final(
    mejor_modelo,
    resultados[mejor_modelo],
    metricas_prueba,
    hash_ds,
    municipios_prueba,
    len(datos_test)
)
print(f"\nEvaluacion guardada en: {ruta_eval}")

# 9. Tambien evaluar el otro modelo
otro_modelo = [k for k in resultados.keys() if k != mejor_modelo][0]
metricas_prueba_otro = evaluar_modelo_final(modelos[otro_modelo], datos_test)
print(f"\nMetricas de prueba ({otro_modelo}):")
print(f"  MAE:  {metricas_prueba_otro['MAE']:.4f}")
print(f"  RMSE: {metricas_prueba_otro['RMSE']:.4f}")
print(f"  R2:   {metricas_prueba_otro['R2']:.4f}")

print("\n" + "=" * 60)
print("PIPELINE COMPLETADO EXITOSAMENTE")
print("=" * 60)
