---
sessionId: session-261115-145400-4kof
---

# Diseno Tecnico y Endpoints

## Estado actual del backend

### Arquitectura

```
src/
├── main.py              # FastAPI: /, /health, POST /datasets/upload
├── loading.py           # Carga CSV desde data/processed/, validacion, reportes JSON
├── validation.py        # Validacion estructural DANE (56 cols) y RIPS (6 cols)
├── quality.py           # Deteccion de duplicados y espacios en Diagnostico
├── schemas.py           # Columnas esperadas, nombres de archivos
├── auth.py              # Autenticacion Keycloak (JWT, rol admin)
├── keycloak_config.py   # Configuracion Keycloak
└── algoritmos.py        # Modelos sklearn (no usados aun)

data/raw/                # CSV subidos via /datasets/upload
data/processed/          # Archivos limpios esperados por loading.py
reports/                  # Reportes JSON de validacion
```

### Flujo actual
1. `POST /datasets/upload` guarda CSV en `data/raw/`. Valida extension, tamaño, estructura CSV.
2. `loading.py` lee de `data/processed/` (no conectado al upload).
3. `validation.py` valida columnas y valores especificos.
4. `quality.py` detecta duplicados y espacios.
5. Reporte JSON se guarda en `reports/`.

### Brechas
- No hay conexion entre `/datasets/upload` y `loading.py`.
- No hay almacenamiento de resultados EDA.
- No hay endpoints para consultar estadisticas.
- No hay modulo de EDA.
- No hay base de datos (todo es archivo plano).

### Componentes reutilizables
| Componente | Reutilizable? |
|------------|---------------|
| `loading.leer_csv()` | Si. Carga CSV con pandas |
| `loading.guardar_reporte()` | Si. Guarda JSON en reports/ |
| `schemas.DANE_COLUMNS` / `RIPS_COLUMNS` | Si. Columnas a analizar |
| `quality.revisar_calidad()` | Si. Hallazgos de calidad |

## Propuesta de arquitectura

### Enfoque: EDA como modulo de generacion de estadisticas

Un nuevo modulo `src/eda.py` que:
1. Recibe un DataFrame ya cargado.
2. Calcula las estadisticas de los notebooks.
3. Devuelve un diccionario JSON-serializable.
4. Los resultados se guardan como JSON en `reports/`.

### Decisiones clave

1. **JSON plano** (no base de datos): Coherente con el patron existente de `reports/`.
2. **Generacion bajo demanda**: Al cargar datos, no en cada consulta. Se invalidan al subir nuevos datos.
3. **Separacion DANE/RIPS**: Dos funciones con estructuras distintas pero compatibles.
4. **Sin dependencias nuevas**: pandas ya se usa en `loading.py`.
5. **Top-10 para frecuencias**: Controlar tamaño de respuesta.

### Estructura JSON de DANE
```json
{
  "dataset": "DANE",
  "generado_en": "2025-01-15T10:30:00",
  "dimensiones": { "filas": 363089, "columnas": 56 },
  "calidad": {
    "duplicados_exactos": 0,
    "nulos_por_columna": { "SEXO": 12 },
    "vacios_por_columna": { "SEXO": 3 }
  },
  "demografico": {
    "sexo": { "1": { "count": 180000, "pct": 49.6 }, "2": { "count": 183089, "pct": 50.4 } },
    "gru_ed1": { ... },
    "est_civil": { ... }
  },
  "geografico": {
    "a_defun": { "1": { "count": 331689, "pct": 91.4 } },
    "sit_defun": { ... },
    "area_res": { ... },
    "top_departamentos": [ { "cod": "11", "count": 120000, "pct": 33.1 } ]
  },
  "causas": {
    "cau_homol_top10": [ { "codigo": "010", "count": 91284, "pct": 25.1 } ],
    "c_bas1_top10": [ ... ],
    "causa_667_top10": [ ... ]
  },
  "asistencia": {
    "asis_med": { "1": { "count": 250000, "pct": 68.9 } }
  }
}
```

### Estructura JSON de RIPS
```json
{
  "dataset": "RIPS",
  "generado_en": "2025-01-15T10:30:00",
  "dimensiones": { "filas": 3567656, "columnas": 6 },
  "calidad": {
    "duplicados_exactos": 1183160,
    "nulos_por_columna": { ... },
    "vacios_por_columna": { ... }
  },
  "numero_atenciones": {
    "validos": 3500000,
    "minimo": 1, "p25": 1, "mediana": 1, "p75": 2, "media": 97, "maximo": 3650
  },
  "univariado": {
    "tipo_atencion": { "Consulta": { "filas": 2000000, "atenciones": 2000000 } },
    "diagnostico_top10": [ { "codigo": "J06.9", "filas": 50000, "atenciones": 50000 } ]
  },
  "geografico": {
    "top_departamentos_filas": [ ... ],
    "top_departamentos_atenciones": [ ... ],
    "departamentos_distintos": 27,
    "municipios_distintos": 1066
  },
  "cruces": {
    "departamento_x_tipo_atencion_top5": [ ... ]
  }
}
```

## Endpoints propuestos

### GET /eda/status
Estado general del EDA.

**Respuesta 200:**
```json
{
  "dane": { "disponible": true, "generado_en": "2025-01-15T10:30:00", "filas": 363089 },
  "rips": { "disponible": false, "generado_en": null, "filas": null }
}
```

### GET /eda/dane
Estadisticas EDA de DANE.

**Respuesta 200:** Estructura JSON de DANE.
**Errores:** 404 (no disponible), 500 (error de lectura).

