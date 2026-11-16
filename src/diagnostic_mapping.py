"""
Homologación CIE-10 a Lista Colombia 105 para la tabulación de mortalidad.

Este módulo contiene las equivalencias verificadas entre códigos CIE-10
y los grupos de causas de la Lista Colombia 105, tal como las publica
el DANE de Colombia.

Fuente oficial:
    DANE - Lista Colombia 105 para la tabulación de mortalidad
    URL: https://www.dane.gov.co/files/investigaciones/poblacion/defunciones/Lista_105_Colombia_CIE9-y-CIE10.xls
    Última consulta: 2026-11-15
    Autor del documento original: PEChaparroN
    Última modificación del documento: 2020-12-15

Fuente complementaria para U07 (COVID-19) — PENDIENTE DE VERIFICACIÓN DOCUMENTAL:
    DANE - Boletín Técnico Estadísticas Vitales (EEVV), II trimestre 2024
    "Colombia agrupa los códigos de COVID-19 dentro del grupo 109
    'Resto de ciertas enfermedades infecciosas y parasitarias',
    de la lista 6/67 para la tabulación de la mortalidad de la CIE-10."
    Los códigos U07.1 (COVID-19, virus identificado) y U07.2
    (COVID-19, virus no identificado) son los establecidos por la OMS/OPS.
    URL: https://www.dane.gov.co/files/operaciones/EEVV/bol-EEVV-Defunciones-IItrim2024.pdf
    Última consulta: 2026-11-15

    Lo que demuestra la fuente:
    - El DANE agrupa U07 en el grupo 109 de la Lista 6/67 OPS para la
      tabulación de defunciones.

    Lo que NO demuestra la fuente:
    - No existe un documento oficial que mapee explícitamente el grupo 109
      de la Lista 6/67 OPS al grupo 010 de la Lista Colombia 105.
    - La correspondencia se infiere porque ambos grupos cubren el residuo
      de A00-B99 ("Todas las demás enfermedades infecciosas y parasitarias"),
      pero esta inferencia no está respaldada por un documento oficial único.

    Estado: Regla complementaria pendiente de verificación documental.
    Se mantiene en el grupo 010 siguiendo la práctica del DANE, pero no
    debe presentarse como equivalencia oficialmente verificada.

Formato CAU_HOMOL:
    El DANE codifica los grupos de la Lista 105 como enteros de 3 dígitos
    con ceros a la izquierda. Por ejemplo:
        Lista 01  -> CAU_HOMOL "001"
        Lista 10  -> CAU_HOMOL "010"
        Lista 105 -> CAU_HOMOL "105"

Uso:
    Las equivalencias se almacenan como rangos y códigos CIE-10 por grupo.
    La función homologar_diagnostico() permite clasificar un código CIE-10
    individual (como los que aparecen en RIPS) al grupo Lista 105 correspondiente.

Notas:
    - La Lista 105 fue diseñada para causas básicas de defunción.
      Su uso para clasificar diagnósticos de atención RIPS es una
      decisión metodológica del proyecto.
    - Los códigos CIE-10 en RIPS pueden tener formato con letra + dígitos
      (ej: "R104", "I10X", "U072"). Se extrae el prefijo alfanumérico
      para la comparación.
    - C50 (Tumor maligno de mama): la Lista 105 distingue "C50, en mujeres"
      (grupo 024) y "C50 en hombres" (grupo 038). Como RIPS no dispone
      de datos de sexo, C50 se clasifica como categoría auxiliar independiente
      (CATEGORIA_C50_AUXILIAR) y no se integra con DANE.
    - Los códigos U07.1 y U07.2 (COVID-19) se asignan al grupo 010 siguiendo
      la práctica del DANE. Esta regla complementaria está pendiente de
      verificación documental: el Boletín Técnico EEVV del DANE confirma
      U07 en el grupo 109 de la Lista 6/67 OPS, pero no existe un documento
      oficial que mapee explícitamente al grupo 010 de la Lista Colombia 105.
"""

