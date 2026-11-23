# -*- coding: utf-8 -*-
"""
Script para generar frontend-IA/src/data/tasas_municipales_2021.json.

Reutiliza directamente obtener_analisis_poblacional() del backend
sin modificar ningún archivo del backend ni los CSV originales.
"""

import json
import math
import sys
from pathlib import Path
from collections import OrderedDict

import numpy as np
import pandas as pd

# Agregar el backend al path para importar la función
# El script está en backend-IA/scripts/, así que el backend es el padre
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

from src.population_analysis import obtener_analisis_poblacional


def safe_json_value(value):
    """Convertir NaN e infinitos a None (null en JSON). No convertir a cero."""
    if value is None:
        return None
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def main():
    print("=" * 60)
    print("GENERACIÓN DE tasas_municipales_2021.json")
    print("=" * 60)

    # --------------------------------------------------
    # 1. Ejecutar la función del backend
    # --------------------------------------------------
    print("\n[1] Ejecutando obtener_analisis_poblacional()...")
    try:
        datos, estadisticas = obtener_analisis_poblacional()
    except Exception as e:
        print(f"ERROR: No se pudo ejecutar la función: {e}")
        sys.exit(1)

    print(f"   Municipios obtenidos: {len(datos)}")
    print(f"   Columnas: {list(datos.columns)}")

    # --------------------------------------------------
    # 2. Validar estructura de datos
    # --------------------------------------------------
    print("\n[2] Validando estructura de datos...")

    columnas_requeridas = {"cod_municipio", "tasa_por_100000", "estado_dane"}
    columnas_presentes = set(datos.columns)

    if not columnas_requeridas.issubset(columnas_presentes):
        faltantes = columnas_requeridas - columnas_presentes
        print(f"ERROR: Columnas faltantes: {faltantes}")
        sys.exit(1)

    print("   [OK] Columnas requeridas presentes")

    # Validar códigos únicos
    codigos = datos["cod_municipio"].astype(str)
    if codigos.duplicated().any():
        duplicados = codigos[codigos.duplicated()].unique()
        print(f"ERROR: Códigos duplicados encontrados: {duplicados}")
        sys.exit(1)

    print(f"   [OK] {len(codigos.unique())} códigos únicos")

    # Validar formato 5 dígitos
    if not codigos.str.fullmatch(r"\d{5}").all():
        invalidos = codigos[~codigos.str.fullmatch(r"\d{5}")]
        print(f"ERROR: Códigos con formato inválido: {invalidos.head()}")
        sys.exit(1)

    print("   [OK] Todos los códigos son de 5 dígitos")

    # --------------------------------------------------
    # 3. Cargar TopoJSON y validar correspondencia
    # --------------------------------------------------
    print("\n[3] Validando correspondencia con TopoJSON...")

    # frontend-IA está al mismo nivel que backend-IA
    project_root = Path(__file__).parent.parent.parent
    topojson_path = project_root / "frontend-IA" / "src" / "data" / "MGNMPIOPOLITICO2021_optimized.topojson"

    if not topojson_path.exists():
        print(f"ADVERTENCIA: TopoJSON no encontrado en {topojson_path}")
        print("   Saltando validación de correspondencia")
        topojson_codigos = None
    else:
        with open(topojson_path, "r", encoding="utf-8") as f:
            topojson = json.load(f)

        geometrias = topojson["objects"]["municipios"]["geometries"]
        topojson_codigos = set()

        for geom in geometrias:
            props = geom.get("properties", {})
            codigo = props.get("MPIO_CDPMP", "")
            if codigo:
                topojson_codigos.add(str(codigo).zfill(5))

        print(f"   Municipios en TopoJSON: {len(topojson_codigos)}")

        # Comparar cobertura
        datos_codigos = set(codigos)

        sin_correspondencia_topo = datos_codigos - topojson_codigos
        sin_correspondencia_datos = topojson_codigos - datos_codigos

        if sin_correspondencia_topo:
            print(f"   [!] Municipios en datos pero NO en TopoJSON: {len(sin_correspondencia_topo)}")
            for cod in sorted(sin_correspondencia_topo)[:10]:
                mun = datos[datos["cod_municipio"] == cod]["municipio"].values
                nombre = mun[0] if len(mun) > 0 else "N/A"
                print(f"      {cod} - {nombre}")
        else:
            print("   [OK] Todos los municipios de datos están en TopoJSON")

        if sin_correspondencia_datos:
            print(f"   [!] Municipios en TopoJSON pero NO en datos: {len(sin_correspondencia_datos)}")
            for cod in sorted(sin_correspondencia_datos)[:10]:
                print(f"      {cod}")
        else:
            print("   [OK] Todos los municipios de TopoJSON están en datos")

    # --------------------------------------------------
    # 4. Validar tasas
    # --------------------------------------------------
    print("\n[4] Validando tasas...")

    tasas = datos["tasa_por_100000"]
    tasas_validas = tasas.dropna()

    print(f"   Municipios con tasa calculada: {len(tasas_validas)}")
    print(f"   Municipios sin tasa (NaN): {tasas.isna().sum()}")

    if len(tasas_validas) > 0:
        print(f"   Tasa mínima: {tasas_validas.min():.4f}")
        print(f"   Tasa máxima: {tasas_validas.max():.4f}")
        print(f"   Tasa media: {tasas_validas.mean():.4f}")

    # Verificar tasas negativas o infinitas
    if len(tasas_validas) > 0:
        tasas_negativas = (tasas_validas < 0).sum()
        tasas_infinitas = np.isinf(tasas_validas).sum()

        if tasas_negativas > 0:
            print(f"   [!] Tasas negativas: {tasas_negativas}")
        if tasas_infinitas > 0:
            print(f"   [!] Tasas infinitas: {tasas_infinitas}")

    # --------------------------------------------------
    # 5. Validar estado_dane
    # --------------------------------------------------
    print("\n[5] Validando estado_dane...")

    estados = datos["estado_dane"].value_counts()
    for estado, count in estados.items():
        print(f"   {estado}: {count}")

    # --------------------------------------------------
    # 6. Comparar municipios clave
    # --------------------------------------------------
    print("\n[6] Comparando municipios clave...")

    municipios_clave = {
        "20001": "Valledupar",
        "11001": "Bogotá",
        "05001": "Medellín"
    }

    for codigo, nombre in municipios_clave.items():
        registro = datos[datos["cod_municipio"] == codigo]

        if registro.empty:
            print(f"   [!] {nombre} ({codigo}) NO encontrado en datos")
            continue

        reg = registro.iloc[0]
        tasa = reg["tasa_por_100000"]
        estado = reg["estado_dane"]
        defunciones = reg["defunciones_sin_asistencia"]
        poblacion = reg["poblacion"]

        if pd.isna(tasa):
            tasa_str = "null"
        else:
            tasa_str = f"{tasa:.4f}"

        print(f"   {nombre} ({codigo}):")
        print(f"      Tasa: {tasa_str} por 100.000 hab.")
        print(f"      Estado DANE: {estado}")
        print(f"      Defunciones sin asistencia: {defunciones}")
        print(f"      Población: {poblacion}")

    # --------------------------------------------------
    # 7. Construir y serializar JSON
    # --------------------------------------------------
    print("\n[7] Construyendo archivo JSON...")

    registros = []
    for _, fila in datos.iterrows():
        registro = OrderedDict()

        for col in datos.columns:
            valor = safe_json_value(fila[col])
            registro[col] = valor

        registros.append(registro)

    # Ordenar por código
    registros.sort(key=lambda r: r["cod_municipio"])

    # --------------------------------------------------
    # 8. Escribir archivo
    # --------------------------------------------------
    output_path = project_root / "frontend-IA" / "src" / "data" / "tasas_municipales_2021.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False, indent=2)

    print(f"\n   [OK] Archivo generado: {output_path}")
    print(f"   [OK] Total de registros: {len(registros)}")

    # --------------------------------------------------
    # 9. Resumen final
    # --------------------------------------------------
    print("\n" + "=" * 60)
    print("RESUMEN FINAL")
    print("=" * 60)
    print(f"Total municipios en datos: {len(datos)}")
    print(f"Municipios con datos DANE: {(datos['estado_dane'] == 'con_datos').sum()}")
    print(f"Municipios sin datos DANE: {(datos['estado_dane'] == 'sin_datos_dane').sum()}")
    print(f"Municipios con tasa calculada: {len(tasas_validas)}")
    print(f"Municipios sin tasa (NaN/null): {tasas.isna().sum()}")

    if topojson_codigos is not None:
        print(f"\nCorrespondencia con TopoJSON:")
        print(f"  En datos y TopoJSON: {len(datos_codigos & topojson_codigos)}")
        print(f"  Solo en datos: {len(sin_correspondencia_topo)}")
        print(f"  Solo en TopoJSON: {len(sin_correspondencia_datos)}")

    print(f"\nEstadísticas DANE:")
    for clave, valor in estadisticas.items():
        print(f"  {clave}: {valor}")

    print("\n[OK] Generación completada exitosamente")


if __name__ == "__main__":
    main()