### GET /eda/rips
Estadisticas EDA de RIPS.

**Respuesta 200:** Estructura JSON de RIPS.
**Errores:** 404 (no disponible), 500 (error de lectura).

### POST /eda/regenerate
Regenera estadisticas EDA. Requiere rol admin.

**Respuesta 200:**
```json
{
  "mensaje": "Estadisticas regeneradas",
  "dane": { "estado": "generado" },
  "rips": { "estado": "no_disponible" }
}
```
**Errores:** 401, 403, 500.

## Archivos a modificar
| Archivo | Cambio |
|---------|--------|
| `src/main.py` | Agregar endpoints GET /eda/status, /eda/dane, /eda/rips, POST /eda/regenerate |
| `src/loading.py` | Llamar a `eda.generar_eda()` despues de validacion exitosa |

## Archivos a crear
| Archivo | Proposito |
|---------|-----------|
| `src/eda.py` | Modulo con `generar_eda_dane(df)`, `generar_eda_rips(df)`, `cargar_eda_stats(dataset)`, `guardar_eda_stats(dataset, stats)` |

## Dependencias adicionales
**Ninguna.** pandas y numpy ya se usan en `loading.py`.

## Riesgos y decisiones pendientes

### Riesgos
1. **Memoria**: DataFrames grandes (3.5M filas RIPS). **Mitigacion:** Top-10 en frecuencias.
2. **Tiempo de generacion**: EDA de RIPS puede tardar minutos. **Decision:** EDA sincrono en `/eda/regenerate`, no en `/datasets/upload`.
3. **Coherencia**: Si el EDA falla, estadisticas antiguas podrian persistir. **Mitigacion:** Eliminar antes de generar.

### Decisiones pendientes
1. **Ejecutar EDA en `/datasets/upload` o solo en `/eda/regenerate`?** Recomendado: solo en `/eda/regenerate`. El upload guarda el archivo; el EDA se dispara explicitamente.
2. **Proteger GET con autenticacion?** Recomendado: si, con `verificar_token`.

# Delivery Steps

### ✓ Step 1: Crear modulo src/eda.py con funciones de calculo de estadisticas
Implementar el modulo EDA con las funciones que calculan las estadisticas extraidas de los notebooks.
- Crear `src/eda.py` con `generar_eda_dane(df)`: dimensiones, nulos/vacios por columna, duplicados, frecuencias de SEXO, GRU_ED1, EST_CIVIL, AREA_RES, A_DEFUN, SIT_DEFUN, ASIS_MED, CAU_HOMOL, C_BAS1, CAUSA_667 (top-10 cada una), top departamentos, cruce A_DEFUN × P_PMAN_IRIS.
- Implementar `generar_eda_rips(df)`: dimensiones, nulos/vacios/espacios por columna, duplicados, estadisticas de NumeroAtenciones (min, P25, mediana, P75, media, max), frecuencias de TipoAtencion y Diagnostico (top-10), distribucion geografica (top departamentos por filas y atenciones), cruces Departamento × TipoAtencion.
- Implementar `cargar_eda_stats(dataset)` para leer JSON desde `reports/`.
- Implementar `guardar_eda_stats(dataset, stats)` reusando el patron de `loading.guardar_reporte()`.
- Limitar todas las frecuencias a top-10 para controlar tamaño de respuesta.
- Usar exclusivamente pandas para mantener coherencia con `loading.py`.

### ✓ Step 2: Integrar EDA en flujo de carga y agregar endpoint /eda/regenerate
Conectar el modulo EDA con el flujo existente y agregar el endpoint de regeneracion.
- Modificar `src/loading.py`: despues de validacion exitosa en `cargar_dataset()`, llamar a `eda.generar_eda()` para el dataset correspondiente.
- Modificar `src/main.py`: agregar `POST /eda/regenerate` (protegido con `requiere_admin`) que regenera las estadisticas EDA para DANE y RIPS.
- Actualizar `POST /datasets/upload` para eliminar estadisticas EDA anteriores al guardar un CSV nuevo (evitar inconsistencia).
- Agregar manejo de errores: si el EDA falla, el upload sigue exitoso pero se registra el error.

### ✓ Step 3: Agregar endpoints GET /eda/status, /eda/dane, /eda/rips
Exponer las estadisticas EDA mediante endpoints REST para consulta del frontend.
- Agregar `GET /eda/status` en `src/main.py`: devuelve disponibilidad de estadisticas de DANE y RIPS (si existen, cuando se generaron, cuantas filas).
- Agregar `GET /eda/dane`: devuelve estadisticas EDA de DANE desde `reports/dane_eda_statistics.json`. Responde 404 si no existen.
- Agregar `GET /eda/rips`: devuelve estadisticas EDA de RIPS desde `reports/rips_eda_statistics.json`. Responde 404 si no existen.
- Proteger todos los endpoints GET con `Depends(verificar_token)` para requerir autenticacion.
- Agregar validacion: si el JSON esta corrupto, responder 500 con mensaje descriptivo.

### ✓ Step 4: Actualizar dependencias y agregar pruebas basicas
Asegurar que las dependencias y pruebas reflejan los cambios.
- Actualizar `requirements.txt` para incluir pandas, numpy, pyjwt y sklearn (ya usados en el codigo pero no declarados).
- Agregar pruebas en `test/test_loading.py` para verificar que `generar_eda_dane()` y `generar_eda_rips()` producen diccionarios con las claves esperadas.
- Agregar pruebas para `cargar_eda_stats()` con archivos JSON de prueba.
- Verificar que los endpoints nuevos responden correctamente con datos de prueba.