# Cada entrada: (cau_homol, descripcion, lista_de_rangos_cie10)
# Los rangos pueden ser:
#   - Un rango: "A00-A09"
#   - Un código individual: "A20"
#   - Un código con subcategoría: "A85.2"
#   - Un rango con subcategoría: "A85.0-A85.1"
#   - Condición especial: "C50, en mujeres"

LISTA_105 = [
    ("001", "Enfermedades infecciosas intestinales", ["A00-A09"]),
    ("002", "Tuberculosis y secuelas", ["A15-A19", "B90"]),
    ("003", "Ciertas enfermedades transmitidas por vectores y rabia",
     ["A20", "A44", "A75-A79", "A82-A84", "A85.2", "A90-A98", "B50-B57"]),
    ("004", "Ciertas enfermedades inmunoprevenibles",
     ["A33-A37", "A80", "B05-B06", "B26", "B91"]),
    ("005", "Septicemia, excepto neonatal", ["A40-A41"]),
    ("006", "Todas las demás enfermedades bacterianas",
     ["A21-A32", "A38-A39", "A42-A43", "A46-A49"]),
    ("007", "Sífilis y otras enfermedades venéreas", ["A50-A64"]),
    ("008", "Hepatitis viral y secuelas", ["B15-B19", "B94.2"]),
    ("009", "Enfermedad por el VIH (SIDA)", ["B20-B24"]),
    ("010", "Todas las demás enfermedades infecciosas y parasitarias",
     ["A65-A74", "A81", "A85.0-A85.1", "A85.8-A89", "A99-B04",
      "B07-B09", "B25", "B27-B49", "B58-B89", "B92-B94.1", "B94.8-B99",
      "U07"]),
    ("011", "Tumores malignos del labio, de la cavidad bucal y de la faringe",
     ["C00-C14"]),
    ("012", "Tumor maligno del esófago", ["C15"]),
    ("013", "Tumor maligno del estómago", ["C16"]),
    ("014", "Tumores malignos de colon, recto y ano", ["C18-C21"]),
    ("015", "Tumor maligno del hígado", ["C22"]),
    ("016", "Tumores malignos de páncreas y de vías biliares", ["C23-C24"]),
    ("017", "Tumor maligno de hígado, excepto células", ["C25"]),
    ("018", "Tumores malignos de otros órganos digestivos",
     ["C17", "C26", "C48"]),
    ("019", "Tumor maligno de tráquea, bronquio y pulmón", ["C32"]),
    ("020", "Tumores malignos de pleura y de otros sitios mal definidos",
     ["C33-C34"]),
    ("021", "Tumores malignos de otros órganos respiratorios",
     ["C30-C31", "C37-C39"]),
    ("022", "Tumores malignos de huesos y cartílagos articulares",
     ["C40-C41"]),
    ("023", "Tumores malignos de otros tejidos conjuntivos y del tejido blando",
     ["C43-C44"]),
    ("024", "Tumor maligno de mama, en mujeres", ["C50, en mujeres"]),
    ("025", "Tumor maligno del cuello del útero", ["C53"]),
    ("026", "Tumores malignos de otros órganos uterinos", ["C54-C55"]),
    ("027", "Tumor maligno de ovario", ["C56"]),
    ("028", "Tumor maligno de próstata", ["C61"]),
    ("029", "Tumor maligno de vejiga urinaria", ["C67"]),
    ("030", "Tumores malignos de riñón, excepto pelvis renal",
     ["C64-C66", "C68"]),
    ("031", "Tumores malignos de otros órganos urinales", ["C69-C72"]),
    ("032", "Tumores malignos de glándula tiroides", ["C73-C75"]),
    ("033", "Tumores malignos de otros órganos endocrinos", ["C76-C79"]),
    ("034", "Tumor maligno primario de sitio no especificado", ["C80"]),
    ("035", "Tumores malignos de órganos linfáticos, hematopooyéticos y relacionados",
     ["C91-C95"]),
    ("036", "Tumores malignos de otros y sitios no especificados",
     ["C81-C85", "C88-C90", "C96"]),
    ("037", "Tumores de comportamiento no especificado, incierto o desconocido",
     ["D00-D48"]),
    ("038", "Tumores malignos de otros sitios",
     ["C45-C47", "C49", "C50 en hombres", "C51-C52", "C57-C58", "C60", "C62-C63", "C97"]),
    ("039", "Anemias", ["D50-D53", "D55-D62", "D64"]),
    ("040", "Otros trastornos de la sangre y los órganos hematopooyéticos",
     ["D65-D76", "D80-D89"]),
    ("041", "Diabetes mellitus", ["E10-E14"]),
    ("042", "Desnutrición y otros trastornos por deficiencia nutricional",
     ["E40-E64"]),
    ("043", "Otras enfermedades endocrinas, nutricionales y metabólicas",
     ["E00-E07", "E15-E34", "E65-E89"]),
    ("044", "Trastornos mentales y del comportamiento",
     ["F01", "F03-F99"]),
    ("045", "Enfermedades inflamatorias del sistema nervioso central",
     ["G00", "G03-G04", "G06", "G08-G09"]),
    ("046", "Epilepsia y otros trastornos nerviosos crónicos",
     ["G40-G45", "G47"]),
    ("047", "Otras enfermedades del sistema nervioso",
     ["G10-G12", "G20-G21", "G23-G25", "G30-G31", "G35-G37",
      "G50-G52", "G54", "G56-G58", "G60-G62", "G64", "G70-G72",
      "G80-G83", "G90-G93", "G95-G96", "G98"]),
    ("048", "Enfermedades del ojo y sus anexos",
     ["H00-H02", "H04-H05", "H10-H11", "H15-H18", "H20-H21",
      "H25-H27", "H30-H31", "H33-H35", "H40", "H43-H44", "H46-H47",
      "H49-H57", "H59-H61", "H65-H66", "H68-H74", "H80-H81", "H83-H93",
      "H95"]),
    ("049", "Rheumatismo agudo y otras enfermedades reumáticas crónicas",
     ["I00-I09"]),
    ("050", "Enfermedad hipertensiva", ["I10-I15"]),
    ("051", "Enfermedad isquémica del corazón", ["I20-I25"]),
    ("052", "Otras enfermedades cardíacas", ["I26-I28"]),
    ("053", "Otras enfermedades del sistema circulatorio",
     ["I30-I31", "I33-I38", "I40", "I42", "I44-I46.1", "I47-I49", "I51"]),
    ("054", "Insuficiencia cardíaca", ["I50"]),
    ("055", "Enfermedad cerebrovascular", ["I60-I67", "I69"]),
    ("056", "Aterosclerosis", ["I70"]),
    ("057", "Aneurisma y hemorragia de la aorta", ["I71"]),
    ("058", "Otras enfermedades de los vasos sanguíneos",
     ["I72-I78", "I80-I95", "I99"]),
    ("059", "Neumonía", ["J12-J16", "J18"]),
    ("060", "Enfermedad crónica de las vías respiratorias inferiores",
     ["J40-J47"]),
    ("061", "Otras enfermedades del sistema respiratorio",
     ["J60-J70"]),
    ("062", "Infecciones agudas de las vías respiratorias superiores",
     ["J00-J11", "J20-J22", "J30-J39", "J80-J86", "J90", "J92-J94",
      "J96-J98"]),
    ("063", "Úlcera péptica", ["K25-K28"]),
    ("064", "Otras enfermedades del esófago, estómago y duodeno",
     ["K20-K22", "K29-K31"]),
    ("065", "Apendicitis y otras enfermedades peritoneales",
     ["K35-K38", "K40-K46", "K56"]),
    ("066", "Enfermedad crónica del hígado y cirrosis", ["K70-K76"]),
    ("067", "Enfermedades de la vesícula biliar", ["K80-K86"]),
    ("068", "Enfermedades inflamatorias del intestino",
     ["K50-K52", "K55", "K57-K64"]),
    ("069", "Otras enfermedades del aparato digestivo",
     ["K00-K14", "K65-K66", "K90", "K92.8-K92.9"]),
    ("070", "Hemorragia gastrointestinal", ["K92.0-K92.2"]),
    ("071", "Enfermedades de la piel y del tejido subcutáneo",
     ["L00-L08", "L10-L13", "L20-L44", "L50-L53", "L55-L60",
      "L63-L85", "L87-L98"]),
    ("072", "Enfermedades del sistema osteomuscular y del tejido conectivo",
     ["M00", "M02", "M05-M06", "M08", "M10-M13", "M15-M25",
      "M30-M35", "M40-M48", "M50-M62", "M65-M67", "M70-M72",
      "M75-M81", "M83-M89", "M91-M99"]),
    ("073", "Enfermedades crónicas del glomérulo y otras",
     ["N00-N07", "N10-N15"]),
    ("074", "Enfermedad renal aguda y otras", ["N17-N19"]),
    ("075", "Otras enfermedades del sistema genitourinario",
     ["N20-N21", "N23", "N25-N28", "N30-N32", "N34-N36", "N39", "N99.1"]),
    ("076", "Hiperplasia de la próstata", ["N40"]),
    ("077", "Enfermedades de los órganos genitales femeninos",
     ["N41-N50", "N60-N73", "N75-N76", "N80-N99.0", "N99.2-N99.9"]),
    ("078", "Embarazo, parto y puerperio", ["O00-O99"]),
    ("079", "Afecciones perinatales relacionadas con el embarazo",
     ["P00", "P04"]),
    ("080", "Traumatismo perinatal", ["P01-P03", "P10-P15"]),
    ("081", "Recién nacido de bajo peso y prematurez", ["P05", "P07"]),
    ("082", "Trastornos respiratorios y del desarrollo fetal",
     ["P20-P28"]),
    ("083", "Otras afecciones originadas en el período perinatal",
     ["P50-P61"]),
    ("084", "Infecciones bacterianas perinatales", ["P35-P39"]),
    ("085", "Síndrome de distrés respiratorio del recién nacido", ["P77"]),
    ("086", "Otras afecciones originadas en el período perinatal",
     ["P08", "P29", "P70-P74", "P76", "P78-P96"]),
    ("087", "Malformaciones congénitas del sistema circulatorio",
     ["Q20-Q28"]),
    ("088", "Otras malformaciones congénitas, deformidades y anomalías cromosómicas",
     ["Q00-Q18", "Q30-Q99"]),
    ("089", "Síntomas, signos y hallazgos clínicos y de laboratorio anormales",
     ["R00-R99"]),
    ("090", "Accidentes de transporte terrestre",
     ["V02-V04", "V09.0", "V09.2-V09.9", "V12-V14", "V19.0-V19.2",
      "V19.4-V19.6", "V19.9", "V20-V79", "V80.3-V80.5", "V81.0-V81.1",
      "V82.0-V82.1", "V83-V86", "V87.0-V87.8", "V88.0-V88.8",
      "V89.0", "V89.2", "V89.9", "Y85.0"]),
    ("091", "Accidentes de transporte como peatón",
     ["V01", "V05-V06", "V09.1", "V10-V11", "V15-V18", "V19.3",
      "V19.8", "V80.0-V80.2", "V80.6-V80.9", "V81.2-V81.9",
      "V82.2-V82.9", "V87.9", "V88.9", "V89.1", "V89.3"]),
    ("092", "Accidentes de transporte acuático y aéreo",
     ["V90-V99", "Y85.9"]),
    ("093", "Caídas", ["W00-W19"]),
    ("094", "Ahogamiento y sumersión accidental", ["W32-W34"]),
    ("095", "Exposición a fuerza mecánica no especificada", ["W65-W74"]),
    ("096", "Exposición a humo, fuego y llamas", ["W75-W84"]),
    ("097", "Envenenamiento accidental por medicamentos y sustancias biológicas",
     ["W85-W99"]),
    ("098", "Lesiones autoinfligidas por envenenamiento", ["X00-X09"]),
    ("099", "Envenenamiento accidental por medicamentos", ["X40-X49"]),
    ("100", "Lesiones autoinfligidas", ["X60-X84", "Y87.0"]),
    ("101", "Homicidio", ["X85-Y09", "Y87.1"]),
    ("102", "Lesiones debidas a intervención de la ley y operaciones bélicas",
     ["Y10-Y34", "Y87.2"]),
    ("103", "Consecuencias de causas externas", ["Y35-Y36", "Y89.0-Y89.1"]),
    ("104", "Efectos adversos y complicaciones de medicamentos",
     ["Y40-Y84", "Y88"]),
    ("105", "Otras causas externas y las no especificadas",
     ["W20-W31", "W35-W64", "X10-X39", "X50-X59", "Y86", "Y89.9"]),
]


