---
sessionId: session-261115-091211-1jup
---

# Revisión metodológica complementaria — Auditoría técnica y metodológica

## Resumen de correcciones respecto a la auditoría inicial

Esta revisión corrige y complementa la auditoría inicial. Los hallazgos principales son:

1. **CAU_HOMOL sí existe** en el CSV DANE con códigos de la Lista 105 Colombia. La auditoría inicial afirmó erróneamente que no estaba disponible.
2. **A_DEFUN se interpretó incorrectamente.** No es "Ambiente de defunción" sino "Área donde ocurrió la defunción", con categorías 1=Cabecera municipal, 2=Centro poblado, 3=Rural disperso, 9=Sin información. La auditoría inicial interpretó A_DEFUN=1 como "Domicilio", lo cual es falso.
3. **SIT_DEFUN tiene 7 categorías** para el sitio físico de defunción, no solo 3.
4. **AREA_RES se interpretó incorrectamente.** Las categorías son 1=Urbana, 2=Intermedia, 3=Rural, no las que se afirmaron.
5. **Los duplicados RIPS tienen implicaciones cuantificables** que requieren análisis de sensibilidad.
6. **La Lista 105 Colombia existe** como documento oficial del DANE (archivo Excel disponible en `https://www.dane.gov.co/files/investigaciones/poblacion/defunciones/Lista_105_Colombia_CIE9-y-CIE10.xls`).
7. **El INS Informe 15** ("Cuando la muerte es evitable") proporciona una metodología de mortalidad evitable con listas de causas susceptibles de atención médica.

---

# 1. Inventario del Repositorio (sin cambios)

El inventario del repositorio permanece igual que en la auditoría inicial. Los archivos, módulos, notebooks, EDA y reportes relevantes son los mismos.

**Corrección:** La afirmación "No existe clasificación Lista 105 de mortalidad evitable" es parcialmente incorrecta. La Lista 105 Colombia existe como documento oficial del DANE (archivo Excel descargable). Sin embargo, no existe en el repositorio local ni una tabla de correspondencia entre los códigos CAU_HOMOL y las causas susceptibles de atención médica del INS.

# 2. Estado Actual del Procesamiento (sin cambios)

El estado del procesamiento permanece igual que en la auditoría inicial.

---

# 3. Correcciones de hallazgos de los EDA

## 3.1 CAU_HOMOL — Hallazgo nuevo

**Hallazgo comprobado:** La columna `CAU_HOMOL` existe en el CSV DANE y contiene códigos de la Lista 105 Colombia. La auditoría inicial afirmó erróneamente que no estaba disponible.

**Descripción oficial (DANE):** "Causa básica agrupada con base en la Lista 105 Colombia".

**Frecuencias principales (del EDA):**
| Código | Registros | % |
|--------|-----------|---|
| 010 | 91,284 | 25.14% |
| 051 | 52,824 | 14.55% |
| 055 | 17,331 | 4.77% |
| 101 | 14,457 | 3.98% |
| 060 | 12,379 | 3.41% |
| 050 | 11,913 | 3.28% |
| 059 | 10,747 | 2.96% |
| 041 | 10,259 | 2.83% |
| 090 | 7,779 | 2.14% |

**Códigos distintos observados:** Al menos 30 códigos distintos (los 20 principales se muestran arriba).

**Relación con C_BAS1 y CAUSA_667:**
- `C_BAS1`: Código de la causa básica de la defunción (CIE-10 completo).
- `CAUSA_667`: Causa agrupada con base en la Lista 6/67 de la OPS (CIE-10).
- `CAU_HOMOL`: Causa básica agrupada con base en la Lista 105 Colombia.

Las tres variables representan la misma información a diferentes niveles de agrupación. CAU_HOMOL es la más agregada (105 categorías) y la más directamente alineada con la estadística oficial colombiana.

**Importancia metodológica:** La Lista 105 Colombia es el estándar oficial para tabulación de mortalidad en Colombia. Los códigos incluyen grupos como:
- 01-10: Enfermedades infecciosas y parasitarias
- 11-38: Tumores
- 39-48: Enfermedades del aparato circulatorio
- 49-58: Enfermedades del aparato respiratorio
- 59-66: Enfermedades del aparato digestivo
- 67-78: Enfermedades del aparato genitourinario
- 79-88: Enfermedades del aparato osteomuscular y tejido conjuntivo
- 89-90: Enfermedades externas
- 91-105: Otras causas

