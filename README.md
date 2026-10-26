# Predicción de riesgo de mortalidad evitable por falta de oportunidad en la atención en zonas rurales

## Descripción

Proyecto académico de análisis de datos y desarrollo de modelos predictivos para investigar la relación entre la mortalidad evitable, la oportunidad de la atención en salud y las condiciones territoriales de las zonas rurales de Colombia.

El proyecto se encuentra en una fase de análisis exploratorio y evaluación de la viabilidad metodológica. El desarrollo del modelo predictivo dependerá de la definición y validación de la variable objetivo, la unidad de análisis y la compatibilidad de las fuentes de datos disponibles.

## Objetivo general

Investigar la viabilidad de desarrollar un modelo predictivo relacionado con el riesgo de mortalidad evitable por falta de oportunidad en la atención en zonas rurales colombianas, mediante el análisis de datos de mortalidad y atención en salud.

La definición operacional del resultado que se desea predecir y la estrategia de integración de las fuentes deberán justificarse antes de iniciar el entrenamiento de los modelos.

## Fuentes de datos

### Estadísticas vitales de defunciones — DANE

Se dispone de un análisis exploratorio de los registros de defunciones no fetales correspondientes a 2021. Este análisis constituye una fuente para caracterizar las defunciones registradas y evaluar las variables disponibles para la investigación.

### Registros Individuales de Prestación de Servicios de Salud — RIPS

Se dispone de un análisis exploratorio de un conjunto de datos de 2021 con 3.567.656 filas y seis columnas.

El análisis identificó limitaciones relacionadas con la ausencia de un diccionario de datos confirmado, la interpretación de la unidad de observación, los registros duplicados, el significado de las cantidades registradas, la interpretación geográfica y la falta de denominadores poblacionales.

Las dos fuentes se analizan inicialmente por separado. Su integración no se considera validada hasta comprobar la compatibilidad de sus unidades de observación, variables geográficas, periodos y demás criterios pertinentes.

## Estado del proyecto

- **Fase 1 — Análisis exploratorio:** se han realizado análisis independientes de DANE y RIPS.
- **Fase 2 — Preparación y modelado:** pendiente de consolidar la definición del problema predictivo, validar los datos disponibles y establecer una estrategia de evaluación.
- **Fase 3 — Despliegue:** previsto como etapa posterior. La tecnología de despliegue y la posible construcción de una API se definirán cuando se conozcan los requisitos del modelo y de su utilización.

## Modelos candidatos

Se consideran inicialmente dos enfoques para una posible tarea de clasificación:

- **Regresión logística:** modelo de referencia (_baseline_).
- **Random Forest:** modelo candidato para comparar su desempeño con el baseline.

Estos modelos son candidatos preliminares. Su implementación y evaluación dependerán de que se disponga de una variable objetivo válida y de datos apropiados para el problema definido.

## Estructura del repositorio

```text
proyecto-mortalidad/
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
└── notebooks/
```

- `data/raw/`: ubicación local de los datos originales.
- `data/interim/`: datos generados durante etapas intermedias.
- `data/processed/`: datos preparados para análisis o modelado.
- `notebooks/`: análisis exploratorios y experimentos desarrollados durante el proyecto.

La estructura se ampliará progresivamente a medida que se incorporen los módulos de procesamiento, entrenamiento, evaluación y despliegue.

## Reproducibilidad y gestión de datos

Los datos originales no se incorporan automáticamente al repositorio. Su versionado dependerá del tamaño, las condiciones de uso y la presencia de información sensible.

Los notebooks y las instrucciones necesarias para reproducir los análisis se incorporarán al repositorio después de revisar sus dependencias, salidas guardadas y referencias a los archivos locales.

## Limitaciones actuales

1. La variable objetivo de mortalidad evitable por falta de oportunidad en la atención aún debe definirse y validarse.
2. No se ha demostrado que las fuentes DANE y RIPS puedan integrarse de manera válida a nivel individual.
3. La interpretación de varias variables de RIPS requiere documentación oficial de la fuente.
4. Los datos analizados corresponden a 2021; no se dispone todavía de una serie temporal validada para estudiar tendencias.
5. Los resultados exploratorios son descriptivos y no demuestran relaciones causales.

## Próximos pasos

1. Documentar y validar las características de las fuentes disponibles.
2. Definir la unidad de análisis y el resultado predictivo de forma metodológicamente justificada.
3. Determinar si las fuentes pueden integrarse y qué variables son adecuadas.
4. Preparar un conjunto de datos reproducible, si la evidencia permite construirlo.
5. Entrenar y comparar los modelos candidatos con métricas apropiadas.
6. Documentar los experimentos y evaluar las alternativas de despliegue.

## Carácter académico

Este repositorio documenta el desarrollo progresivo de un proyecto académico. Las decisiones metodológicas, los resultados y las capacidades del modelo se actualizarán a medida que sean comprobados.