def obtener_grupo(cau_homol):
    """
    Devuelve la descripción del grupo Lista 105 dado un código CAU_HOMOL.

    Args:
        cau_homol: Código de 3 dígitos (ej: "010", "051").

    Returns:
        Descripción del grupo o None si no se encuentra.
    """
    for codigo, descripcion, _ in LISTA_105:
        if codigo == str(cau_homol).strip():
            return descripcion
    return None


def obtener_rangos_cie10(cau_homol):
    """
    Devuelve la lista de rangos CIE-10 para un código CAU_HOMOL.

    Args:
        cau_homol: Código de 3 dígitos (ej: "010").

    Returns:
        Lista de strings con rangos CIE-10 o None.
    """
    for codigo, _, rangos in LISTA_105:
        if codigo == str(cau_homol).strip():
            return rangos
    return None


def todos_los_codigos_cau_homol():
    """Devuelve la lista de todos los códigos CAU_HOMOL válidos."""
    return [codigo for codigo, _, _ in LISTA_105]


# Categoría auxiliar para C50 (Tumor maligno de mama).
# La Lista 105 distingue "C50, en mujeres" (grupo 024) y
# "C50 en hombres" (grupo 038). Como RIPS no dispone de datos
# de sexo, C50 se clasifica como categoría auxiliar independiente.
# No es un grupo oficial de la Lista 105.
CATEGORIA_C50_AUXILIAR = "C50"