**Limitación:** No todos los códigos de la Lista 105 son causas evitables. Se requiere la correspondencia del INS Informe 15 para identificar cuáles son susceptibles de atención médica.

## 3.2 Corrección de A_DEFUN

**Interpretación incorrecta de la auditoría inicial:** "A_DEFUN (Ambiente de defunción): 1=Domicilio (331,689, 91.35%), 3=EPS/Hospital (23,197), 2=Otro (7,917)".

**Interpretación correcta (DANE microdatos):**

| Código | Categoría | Registros | % |
|--------|-----------|-----------|---|
| 1 | Cabecera municipal | 331,689 | 91.35% |
| 2 | Centro poblado (Inspección, corregimiento o caserío) | 7,917 | 2.18% |
| 3 | Rural disperso | 23,197 | 6.39% |
| 9 | Sin información | 286 | 0.08% |

**Corrección:** A_DEFUN=1 significa "Cabecera municipal", no "Domicilio". La variable describe el área geográfica donde ocurrió la defunción, no el sitio físico.

## 3.3 Corrección de SIT_DEFUN

**Interpretación incorrecta de la auditoría inicial:** "SIT_DEFUN (Sitación): 1=Hospital (249,752, 68.78%), 3=Domicilio (90,605, 24.95%)".

**Interpretación correcta (DANE microdatos):**

| Código | Categoría | Registros | % |
|--------|-----------|-----------|---|
| 1 | Hospital/clínica | 249,752 | 68.78% |
| 2 | Centro/puesto de salud | 1,622 | 0.45% |
| 3 | Casa/domicilio | 90,605 | 24.95% |
| 4 | Lugar de trabajo | 952 | 0.26% |
| 5 | Vía pública | 11,613 | 3.20% |
| 6 | Otro | 7,399 | 2.04% |
| 9 | Sin información | 1,146 | 0.32% |

**Corrección:** SIT_DEFUN tiene 7 categorías, no 3. La auditoría inicial omitió las categorías 2, 4, 5 y 6.

## 3.4 Corrección de AREA_RES

**Interpretación incorrecta de la auditoría inicial:** "AREA_RES: 1=Urbana (299,331, 82.44%), 3=Rural (45,269, 12.47%), 2=Intermedia (16,087, 4.43%)".

**Interpretación correcta:** Las categorías son correctas en número pero la descripción era imprecisa. AREA_RES describe el área de residencia habitual del fallecido:

| Código | Categoría | Registros | % |
|--------|-----------|-----------|---|
| 1 | Urbana | 299,331 | 82.44% |
| 2 | Intermedia | 16,087 | 4.43% |
| 3 | Rural | 45,269 | 12.47% |
| (vacío) | — | 1,931 | 0.53% |
| 9 | Sin información | 471 | 0.13% |

Esta interpretación era correcta en la auditoría inicial. Sin embargo, las variables derivadas `dane_area_rural` y `dane_pct_rural` deben usar AREA_RES=3, no A_DEFUN=3.

## 3.5 Variables derivadas afectadas

Las siguientes variables de la auditoría inicial deben corregirse:

- **`dane_defunciones_domicilio`**: Se calculaba como A_DEFUN=1, lo cual contaba defunciones en cabecera municipal, no en domicilio. **Corrección:** Usar SIT_DEFUN=3 para defunciones en casa/domicilio.
- **`dane_pct_domicilio`**: Derivado del error anterior. **Corrección:** `dane_defunciones_domicilio / dane_defunciones_totales` usando SIT_DEFUN=3.
- **`dane_defunciones_hospital`**: Se calculaba correctamente como SIT_DEFUN=1.
- **`dane_pct_hospital`**: Correcto.
- **`dane_area_rural`**: Se calculaba como AREA_RES=3, lo cual es correcto para residentes en área rural. Pero si se quiere defunciones ocurridas en área rural, usar A_DEFUN=3.

## 3.6 Duplicados RIPS — Análisis de sensibilidad

**Hallazgos adicionales del EDA:**
- Filas excedentes por duplicados exactos: 1,183,160 (33.16% del total).
- Filas en algún grupo repetido (clave de 5 dimensiones): 2,089,523 (58.57%).
- Filas si se conservara una por grupo exacto: 2,384,496.
- Los excedentes exactos coinciden con los excedentes por clave de 5 dimensiones, lo que significa que todos los duplicados tienen idéntico `NumeroAtenciones`.

