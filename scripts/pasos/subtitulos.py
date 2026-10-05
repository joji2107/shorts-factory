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
PARECIDO_JUNTAS = 0.8   # para cambiar una palabra oída por 2 o 3 del guion que suenan igual juntas
# Palabras de un número escrito con letras, ya normalizadas (sin tildes): Whisper los escribe con cifras
NUMERO = re.compile(r"\d+|cero|uno?|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|"
                    r"trece|catorce|quince|dieci\w+|veint\w*|treinta|cuarenta|cincuenta|sesenta|"
                    r"setenta|ochenta|noventa|cien|ciento|\w*cientos|quinientos|mil|millon|millones")


# Valor de cada palabra de un número escrito con letras (normalizada: sin tildes)
VALORES = {"cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
           "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14,
           "quince": 15, "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20,
           "veintiuno": 21, "veintiun": 21, "veintiuna": 21, "veintidos": 22, "veintitres": 23,
           "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26, "veintisiete": 27, "veintiocho": 28,
           "veintinueve": 29, "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70,
           "ochenta": 80, "noventa": 90, "cien": 100, "ciento": 100, "doscientos": 200, "doscientas": 200,
           "trescientos": 300, "trescientas": 300, "cuatrocientos": 400, "cuatrocientas": 400,
           "quinientos": 500, "quinientas": 500, "seiscientos": 600, "seiscientas": 600,
           "setecientos": 700, "setecientas": 700, "ochocientos": 800, "ochocientas": 800,
           "novecientos": 900, "novecientas": 900}


def valor_numero(palabras):
    """'treinta y cinco' -> 35, 'dos mil seis' -> 2006 (palabras normalizadas). None si
    alguna no es parte de un número."""
    total, grupo = 0, 0
    for palabra in palabras:
        if palabra == "y":
            continue
        if palabra.isdigit():
            grupo += int(palabra)
        elif palabra == "mil":
            total, grupo = total + (grupo or 1) * 1000, 0
        elif palabra in ("millon", "millones"):
            total, grupo = (total + (grupo or 1)) * 1_000_000, 0
        elif palabra in VALORES:
            grupo += VALORES[palabra]
        else:
            return None
    return total + grupo


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


def seccion_guion(ruta):
    """El texto de la sección '## Guion' de guion.md ("" si no la tiene)."""
    seccion = re.search(r"^## Guion\s*$(.*?)(?=^## |\Z)", ruta.read_text(encoding="utf-8"), re.M | re.S)
    return seccion.group(1) if seccion else ""


def solo_lo_que_se_dice(texto):
    """Quita lo que no se lee en voz alta: las etiquetas (**Gancho:**), las (pausa) y las
    marcas de montaje entre corchetes ([respiro 3], [plano volcan_03 12 6])."""
    texto = re.sub(r"^\*\*[^*\n]+:\*\*", " ", texto, flags=re.M)
    texto = re.sub(r"\(pausa\)", " ", texto, flags=re.I)
    return re.sub(r"\[[^\]]*\]", " ", texto)


def palabras_del_guion(ruta):
    """Las palabras que se dicen en el guion: (normalizada, True si va en negrita, tal cual).
    Solo cuenta la sección '## Guion', sin etiquetas, (pausa) ni marcas."""
    return palabras_de_texto(solo_lo_que_se_dice(seccion_guion(ruta)))


def palabras_de_texto(texto):
    """(normalizada, en negrita, tal cual) de cada palabra de un trozo de guion ya limpio."""
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
        entre_iguales = (0 < n < len(tramos) - 1 and tramos[n - 1][0] == "equal"
                         and tramos[n + 1][0] == "equal")
        if operacion == "replace" and entre_iguales and b2 - b1 == 1 and transcritas[b1][1].isdigit():
            # Whisper escribe los números con cifras: si el valor es el del guion ("2006" por
            # "dos mil seis"), está bien oído y se deja. Si es otro ("75" por "de treinta y
            # cinco", en 012), lo oyó mal: se pone el texto del guion.
            # "por ciento" no es parte del número: con él, "siete por ciento" valía 700 y el
            # "7 %" bien oído se cambiaba, dejando el "%" suelto en el subtítulo (014)
            tramo = [g[0] for g in guion[a1:a2]]
            numero = [p for k, p in enumerate(tramo) if (es_numero(p) or p == "y")
                      and not (p == "ciento" and k > 0 and tramo[k - 1] == "por")]
            valor = valor_numero(numero) if any(es_numero(p) for p in numero) else None
            if valor is not None and valor != int(transcritas[b1][1]):
                i = transcritas[b1][0]
                antes = palabras[i]["palabra"]
                palabras[i]["palabra"] = " ".join(g[2] for g in guion[a1:a2])
                cambios.append(f"«{antes}» -> «{palabras[i]['palabra']}» (número mal oído)")
            continue
        if (operacion == "replace" and entre_iguales and b2 - b1 == 1 and 2 <= a2 - a1 <= 3
                and difflib.SequenceMatcher(None, "".join(g[0] for g in guion[a1:a2]),
                                            transcritas[b1][1]).ratio() >= PARECIDO_JUNTAS):
            # Whisper juntó varias palabras en una que suena igual: "el mar te pareció" ->
            # "el martes pareció" (014). Sin espacios casi coinciden: se pone el guion.
            i = transcritas[b1][0]
            antes = palabras[i]["palabra"]
            palabras[i]["palabra"] = " ".join(g[2] for g in guion[a1:a2])
            cambios.append(f"«{antes}» -> «{palabras[i]['palabra']}» (palabras juntas)")
            continue
        if operacion != "replace" or a2 - a1 != b2 - b1:
            continue
        del_guion = "".join(g[0] for g in guion[a1:a2])
        oido = "".join(limpia for _, limpia in transcritas[b1:b2])
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
    """Whisper parte a veces las cifras ("30" y ".000,"): se juntan en una sola palabra.
    También el símbolo que va detrás ("7" y "%"): suelto, caía en el subtítulo siguiente
    ("CARGAR UN 7" / "% MÁS DE", en 014). Se escribe con espacio, como en español."""
    resultado = []
    for p in palabras:
        if resultado and re.match(r"[.,]\d", p["palabra"]) and re.search(r"\d$", resultado[-1]["palabra"]):
            resultado[-1] = {**resultado[-1], "palabra": resultado[-1]["palabra"] + p["palabra"], "fin": p["fin"]}
        elif resultado and re.fullmatch(r"\s*[%‰ºª°]\W*", p["palabra"]) and re.search(r"\d$", resultado[-1]["palabra"]):
            resultado[-1] = {**resultado[-1], "palabra": resultado[-1]["palabra"] + " " + p["palabra"].strip(),
                             "fin": p["fin"]}
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