def es_categoria_c50(resultado):
    """
    Verifica si un resultado de homologar_diagnostico() es la
    categoría auxiliar C50.

    Args:
        resultado: Valor devuelto por homologar_diagnostico().

    Returns:
        True si es la categoría C50 auxiliar, False en caso contrario.
    """
    return resultado == CATEGORIA_C50_AUXILIAR


def extraer_codigo_cie10(diagnostico):
    """
    Extrae el código CIE-10 de una cadena de diagnóstico RIPS.

    El formato RIPS es "CODIGO - DESCRIPCION" o solo "CODIGO".
    Los códigos CIE-10 tienen formato letra + dígitos, opcionalmente
    con subcategorías (ej: "R104", "I10X", "U072", "A85.2").

    Args:
        diagnostico: Cadena de diagnóstico (ej: "R104 - OTROS DOLORES...").

    Returns:
        Código CIE-10 normalizado o None si no se puede extraer.
    """
    if not diagnostico or not isinstance(diagnostico, str):
        return None

    diag = diagnostico.strip()
    if not diag:
        return None

    # Separar por " - " si existe
    partes = diag.split(" - ", 1)
    codigo = partes[0].strip()

    # Normalizar: quitar espacios internos y puntos
    codigo = codigo.replace(" ", "")

    if not codigo:
        return None

    return codigo