**Implicación:** Al deduplicar, se reduciría la suma total de atenciones proporcionalmente. El análisis de sensibilidad del EDA calculó esta variación pero los resultados numéricos no están en los archivos de salida (se muestran con `display()`).

**Recomendación:** Conservar los duplicados pero documentar explícitamente que los indicadores RIPS incluyen filas duplicadas. Implementar una opción de deduplicación como alternativa configurable.

# 4. Diccionario de Variables Candidatas — Versión corregida

## Variables que deben eliminarse o corregirse

| Variable | Problema | Acción |
|----------|----------|--------|
| `dane_defunciones_domicilio` | Se calculaba como A_DEFUN=1 (cabecera municipal), no domicilio | **Eliminar y reemplazar** por variable basada en SIT_DEFUN=3 |
| `dane_pct_domicilio` | Derivado del error anterior | **Eliminar y reemplazar** |
| `dane_defunciones_circulatorias` (C_BAS1) | Mejor usar CAU_HOMOL | **Reemplazar** por versión basada en CAU_HOMOL |
| `dane_defunciones_respiratorias` (C_BAS1) | Mejor usar CAU_HOMOL | **Reemplazar** por versión basada en CAU_HOMOL |
| `dane_defunciones_externas` (C_BAS1) | Mejor usar CAU_HOMOL | **Reemplazar** por versión basada en CAU_HOMOL |
| `dane_area_rural` | Ambigua: no distingue residencia vs ocurrencia | **Reemplazar** por variables específicas |
| `dane_pct_rural` | Ambigua | **Reemplazar** por variables específicas |

## Variables nuevas propuestas

| Nombre propuesto | Descripción | Fuente | Variable original | Fórmula | Tipo | Tratamiento ausentes | Uso | Limitaciones |
|-----------------|-------------|--------|-------------------|---------|------|---------------------|-----|-------------|
| `dane_defunciones_cabecera` | Defunciones en cabecera municipal | DANE | `A_DEFUN` | `count` donde A_DEFUN='1' | int64 | 0 | Descriptiva | Área geográfica, no sitio físico |
| `dane_pct_cabecera` | Proporción en cabecera municipal | DANE | Derivado | `dane_defunciones_cabecera / dane_defunciones_totales` | float64 | NaN si total=0 | Descriptiva | — |
| `dane_defunciones_rural_ocurrencia` | Defunciones en rural disperso (ocurrencia) | DANE | `A_DEFUN` | `count` donde A_DEFUN='3' | int64 | 0 | Descriptiva | — |
| `dane_pct_rural_ocurrencia` | Proporción en rural disperso | DANE | Derivado | `dane_defunciones_rural_ocurrencia / dane_defunciones_totales` | float64 | NaN si total=0 | Descriptiva | — |
| `dane_defunciones_domicilio` | Defunciones en casa/domicilio (sitio físico) | DANE | `SIT_DEFUN` | `count` donde SIT_DEFUN='3' | int64 | 0 | Descriptiva | Sitio físico, no área geográfica |
| `dane_pct_domicilio` | Proporción en casa/domicilio | DANE | Derivado | `dane_defunciones_domicilio / dane_defunciones_totales` | float64 | NaN si total=0 | Descriptiva | — |
| `dane_defunciones_centro_salud` | Defunciones en centro/puesto de salud | DANE | `SIT_DEFUN` | `count` donde SIT_DEFUN='2' | int64 | 0 | Descriptiva | Nueva variable |
| `dane_pct_centro_salud` | Proporción en centro/puesto de salud | DANE | Derivado | `dane_defunciones_centro_salud / dane_defunciones_totales` | float64 | NaN si total=0 | Descriptiva | — |
| `dane_defunciones_via_publica` | Defunciones en vía pública | DANE | `SIT_DEFUN` | `count` donde SIT_DEFUN='5' | int64 | 0 | Descriptiva | Nueva variable |
| `dane_pct_via_publica` | Proporción en vía pública | DANE | Derivado | `dane_defunciones_via_publica / dane_defunciones_totales` | float64 | NaN si total=0 | Descriptiva | — |
| `dane_area_rural_residencia` | Defunciones de residentes en área rural | DANE | `AREA_RES` | `count` donde AREA_RES='3' | int64 | 0 | Descriptiva | Residencia, no ocurrencia |
| `dane_pct_rural_residencia` | Proporción de residentes rurales | DANE | Derivado | `dane_area_rural_residencia / dane_defunciones_totales` | float64 | NaN si total=0 | Descriptiva | — |
| `dane_defunciones_circulatorias_homol` | Defunciones por causas circulatorias (CAU_HOMOL 39-48) | DANE | `CAU_HOMOL` | `count` donde CAU_HOMOL entre '039' y '048' | int64 | 0 | Descriptiva | Agrupación por rango Lista 105 |
| `dane_pct_circulatorias_homol` | Proporción de causas circulatorias | DANE | Derivado | `dane_defunciones_circulatorias_homol / dane_defunciones_totales` | float64 | NaN si total=0 | Descriptiva | — |
| `dane_defunciones_respiratorias_homol` | Defunciones por causas respiratorias (CAU_HOMOL 49-58) | DANE | `CAU_HOMOL` | `count` donde CAU_HOMOL entre '049' y '058' | int64 | 0 | Descriptiva | — |
| `dane_pct_respiratorias_homol` | Proporción de causas respiratorias | DANE | Derivado | `dane_defunciones_respiratorias_homol / dane_defunciones_totales` | float64 | NaN si total=0 | Descriptiva | — |
| `dane_defunciones_externas_homol` | Defunciones por causas externas (CAU_HOMOL 89-90) | DANE | `CAU_HOMOL` | `count` donde CAU_HOMOL entre '089' y '090' | int64 | 0 | Descriptiva | — |
| `dane_pct_externas_homol` | Proporción de causas externas | DANE | Derivado | `dane_defunciones_externas_homol / dane_defunciones_totales` | float64 | NaN si total=0 | Descriptiva | — |

