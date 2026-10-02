"""Paso 3: convertir las palabras en subtítulos dinámicos (.ass)."""
import json

FIN_FRASE = (".", "?", "!", ",", ";", ":")


def formato_ass(segundos):
    cs_totales = int(round(segundos * 100))
    horas, resto = divmod(cs_totales, 360_000)
    minutos, resto = divmod(resto, 6_000)
    segs, cs = divmod(resto, 100)
    return f"{horas}:{minutos:02}:{segs:02}.{cs:02}"


def cabecera(c):
    return (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Short,{c['fuente']},{c['tamano']},&H00FFFFFF,&H00FFFFFF,&H00000000,"
        f"&H00000000,-1,0,0,0,100,100,0,0,1,7,0,2,60,60,{c['margen_vertical']},1\n\n"
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


def generar_ass(json_entrada, ass_salida, c):
    palabras = json.loads(json_entrada.read_text(encoding="utf-8"))
    grupos = agrupar(palabras, c)

    lineas = [cabecera(c)]
    for n, g in enumerate(grupos):
        inicio, fin = g[0]["inicio"], g[-1]["fin"]
        if n + 1 < len(grupos) and grupos[n + 1][0]["inicio"] - fin < 0.25:
            fin = grupos[n + 1][0]["inicio"]
        texto = " ".join(p["palabra"] for p in g)
        if c["mayusculas"]:
            texto = texto.upper()
        texto = texto.replace("{", "(").replace("}", ")")
        lineas.append(
            f"Dialogue: 0,{formato_ass(inicio)},{formato_ass(fin)},Short,,0,0,0,,{texto}\n"
        )

    ass_salida.write_text("".join(lineas), encoding="utf-8")
    print(f"   {len(palabras)} palabras en {len(grupos)} grupos")
