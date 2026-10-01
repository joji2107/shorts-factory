"""Convierte el .json de palabras (de transcribir.py) en subtítulos .ass
de pocas palabras por pantalla, listos para grabar en el vídeo."""
import json
import sys
from pathlib import Path

MAX_PALABRAS = 3        # palabras máximas por pantalla
PAUSA_MAX = 0.45        # segundos de silencio que fuerzan un corte
FIN_FRASE = (".", "?", "!", ",", ";", ":")
MAYUSCULAS = True

CABECERA = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Short,DejaVu Sans,80,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,7,0,2,60,60,560,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def formato_ass(segundos):
    """Convierte segundos (65.5) al formato de ASS (0:01:05.50)."""
    cs_totales = int(round(segundos * 100))
    horas, resto = divmod(cs_totales, 360_000)
    minutos, resto = divmod(resto, 6_000)
    segs, cs = divmod(resto, 100)
    return f"{horas}:{minutos:02}:{segs:02}.{cs:02}"


def agrupar(palabras):
    """Reparte las palabras en grupos de pocas palabras."""
    grupos, actual = [], []
    for p in palabras:
        # Una pausa larga entre palabras cierra el grupo anterior
        if actual and p["inicio"] - actual[-1]["fin"] > PAUSA_MAX:
            grupos.append(actual)
            actual = []
        actual.append(p)
        # Se cierra el grupo si está lleno o si la palabra acaba en puntuación
        if len(actual) >= MAX_PALABRAS or p["palabra"].endswith(FIN_FRASE):
            grupos.append(actual)
            actual = []
    if actual:
        grupos.append(actual)
    return grupos


def main():
    if len(sys.argv) < 2:
        print("Uso: python generar_ass.py <archivo.json>")
        sys.exit(1)

    ruta = Path(sys.argv[1])
    palabras = json.loads(ruta.read_text(encoding="utf-8"))
    grupos = agrupar(palabras)

    lineas = [CABECERA]
    for n, g in enumerate(grupos):
        inicio = g[0]["inicio"]
        fin = g[-1]["fin"]
        # Si el siguiente grupo empieza casi enseguida, alargamos este
        # hasta ahí para que el texto no parpadee entre palabras
        if n + 1 < len(grupos):
            siguiente = grupos[n + 1][0]["inicio"]
            if siguiente - fin < 0.25:
                fin = siguiente
        texto = " ".join(p["palabra"] for p in g)
        if MAYUSCULAS:
            texto = texto.upper()
        texto = texto.replace("{", "(").replace("}", ")")
        lineas.append(
            f"Dialogue: 0,{formato_ass(inicio)},{formato_ass(fin)},Short,,0,0,0,,{texto}\n"
        )

    salida = ruta.with_suffix(".ass")
    salida.write_text("".join(lineas), encoding="utf-8")
    print(f"{len(palabras)} palabras -> {len(grupos)} grupos -> {salida.name}")


if __name__ == "__main__":
    main()