## Variables heredadas de la auditoría inicial (sin cambios)

Las siguientes variables permanecen sin cambios:
- `cod_dpto`, `cod_municipio`, `departamento`, `municipio` (identificación geográfica).
- `rips_total_atenciones`, `rips_consultas`, `rips_procedimientos`, `rips_urgencias`, `rips_hospitalizaciones`.
- `rips_pct_consultas`, `rips_pct_procedimientos`, `rips_pct_urgencias`, `rips_pct_hospitalizaciones`.
- `rips_participacion_nacional`.
- `dane_defunciones_totales`, `dane_defunciones_con_asistencia`, `dane_defunciones_sin_asistencia`.
- `dane_defunciones_ignoradas`, `dane_defunciones_sin_info`, `dane_respuestas_validas`.
- `dane_pct_sin_asistencia`, `dane_pct_con_asistencia`.
- `dane_defunciones_u071`, `dane_pct_u071`, `dane_defunciones_no_u071`.
- `dane_defunciones_hospital`, `dane_pct_hospital` (correctos, basados en SIT_DEFUN=1).
- `dane_participacion_nacional`.
- `tiene_dane`, `tiene_rips`, `dane_registros_usados`, `rips_registros_usados`, `informacion_suficiente`.

---

# 5. Diseño del Dataset Municipal Final — Versión corregida

**Unidad de análisis:** Una fila por municipio para el año 2021.

**Corrección sobre integración geográfica:**

La auditoría inicial recomendó usar exclusivamente `COD_MUNIC` (ocurrencia) de DANE. Esta revisión propone:

1. **Preparar dos agregaciones independientes de DANE:**
   - Por municipio de residencia (`CODMUNRE`).
   - Por municipio de ocurrencia (`COD_MUNIC`).
2. **Comparar cobertura y distribución** antes de decidir.
3. **No forzar una única integración** hasta poder justificarla con evidencia.

**Formato de Municipio en RIPS:** El campo `Municipio` tiene formato `CODIGO - NOMBRE` (ej. `11001 - Bogotá, D.C.`). El código municipal de 5 dígitos se construye concatenando el código de departamento (2 dígitos) + código de municipio (3 dígitos). El EDA verificó que el prefijo de 2 dígitos del código municipal coincide con el código de departamento en todas las filas.

**Total estimado:** ~50 columnas por municipio (aumentado desde ~37 debido a nuevas variables).

---

# 6. Reevaluación de la Variable Objetivo

## Alternativa A: Proporción de defunciones sin asistencia médica (ASIS_MED)

**Qué representa:** Proporción de defunciones donde se registró que la persona no recibió asistencia médica durante el proceso que llevó a la muerte.

