"""Paso 3: convertir las palabras en subtítulos dinámicos (.ass).

Las palabras que el guion (shorts/<nombre>/guion.md) marca en **negrita** salen en
el color de resaltado. Para saber cuáles son se alinea el texto del guion con la
transcripción (difflib), en vez de buscar cada palabra suelta: así, si "no" va en
negrita una sola vez, no se resaltan todos los "no" del vídeo.

Con la misma alineación se corrigen los errores de Whisper: si un tramo de la
transcripción tiene tantas palabras como el del guion y se parece lo bastante ("Eso
qué hay después" / "Eso que oyes después"), se muestra el texto del guion con los
tiempos de Whisper. Si es muy distinto (una frase improvisada), se deja lo que se dijo.
palabras.json no cambia: solo lo que sale en pantalla.
"""
import difflib
import json
import re
import unicodedata

FIN_FRASE = (".", "?", "!", ",", ";", ":")
PARECIDO_MIN = 0.5      # parecido mínimo (de 0 a 1) para corregir un tramo con el guion
# Palabras de un número escrito con letras, ya normalizadas (sin tildes): Whisper los escribe con cifras
NUMERO = re.compile(r"\d+|cero|uno?|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|"
                    r"trece|catorce|quince|dieci\w+|veint\w*|treinta|cuarenta|cincuenta|sesenta|"
                    r"setenta|ochenta|noventa|cien|ciento|\w*cientos|quinientos|mil|millon|millones")


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
    """Las palabras que se dicen en el guion: (normalizada, True si va en negrita, tal cual).
    Solo cuenta la sección '## Guion', sin las etiquetas (**Gancho:**) ni las (pausa)."""
    seccion = re.search(r"^## Guion\s*$(.*?)(?=^## |\Z)", ruta.read_text(encoding="utf-8"), re.M | re.S)
    if not seccion:
        return []
    texto = re.sub(r"^\*\*[^*\n]+:\*\*", " ", seccion.group(1), flags=re.M)
    texto = re.sub(r"\(pausa\)", " ", texto, flags=re.I)
    resultado, negrita = [], False
    for trozo in texto.split():
        # Cada "**" abre o cierra la negrita; la puntuación se queda pegada ("**rayo**." -> "rayo.")
        palabra, en_negrita, i = "", None, 0
        while i < len(trozo):
            if trozo.startswith("**", i):
                negrita, i = not negrita, i + 2
                continue
            if en_negrita is None and trozo[i].isalnum():
                en_negrita = negrita
            palabra, i = palabra + trozo[i], i + 1
        if normalizar(palabra):
            resultado.append((normalizar(palabra), bool(en_negrita), palabra))
    return resultado


def alinear(palabras, guion):
    """Alinea el guion con la transcripción. Devuelve las palabras transcritas que cuentan,
    como (posición, normalizada), y los tramos de difflib (operación, a1, a2, b1, b2):
    guion[a1:a2] corresponde a transcritas[b1:b2]."""
    transcritas = [(i, normalizar(p["palabra"])) for i, p in enumerate(palabras)]
    transcritas = [(i, limpia) for i, limpia in transcritas if limpia]
    comparador = difflib.SequenceMatcher(None, [g[0] for g in guion],
                                         [limpia for _, limpia in transcritas], autojunk=False)
    return transcritas, comparador.get_opcodes()


def corregir_con_guion(palabras, guion):
    """Pone el texto del guion donde Whisper lo ha escrito mal. En los tramos iguales,
    la forma escrita del guion (tildes y puntuación: "qué" -> "que"). En los distintos,
    si tienen el mismo número de palabras y se parecen lo bastante, o son 1 o 2 palabras
    entre dos tramos iguales ("eso que [hay] después": casi seguro, mal oído).
    Devuelve los cambios de palabras, para enseñarlos."""
    transcritas, tramos = alinear(palabras, guion)
    cambios = []
    for n, (operacion, a1, a2, b1, b2) in enumerate(tramos):
        if operacion == "equal":
            for (i, _), (_, _, original) in zip(transcritas[b1:b2], guion[a1:a2]):
                palabras[i]["palabra"] = original
            continue
        if operacion != "replace" or a2 - a1 != b2 - b1:
            continue
        del_guion = "".join(g[0] for g in guion[a1:a2])
        oido = "".join(limpia for _, limpia in transcritas[b1:b2])
        entre_iguales = (0 < n < len(tramos) - 1 and tramos[n - 1][0] == "equal"
                         and tramos[n + 1][0] == "equal")
        parecido = difflib.SequenceMatcher(None, del_guion, oido).ratio()
        if parecido < PARECIDO_MIN and not (entre_iguales and a2 - a1 <= 2):
            continue
        antes = " ".join(palabras[i]["palabra"] for i, _ in transcritas[b1:b2])
        for (i, _), (_, _, original) in zip(transcritas[b1:b2], guion[a1:a2]):
            palabras[i]["palabra"] = original
        cambios.append(f"«{antes}» -> «{' '.join(g[2] for g in guion[a1:a2])}»")
    return cambios


