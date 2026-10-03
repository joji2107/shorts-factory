"""Paso 3: convertir las palabras en subtítulos dinámicos (.ass).

Las palabras que el guion (shorts/<nombre>/guion.md) marca en **negrita** salen en
el color de resaltado. Para saber cuáles son se alinea el texto del guion con la
transcripción (difflib), en vez de buscar cada palabra suelta: así, si "no" va en
negrita una sola vez, no se resaltan todos los "no" del vídeo.
"""
import difflib
import json
import re
import unicodedata

FIN_FRASE = (".", "?", "!", ",", ";", ":")


def color_ass(web):
    """'#FFC93C' -> '3CC9FF'. ASS escribe los colores al revés que la web: azul, verde, rojo."""
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", web):
        raise ValueError(f"Color no válido: {web!r} (tiene que ser como #FFC93C)")
    rojo, verde, azul = web[1:3], web[3:5], web[5:7]
    return f"{azul}{verde}{rojo}".upper()


def normalizar(palabra):
    """Minúsculas, sin tildes ni signos: '¿Soñar...' -> 'sonar'."""
    sin_tildes = "".join(letra for letra in unicodedata.normalize("NFD", palabra)
                         if unicodedata.category(letra) != "Mn")
    return re.sub(r"[\W_]", "", sin_tildes.lower())


def palabras_del_guion(ruta):
    """Las palabras que se dicen en el guion, normalizadas, con True si van en negrita.
    Solo cuenta la sección '## Guion', sin las etiquetas (**Gancho:**) ni las (pausa)."""
    seccion = re.search(r"^## Guion\s*$(.*?)(?=^## |\Z)", ruta.read_text(encoding="utf-8"), re.M | re.S)
    if not seccion:
        return []
    texto = re.sub(r"^\*\*[^*\n]+:\*\*", " ", seccion.group(1), flags=re.M)
    texto = re.sub(r"\(pausa\)", " ", texto, flags=re.I)
    resultado = []
    # Al partir por "**", los trozos impares son los que estaban entre asteriscos
    for n, trozo in enumerate(texto.split("**")):
        for palabra in trozo.split():
            if normalizar(palabra):
                resultado.append((normalizar(palabra), n % 2 == 1))
    return resultado


def indices_resaltados(palabras, ruta_guion):
    """Las posiciones de la transcripción que corresponden a palabras en negrita del
    guion, y cuántas palabras en negrita tiene el guion."""
    guion = palabras_del_guion(ruta_guion)
    transcritas = [(i, normalizar(p["palabra"])) for i, p in enumerate(palabras)]
    transcritas = [(i, limpia) for i, limpia in transcritas if limpia]
    comparador = difflib.SequenceMatcher(None, [limpia for limpia, _ in guion],
                                         [limpia for _, limpia in transcritas], autojunk=False)
    resaltados = set()
    for tramo in comparador.get_matching_blocks():      # tramos iguales en los dos textos
        for k in range(tramo.size):
            if guion[tramo.a + k][1]:
                resaltados.add(transcritas[tramo.b + k][0])
    return resaltados, sum(negrita for _, negrita in guion)


def formato_ass(segundos):
    cs_totales = int(round(segundos * 100))
    horas, resto = divmod(cs_totales, 360_000)
    minutos, resto = divmod(resto, 6_000)
    segs, cs = divmod(resto, 100)
    return f"{horas}:{minutos:02}:{segs:02}.{cs:02}"


def cabecera(c):
    texto, contorno = color_ass(c["color_texto"]), color_ass(c["color_contorno"])
    return (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Short,{c['fuente']},{c['tamano']},&H00{texto},&H00{texto},&H00{contorno},"
        f"&H00000000,-1,0,0,0,100,100,0,0,1,{c['contorno']},0,2,60,60,{c['margen_vertical']},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def agrupar(palabras, c):
    grupos, actual = [], []
    for p in palabras:
        if actual and p["inicio"] - actual[-1]["fin"] > c["pausa_max"]:
            grupos.append(actual)
            actual = []
        actual.append(p)
        if len(actual) >= c["max_palabras"] or p["palabra"].endswith(FIN_FRASE):
            grupos.append(actual)
            actual = []
    if actual:
        grupos.append(actual)
    return grupos


def escribir(p, c):
    """El texto de una palabra en el .ass, con el color de resaltado si lo lleva."""
    texto = p["palabra"].upper() if c["mayusculas"] else p["palabra"]
    texto = texto.replace("{", "(").replace("}", ")")     # las llaves son etiquetas en ASS
    if p.get("resaltada"):
        # \1c cambia el color del texto (en ASS, &HBBGGRR&) y \r vuelve al del estilo
        texto = f"{{\\1c&H{color_ass(c['color_resaltado'])}&}}{texto}{{\\r}}"
    return texto


def generar_ass(json_entrada, ass_salida, c, guion=None):
    """guion: la ruta de guion.md del short; si no existe, no se resalta nada."""
    palabras = json.loads(json_entrada.read_text(encoding="utf-8"))
    if c["resaltar_negritas"] and guion is not None and guion.exists():
        resaltados, en_negrita = indices_resaltados(palabras, guion)
        for i in resaltados:
            palabras[i]["resaltada"] = True
        print(f"   {len(resaltados)} de {en_negrita} palabras en negrita del guion resaltadas")
    grupos = agrupar(palabras, c)

    lineas = [cabecera(c)]
    for n, g in enumerate(grupos):
        inicio, fin = g[0]["inicio"], g[-1]["fin"]
        if n + 1 < len(grupos) and grupos[n + 1][0]["inicio"] - fin < 0.25:
            fin = grupos[n + 1][0]["inicio"]
        texto = " ".join(escribir(p, c) for p in g)
        lineas.append(
            f"Dialogue: 0,{formato_ass(inicio)},{formato_ass(fin)},Short,,0,0,0,,{texto}\n"
        )

    ass_salida.write_text("".join(lineas), encoding="utf-8")
    print(f"   {len(palabras)} palabras en {len(grupos)} grupos")