**Fórmula:**
```
dane_pct_sin_asistencia = dane_defunciones_sin_asistencia / dane_respuestas_validas
target = 1 si dane_pct_sin_asistencia >= umbral Y dane_respuestas_validas >= MIN_OBSERVACIONES
target = 0 si dane_pct_sin_asistencia < umbral Y dane_respuestas_validas >= MIN_OBSERVACIONES
target = NaN si dane_respuestas_validas < MIN_OBSERVACIONES
```

**Predictores candidatos:** Proporciones de tipos de atención RIPS, proporciones de causas de muerte (CAU_HOMOL), proporción de defunciones en domicilio, proporción rural, proporción COVID-19.

**Filtración de información:** `dane_pct_sin_asistencia` y `dane_pct_con_asistencia` no pueden ser predictores. Ni `dane_defunciones_sin_asistencia`, `dane_defunciones_con_asistencia`, ni `dane_respuestas_validas`.

**Limitaciones:**
- No es mortalidad evitable en sentido clínico.
- La ausencia de asistencia no implica que la muerte fuera evitable.
- La pandemia (U071 = 23.22%) sesga los patrones.

**Alineación con el proyecto:** Parcial. Mide un aspecto del acceso a atención, pero no la calidad ni la oportunidad.

## Alternativa B: Proporción de defunciones por causas susceptibles de atención médica (CAU_HOMOL + INS)

**Qué representa:** Proporción de defunciones cuyas causas básicas están clasificadas como susceptibles de atención médica según la metodología del INS.

**Fórmula:**
```
dane_defunciones_susceptibles = count donde CAU_HOMOL está en la lista de causas susceptibles del INS
dane_pct_susceptibles = dane_defunciones_susceptibles / dane_defunciones_totales
target = 1 si dane_pct_susceptibles >= umbral Y dane_defunciones_totales >= MIN_OBSERVACIONES
target = 0 si dane_pct_susceptibles < umbral Y dane_defunciones_totales >= MIN_OBSERVACIONES
target = NaN si dane_defunciones_totales < MIN_OBSERVACIONES
```

**Predictores candidatos:** Proporciones de tipos de atención RIPS, `dane_pct_sin_asistencia`, proporción de defunciones en domicilio, proporción rural, proporción COVID-19.

**Filtración de información:** `dane_pct_susceptibles` y sus componentes no pueden ser predictores. Las proporciones de grupos de causa CAU_HOMOL que solapan con la lista de susceptibles tampoco.

**Limitaciones:**
- **Requiere la tabla de correspondencia del INS Informe 15** entre códigos CAU_HOMOL y causas susceptibles de atención médica. Esta tabla no existe en el repositorio.
- El INS Informe 15 usa listas de causas basadas en CIE-10, no directamente en códigos de la Lista 105. Se requiere mapear.
- Algunas causas susceptibles requieren considerar edad del fallecido (`GRU_ED1`, `GRU_ED2`).

**Alineación con el proyecto:** Alta. Es la definición más cercana a "mortalidad evitable" con base en documentación oficial.

## Comparación

| Criterio | Alternativa A (ASIS_MED) | Alternativa B (CAU_HOMOL + INS) |
|----------|--------------------------|----------------------------------|
| Implementable ahora | ✅ Sí | ❌ Requiere tabla de correspondencia |
| Base documental | ASIS_MED es variable oficial | INS Informe 15 es referencia oficial |
| Alineación con objetivo | Parcial | Alta |
| Filtración de información | Fácil de controlar | Compleja (solapamiento con predictores) |
| Distribución de clases | ~75/25 con percentil 75 | Desconocida sin tabla |
| Viabilidad de entrenamiento | ~1,000 municipios | ~1,000 municipios |

## Recomendación

**Alternativa A como solución inmediata:** Usar `dane_pct_sin_asistencia` como variable objetivo provisional, con la etiqueta correcta: "proporción de defunciones sin asistencia médica registrada", no "mortalidad evitable".

**Alternativa B como objetivo a mediano plazo:** Incorporar la tabla de correspondencia del INS Informe 15 para construir una variable basada en causas susceptibles de atención médica. Esto requiere:
1. Descargar el INS Informe 15 completo.
2. Extraer la lista de causas susceptibles de atención médica.
3. Mapear los códigos CIE-10 de la lista a los códigos CAU_HOMOL de la Lista 105.
4. Considerar restricciones de edad si aplica.