def codigo_en_rango(codigo, rango):
    """
    Verifica si un código CIE-10 está dentro de un rango.

    Maneja:
        - Rangos: "A00-A09", "I44-I46.1"
        - Códigos individuales: "A20", "B90"
        - Códigos con subcategoría: "A85.2"

    Args:
        codigo: Código CIE-10 a verificar (ej: "R104").
        rango: Rango o código de la Lista 105 (ej: "R00-R99").

    Returns:
        True si el código está dentro del rango.
    """
    if "-" in rango:
        inicio, fin = rango.split("-", 1)
        # Normalizar: quitar puntos para comparación numérica
        # pero mantener la letra
        return _codigo_en_rango_detallado(codigo, inicio.strip(), fin.strip())
    else:
        # Código individual
        esperado = rango.strip()
        return _codigos_iguales(codigo, esperado)


def _codigos_iguales(codigo, esperado):
    """
    Compara dos códigos CIE-10 considerando que RIPS puede usar
    formatos con X al final (ej: "I10X" = "I10") y puntos
    (ej: "K922" = "K92.2").

    También soporta coincidencia por prefijo: un código individual
    en la Lista 105 (ej: "N39") puede representar un grupo de códigos
    más específicos (ej: "N390", "N391").
    """
    c = _normalizar_codigo(codigo)
    e = _normalizar_codigo(esperado)

    # Comparación exacta
    if c == e:
        return True

    # Un código con sufijo X significa "no especificado"
    # I10X debe coincidir con I10
    if c.endswith("X") and c[:-1] == e:
        return True
    if e.endswith("X") and e[:-1] == c:
        return True

    # Coincidencia por prefijo: un código individual en la Lista 105
    # puede representar un grupo. Por ejemplo, "N39" en la lista
    # cubre N390, N391, N392, etc.
    # Solo aplicar si la letra es la misma y el código del dato
    # empieza con el código de la lista
    c_letra = _extraer_letra(c)
    e_letra = _extraer_letra(e)
    if c_letra == e_letra and c.startswith(e):
        return True

    return False