def indices_resaltados(palabras, guion):
    """Las posiciones de la transcripción que corresponden a palabras en negrita del
    guion, y cuántas palabras en negrita tiene el guion."""
    transcritas, tramos = alinear(palabras, guion)
    resaltados = set()
    for operacion, a1, a2, b1, b2 in tramos:
        if operacion == "equal":                         # tramo igual en los dos textos
            for k in range(a2 - a1):
                if guion[a1 + k][1]:
                    resaltados.add(transcritas[b1 + k][0])
        elif operacion == "replace" and all(g[1] for g in guion[a1:a2]):
            # Whisper lo ha escrito de otra manera ("treinta mil" -> "30.000"): si en el
            # guion todo el tramo va en negrita, se resalta lo transcrito en su lugar
            resaltados.update(i for i, _ in transcritas[b1:b2])
        elif operacion == "replace" and cifra_en_negrita(guion[a1:a2]):
            # Tramo mezclado: "doscientos mil kilómetros" -> "200.000 km". La negrita es
            # el número, así que se resalta lo transcrito con cifras ("200.000"), no "km"
            resaltados.update(i for i, limpia in transcritas[b1:b2] if any(c.isdigit() for c in limpia))
    return resaltados, sum(g[1] for g in guion)


def es_numero(normalizada):
    """'doscientos', 'mil', 'veintiuno', '2061'... (sin tildes, en minúsculas)."""
    return bool(NUMERO.fullmatch(normalizada))


def cifra_en_negrita(tramo):
    """Si en un tramo del guion las palabras en negrita son un número escrito con letras
    (o con cifras) y las demás no lo son."""
    negritas = [g[0] for g in tramo if g[1]]
    resto = [g[0] for g in tramo if not g[1]]
    return bool(negritas) and all(es_numero(p) for p in negritas) and not any(es_numero(p) for p in resto)


def unir_cifras(palabras):
    """Whisper parte a veces las cifras ("30" y ".000,"): se juntan en una sola palabra."""
    resultado = []
    for p in palabras:
        if resultado and re.match(r"[.,]\d", p["palabra"]) and re.search(r"\d$", resultado[-1]["palabra"]):
            resultado[-1] = {**resultado[-1], "palabra": resultado[-1]["palabra"] + p["palabra"], "fin": p["fin"]}
        else:
            resultado.append(dict(p))
    return resultado


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
    """guion: la ruta de guion.md del short; si no existe, no se corrige ni se resalta nada."""
    palabras = unir_cifras(json.loads(json_entrada.read_text(encoding="utf-8")))
    del_guion = palabras_del_guion(guion) if guion is not None and guion.exists() else []
    if c["corregir_con_guion"] and del_guion:
        cambios = corregir_con_guion(palabras, del_guion)
        print(f"   {len(cambios)} tramos corregidos con el guion" + "".join(f"\n      {x}" for x in cambios))
    if c["resaltar_negritas"] and del_guion:
        resaltados, en_negrita = indices_resaltados(palabras, del_guion)
        for i in resaltados:
            palabras[i]["resaltada"] = True
        print(f"   {len(resaltados)} de {en_negrita} palabras en negrita del guion resaltadas")
    grupos = agrupar(palabras, c)

    lineas = [cabecera(c)]
    for n, g in enumerate(grupos):
        inicio, fin = g[0]["inicio"], g[-1]["fin"]
        if n + 1 < len(grupos) and grupos[n + 1][0]["inicio"] - fin < 0.25:
            fin = grupos[n + 1][0]["inicio"]
        # Cada subtítulo se ve al menos duracion_min, sin pisar el siguiente
        fin = max(fin, inicio + c["duracion_min"])
        if n + 1 < len(grupos):
            fin = min(fin, grupos[n + 1][0]["inicio"])
        texto = " ".join(escribir(p, c) for p in g)
        lineas.append(
            f"Dialogue: 0,{formato_ass(inicio)},{formato_ass(fin)},Short,,0,0,0,,{texto}\n"
        )

    ass_salida.write_text("".join(lineas), encoding="utf-8")
    print(f"   {len(palabras)} palabras en {len(grupos)} grupos")