**No denominar "mortalidad evitable" a la proporción de defunciones sin asistencia médica.** Son conceptos diferentes.

---

# 7. Perfiles Territoriales y Prioridades — Versión corregida

## Correcciones respecto a la auditoría inicial

Los perfiles iniciales usaban `dane_defunciones_domicilio` calculado incorrectamente. Con las variables corregidas, los perfiles se reformulan:

### Perfil 1: Sin señales de alerta detectadas
- `dane_pct_sin_asistencia` < percentil 50
- `dane_defunciones_totales` >= MIN_OBSERVACIONES
- `informacion_suficiente` = True
- **Recomendación:** Continuar monitoreo rutinario.

### Perfil 2: Baja actividad registrada compatible con baja demanda
- `rips_total_atenciones` < percentil 25 nacional
- `dane_defunciones_totales` < percentil 25 nacional
- `dane_pct_sin_asistencia` < percentil 50
- **Recomendación:** Verificar si la baja actividad refleja baja demanda real o subregistro.

### Perfil 3: Posibles barreras de acceso
- `rips_total_atenciones` < percentil 33 nacional (tercil inferior)
- `dane_pct_sin_asistencia` >= percentil 66 nacional (tercil superior)
- `dane_defunciones_totales` >= MIN_OBSERVACIONES
- **Recomendación:** Investigar acceso a servicios de salud, cobertura de EPS, y disponibilidad de talento humano.

### Perfil 4: Posible presión asistencial
- `rips_total_atenciones` > percentil 66 nacional
- `rips_pct_urgencias` > percentil 66 nacional
- `dane_defunciones_totales` > percentil 66 nacional
- **Recomendación:** Analizar concentración de demanda, capacidad instalada y tiempos de espera.

### Perfil 5: Información insuficiente
- `informacion_suficiente` = False
- O `dane_defunciones_totales` < MIN_OBSERVACIONES
- **Recomendación:** No emitir clasificación. Priorizar recolección de datos.

## Advertencias metodológicas

- Los perfiles son **señales**, no diagnósticos.
- No demuestran colapso del sistema ni falta de talento humano.
- No confundir:
  - Atenciones con pacientes.
  - Conteos absolutos con demanda relativa.
  - Actividad elevada con saturación.
  - Defunciones sin asistencia con barreras de acceso demostradas.
- Los perfiles pueden ser simultáneos.
- Sin datos de personal, capacidad instalada, ocupación ni tiempos de espera.

## Niveles de prioridad

| Nivel | Regla | Justificación |
|-------|-------|---------------|
| **Alta** | Perfil 3 con `dane_pct_sin_asistencia` > percentil 75 | Señal fuerte de posible falta de acceso |
| **Media** | Perfil 3 con `dane_pct_sin_asistencia` entre percentil 66 y 75, o Perfil 4 | Señales moderadas |
| **Baja** | Perfil 1 o 2 | Sin señales preocupantes |

## Protección contra clasificación con pocos datos

- Municipios con `dane_respuestas_validas < MIN_OBSERVACIONES` se marcan como "información insuficiente".
- Los percentiles se calculan solo sobre municipios con información suficiente.
- Un municipio con 10 defunciones y 9 sin asistencia (90%) tiene la misma clasificación que uno con 1,000 defunciones y 400 sin asistencia (40%) si ambos superan el umbral. **Esta limitación debe documentarse explícitamente.**

---

# 8. Diseño de los Dos Modelos — Versión corregida

## Correcciones respecto a la auditoría inicial

### Variables predictoras actualizadas

**Predictores de RIPS (proporciones):**
- `rips_pct_consultas`, `rips_pct_procedimientos`, `rips_pct_urgencias`, `rips_pct_hospitalizaciones`
- `rips_participacion_nacional`

**Predictores de DANE (proporciones, excluyendo la variable objetivo):**
- `dane_pct_sin_asistencia` → **EXCLUIDO** si es la variable objetivo.
- `dane_pct_con_asistencia` → **EXCLUIDO.** Derivado del objetivo.
- `dane_pct_domicilio` (basado en SIT_DEFUN=3, corregido)
- `dane_pct_hospital` (basado en SIT_DEFUN=1, correcto)
- `dane_pct_centro_salud` (nueva variable)
- `dane_pct_via_publica` (nueva variable)
- `dane_pct_rural_residencia` (corregido, basado en AREA_RES=3)
- `dane_pct_rural_ocurrencia` (nueva variable, basada en A_DEFUN=3)
- `dane_pct_u071`
- `dane_pct_circulatorias_homol` (basado en CAU_HOMOL, reemplaza versión C_BAS1)
- `dane_pct_respiratorias_homol` (basado en CAU_HOMOL, reemplaza versión C_BAS1)
- `dane_pct_externas_homol` (basado en CAU_HOMOL, reemplaza versión C_BAS1)
- `dane_defunciones_totales` → **INCLUIDO con precaución.**