def _normalizar_codigo(codigo):
    """
    Normaliza un código CIE-10 para comparación.
    - Quitar puntos: "K92.2" -> "K922"
    - Quitar X final: "I10X" -> "I10"
    """
    c = codigo.strip().upper()
    c = c.replace(".", "")
    if c.endswith("X"):
        c = c[:-1]
    return c


def _codigo_en_rango_detallado(codigo, inicio, fin):
    """
    Verifica si un código CIE-10 está entre inicio y fin.

    La comparación se hace por:
    1. Letra principal (A, B, C, ..., Z)
    2. Parte numérica después de la letra, comparando carácter por carácter

    Los códigos CIE-10 tienen longitud variable:
    - "R00" (3 chars), "R104" (4 chars), "I46.1" (4 chars)
    - El rango "R00-R99" cubre R000-R999 (todos los códigos R)
    - El rango "I20-I25" cubre I20-I25 (I200-I259)

    Para la comparación, se normaliza la longitud numérica:
    - Se compara el prefijo común (mismos dígitos que el rango)
    """
    c_norm = _normalizar_codigo(codigo)
    i_norm = _normalizar_codigo(inicio)
    f_norm = _normalizar_codigo(fin)

    # Extraer letra y parte numérica
    c_letra = _extraer_letra(c_norm)
    i_letra = _extraer_letra(i_norm)
    f_letra = _extraer_letra(f_norm)

    # La letra debe estar en el rango
    if not (i_letra <= c_letra <= f_letra):
        return False

    # Extraer parte numérica como string para comparación de prefijos
    c_num_str = _extraer_numeros_str(c_norm)
    i_num_str = _extraer_numeros_str(i_norm)
    f_num_str = _extraer_numeros_str(f_norm)

    # Si la letra es la misma, verificar el número
    if c_letra == i_letra == f_letra:
        return _num_str_en_rango(c_num_str, i_num_str, f_num_str)

    # Si la letra del código es igual al inicio, debe ser >= inicio
    if c_letra == i_letra:
        return _num_str_ge(c_num_str, i_num_str)

    # Si la letra del código es igual al fin, debe ser <= fin
    if c_letra == f_letra:
        return _num_str_le(c_num_str, f_num_str)

    # La letra está entre inicio y fin
    return True


def _extraer_numeros_str(codigo):
    """Extrae la parte numérica de un código CIE-10 como string."""
    numeros = ""
    for char in codigo:
        if char.isdigit():
            numeros += char
    return numeros if numeros else "0"


def _num_str_en_rango(val, inicio, fin):
    """
    Verifica si un número (como string) está en el rango [inicio, fin].

    Los rangos CIE-10 usan prefijos: "R00-R99" significa que cualquier
    código que empiece con R y cuyo número esté entre 00 y 99 está incluido.

    Para códigos más largos (ej: R104), se compara el prefijo de la misma
    longitud que el límite del rango.
    """
    # Comparar con la longitud del inicio
    len_inicio = len(inicio)
    len_fin = len(fin)
    len_ref = max(len_inicio, len_fin)

    # Si el código es más corto que el rango, pad con ceros
    if len(val) < len_ref:
        val_cmp = val.ljust(len_ref, '0')
    else:
        val_cmp = val[:len_ref]

    inicio_cmp = inicio.ljust(len_ref, '0')
    fin_cmp = fin.ljust(len_ref, '0')

    return inicio_cmp <= val_cmp <= fin_cmp


def _num_str_ge(val, ref):
    """Verifica si val >= ref comparando prefijos."""
    len_ref = len(ref)
    if len(val) < len_ref:
        val_cmp = val.ljust(len_ref, '0')
    else:
        val_cmp = val[:len_ref]
    return val_cmp >= ref[:len_ref]


def _num_str_le(val, ref):
    """Verifica si val <= ref comparando prefijos."""
    len_ref = len(ref)
    if len(val) < len_ref:
        val_cmp = val.ljust(len_ref, '0')
    else:
        val_cmp = val[:len_ref]
    return val_cmp <= ref[:len_ref]


def _extraer_letra(codigo):
    """Extrae la letra(s) al inicio de un código CIE-10."""
    letra = ""
    for char in codigo:
        if char.isalpha():
            letra += char
        else:
            break
    return letra


def _extraer_numeros(codigo):
    """Extrae la parte numérica de un código CIE-10 como entero."""
    numeros = ""
    for char in codigo:
        if char.isdigit():
            numeros += char
    return int(numeros) if numeros else 0


def homologar_diagnostico(diagnostico):
    """
    Clasifica un diagnóstico RIPS al grupo Lista 105 correspondiente.

    Args:
        diagnostico: Cadena de diagnóstico RIPS
                     (ej: "R104 - OTROS DOLORES ABDOMINALES").

    Returns:
        Código CAU_HOMOL de 3 dígitos (ej: "089"),
        CATEGORIA_C50_AUXILIAR si es C50 (sin datos de sexo),
        o None si no se puede homologar.
    """
    codigo = extraer_codigo_cie10(diagnostico)
    if not codigo:
        return None

    # C50: categoría auxiliar independiente.
    # La Lista 105 distingue "C50, en mujeres" (grupo 024) y
    # "C50 en hombres" (grupo 038). Como RIPS no dispone de datos
    # de sexo, no se puede determinar el grupo correcto.
    # Se devuelve la categoría auxiliar para fines de reporte.
    # C50 con subcategorías (C500-C509) también se incluyen.
    codigo_normalizado = _normalizar_codigo(codigo)
    if codigo_normalizado.startswith("C50"):
        return CATEGORIA_C50_AUXILIAR

    for cau_homol, _, rangos in LISTA_105:
        for rango in rangos:
            # Rangos con condiciones de sexo no se evalúan automáticamente
            # (ej: "C50, en mujeres", "C50 en hombres")
            if "," in rango or "en mujeres" in rango or "en hombres" in rango:
                # Extraer solo la parte del código para comparación
                parte_codigo = rango.split(",")[0].strip()
                # Si es C50 con condición de sexo, saltar (ya se manejó arriba)
                if _normalizar_codigo(parte_codigo) == "C50":
                    continue
                if codigo_en_rango(codigo, parte_codigo):
                    return cau_homol
            else:
                if codigo_en_rango(codigo, rango):
                    return cau_homol

    return None