**Total de predictores:** ~15 variables (aumentado desde ~12).

### Filtración de información

**Variables excluidas por filtración:**
- `dane_pct_sin_asistencia`: Es la variable objetivo misma.
- `dane_pct_con_asistencia`: Derivada del objetivo.
- `dane_defunciones_sin_asistencia`: Componente del numerador.
- `dane_defunciones_con_asistencia`: Componente del denominador.
- `dane_respuestas_validas`: Denominador del objetivo.

**Riesgo residual:** `dane_defunciones_totales` correlacionado con estabilidad del objetivo. Mitigado con `MIN_OBSERVACIONES`.

### Algoritmos, particiones y métricas

Sin cambios respecto a la auditoría inicial:
- Regresión logística regularizada (L2) y árbol de decisión.
- Particiones: 70% entrenamiento, 15% validación, 15% prueba.
- Métricas prioritarias: PR-AUC, F1-score, Recall, Precision.

---

# 9. Riesgos Metodológicos y Técnicos — Versión corregida

## Riesgos nuevos o actualizados

### CAU_HOMOL sin tabla de correspondencia completa
- **Riesgo:** Los rangos de códigos CAU_HOMOL que proponemos (01-10, 39-48, 49-58, 89-90) se basan en la estructura general de la Lista 105 Colombia. Sin embargo, sin el archivo Excel completo, no podemos verificar que todos los códigos dentro de cada rango correspondan exactamente a las categorías descritas.
- **Mitigación:** Descargar y verificar el archivo `Lista_105_Colombia_CIE9-y-CIE10.xls` del DANE antes de implementar.

### INS Informe 15 sin tabla de correspondencia
- **Riesgo:** El INS Informe 15 define causas susceptibles de atención médica usando códigos CIE-10, no códigos CAU_HOMOL. Mapear entre CIE-10 y Lista 105 requiere la tabla oficial del DANE.
- **Mitigación:** Descargar ambos documentos y construir la correspondencia manualmente.

### Duplicados RIPS
- **Riesgo:** 1,183,160 filas excedentes (33.16%) afectan las sumas de `NumeroAtenciones`.
- **Hallazgo nuevo:** Los excedentes exactos coinciden con los excedentes por clave de 5 dimensiones, lo que significa que todos los duplicados tienen idéntico `NumeroAtenciones`. Esto sugiere que son errores de extracción, no datos legítimos con valores diferentes.
- **Recomendación actualizada:** **Deduplicar antes de agregar** es la opción más defendible, dado que los duplicados tienen valores idénticos. Sin embargo, documentar ambas opciones.

### Interpretación incorrecta de variables
- **Riesgo:** La auditoría inicial interpretó incorrectamente A_DEFUN, lo que habría producido indicadores erróneos.
- **Mitigación:** Todas las variables corregidas en esta revisión.

### Riesgos heredados (sin cambios)
- Denominadores ausentes (sin población municipal).
- Datos faltantes (C_MUERTEE vacía, sin mes en RIPS).
- Cobertura desigual (Bogotá domina).
- Limitaciones ecológicas.
- Pandemia (U071).
- Número de observaciones (~1,000 municipios).
- Correspondencia geográfica (RIPS no distingue residencia vs prestación).

---

# 10. Plan de Implementación — Versión corregida

## Cambios respecto a la auditoría inicial

**Paso adicional 0: Verificar correspondencias oficiales**
- Descargar `Lista_105_Colombia_CIE9-y-CIE10.xls` del DANE.
- Descargar INS Informe 15 completo.
- Construir tabla de correspondencia entre códigos CAU_HOMOL y categorías de la Lista 105.
- Construir tabla de correspondencia entre causas susceptibles del INS y códigos CAU_HOMOL.
- **Dependencias:** Ninguna.

**Paso adicional entre 3 y 4: Comparar agregaciones geográficas**
- Preparar agregación de DANE por municipio de residencia.
- Preparar agregación de DANE por municipio de ocurrencia.
- Comparar cobertura, distribución y solapamiento con RIPS.
- Documentar ventajas y limitaciones de cada alternativa.
- **Dependencias:** Paso 3 (homologación geográfica).

**Paso 5 actualizado: Agregación municipal de RIPS con deduplicación**
- Implementar opción de deduplicación antes de agregar.
- Calcular indicadores con y sin deduplicación.
- Documentar diferencias.
- **Dependencias:** Paso 3.

**Paso 4 actualizado: Agregación municipal de DANE con variables corregidas**
- Usar SIT_DEFUN=3 para defunciones en domicilio.
- Usar A_DEFUN=3 para defunciones en rural disperso.
- Usar AREA_RES=3 para residentes en área rural.
- Usar CAU_HOMOL para agrupaciones de causas.
- **Dependencias:** Paso 0, Paso 3.

Los demás pasos permanecen sin cambios.

---

# 11. Decisiones Pendientes — Versión corregida

## Decisiones que requieren aprobación humana

**1. Variable objetivo: ¿ASIS_MED o CAU_HOMOL + INS?**
- **Importancia:** Define todo el diseño del modelo y la interpretación de resultados.
- **Alternativa A (recomendada para implementación inmediata):** Usar `dane_pct_sin_asistencia` como proxy provisional. Implementable ahora. Etiquetar correctamente como "proporción de defunciones sin asistencia médica registrada".
- **Alternativa B (recomendada para versión definitiva):** Construir variable basada en causas susceptibles de atención médica usando CAU_HOMOL + INS Informe 15. Requiere tabla de correspondencia faltante.

**2. Deduplicación de RIPS**
- **Importancia:** 1,183,160 filas excedentes (33.16%) afectan significativamente las sumas.
- **Hallazgo nuevo:** Todos los duplicados tienen idéntico `NumeroAtenciones`, lo que sugiere errores de extracción.
- **Alternativa A (recomendada, cambiada desde auditoría inicial):** Deduplicar antes de agregar. Los duplicados son errores de extracción, no datos legítimos.
- **Alternativa B:** Conservar duplicados y documentar. Menos defendible dado el hallazgo.

**3. Tratamiento de COVID-19 (U071)**
- **Importancia:** 23.22% del total de defunciones. Sesga patrones de mortalidad y asistencia.
- **Alternativa A (recomendada):** Incluir y controlar con `dane_pct_u071` como predictor.
- **Alternativa B:** Excluir defunciones por U071 del análisis.

**4. Geografía de referencia**
- **Importancia:** Determina qué municipio se asocia con cada defunción.
- **Alternativa A (recomendada):** Usar ocurrencia (`COD_MUNIC`). Más alineado con RIPS (lugar de prestación).
- **Alternativa B:** Usar residencia (`CODMUNRE`). Más alineado con análisis de población residente.
- **Alternativa C (nueva):** Preparar ambas agregaciones y comparar antes de decidir.

**5. Umbral de variable objetivo**
- **Importancia:** Define qué municipios se clasifican como clase positiva.
- **Alternativa A (recomendada):** Percentil 75 de la distribución municipal. Adaptable a los datos.
- **Alternativa B:** Umbral fijo (ej. 30%). Más interpretable pero arbitrario.

**6. MIN_OBSERVACIONES**
- **Importancia:** Determina cuántos municipios se excluyen por información insuficiente.
- **Propuesta:** 10 respuestas válidas de ASIS_MED.
- **Alternativa:** 5 (más inclusivo) o 20 (más conservador).

**7. Modelo de aprendizaje automático**
- **Importancia:** Con ~1,000 observaciones y ~15 predictores, los modelos son viables pero limitados.
- **Pregunta:** ¿Proceder con entrenamiento o priorizar el análisis descriptivo y los perfiles territoriales?
- **Riesgo:** Los modelos pueden sobreajustar con pocos datos y un solo año.

**8. Tabla de correspondencia CAU_HOMOL**
- **Importancia:** Sin ella, las agrupaciones de causas basadas en CAU_HOMOL son aproximaciones.
- **Acción requerida:** Descargar y verificar `Lista_105_Colombia_CIE9-y-CIE10.xls` del DANE.
- **Fuente:** `https://www.dane.gov.co/files/investigaciones/poblacion/defunciones/Lista_105_Colombia_CIE9-y-CIE10.xls`