"""Energía de las canciones (fábrica 2.0): dónde está su momento fuerte y desde qué
segundo hay que empezarlas para que ese momento coincida con la revelación del short.

La energía se mide con la sonoridad de corto plazo de FFmpeg (ebur128, ventana de 3 s,
10 valores por segundo) y se resume en un valor por segundo. El *momento fuerte* es el
segundo en que más sube la media de los VENTANA segundos siguientes sobre la de los
anteriores (la entrada del estribillo o del drop): lo que se nota es el contraste con lo
que sonaba justo antes. Lo que viene tiene que quedar al menos POR_ENCIMA dB sobre la
mediana de la canción (si no, sería volver de un silencio a lo normal) y no cuentan los
primeros INTRO segundos (la entrada de la canción). Una canción cuya mayor subida no
llega a SUBIDA_MIN dB es *plana*: no tiene momento fuerte.

Primera versión: se pedía POR_ENCIMA = 2 dB y se medía si era plana por los dB sobre la
mediana. En misterio_03, que es fuerte casi todo el rato (mediana alta), descartaba su
mejor momento: la vuelta tras el valle del segundo 93-127, que sube 8,6 dB.

Los resultados se guardan en biblioteca/musica.json (scripts/analizar_musica.py) y el
render los lee. Sin print(): lo pueden importar el render y el servidor MCP.
"""
import json
import re
import statistics

from .utilidades import ejecutar

VENTANA = 6          # segundos a cada lado para comparar la energía
POR_ENCIMA = 0.5     # dB que el tramo fuerte tiene que superar a la mediana de la canción
INTRO = 10           # segundos del principio en los que no se busca (la entrada de la canción)
SUBIDA_MIN = 3.0     # con una subida menor, la canción es plana (no tiene momento fuerte)
SUELO = -70.0        # dB: el silencio cuenta como esto (si no, sería -infinito)
FLOJO = 6.0          # dB por debajo de la mediana: un respiro ahí es casi un silencio muerto


def curva(archivo):
    """La sonoridad de corto plazo de cada segundo de la canción (LUFS, de 0,5 en 0,5)."""
    resultado = ejecutar([
        "ffmpeg", "-hide_banner", "-nostats", "-i", archivo, "-vn",
        "-af", "ebur128=metadata=1,ametadata=print:key=lavfi.r128.S", "-f", "null", "-",
    ])
    por_segundo, actual = {}, 0.0
    for linea in resultado.stderr.splitlines():
        tiempo = re.search(r"pts_time:([\d.]+)", linea)
        if tiempo:
            actual = float(tiempo.group(1))
        valor = re.search(r"lavfi\.r128\.S=(-?[\d.]+|-inf)", linea)
        if valor:
            db = SUELO if valor.group(1) == "-inf" else max(SUELO, float(valor.group(1)))
            por_segundo.setdefault(int(actual), []).append(db)
    valores = [statistics.mean(por_segundo[s]) for s in sorted(por_segundo)]
    # Los 3 primeros segundos la ventana de ebur128 aún se está llenando: se copian del 3
    if len(valores) > 3:
        valores[:3] = [valores[3]] * 3
    return [round(v * 2) / 2 for v in valores]


def momento_fuerte(valores):
    """(segundo, subida en dB, dB sobre la mediana) del momento fuerte, o (None, 0, 0)."""
    if len(valores) < 2 * VENTANA + 1:
        return None, 0.0, 0.0
    mediana = statistics.median(valores)
    mejor = (None, 0.0, 0.0)
    for t in range(max(VENTANA, INTRO), len(valores) - VENTANA + 1):
        antes = statistics.mean(valores[t - VENTANA:t])
        despues = statistics.mean(valores[t:t + VENTANA])
        if despues - mediana >= POR_ENCIMA and despues - antes > mejor[1]:
            mejor = (t, round(despues - antes, 1), round(despues - mediana, 1))
    return mejor


def analizar(archivo, duracion_total):
    """Lo que se guarda de cada canción en biblioteca/musica.json."""
    valores = curva(archivo)
    segundo, subida, sobre = momento_fuerte(valores)
    return {"duracion": round(duracion_total, 1), "mediana_lufs": statistics.median(valores),
            "momento_fuerte": segundo, "subida_db": subida, "sobre_mediana_db": sobre,
            "plana": segundo is None or subida < SUBIDA_MIN, "curva": valores}


def leer_energia(raiz):
    """El contenido de biblioteca/musica.json ({} si todavía no existe)."""
    ruta = raiz / "biblioteca" / "musica.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def respiros_flojos(energia, inicio, respiros):
    """Avisos de los respiros que caen en un tramo flojo de la canción (FLOJO dB o más por
    debajo de su mediana): en 902-respiros, alineando misterio_03 con la revelación, el
    primer respiro caía en el valle de antes del drop y sonaba a -28 LUFS, casi mudo."""
    avisos = []
    curva = energia["curva"]
    for r in respiros:
        tramo = curva[int(inicio + r["inicio"]):int(inicio + r["fin"]) + 1]
        if tramo and statistics.mean(tramo) < energia["mediana_lufs"] - FLOJO:
            avisos.append(f"el respiro de {r['inicio']:.1f} s (antes de «{r['antes_de']}») cae en un tramo "
                          f"flojo de la canción ({statistics.mean(tramo) - energia['mediana_lufs']:+.0f} dB): "
                          "sonará casi en silencio; muévelo o quítalo")
    return avisos


def inicio_musica(momento, revelacion, total, duracion_cancion):
    """Desde qué segundo empezar la canción para que su momento fuerte suene en la
    revelación. Devuelve (inicio, aviso o None). Si el momento fuerte llega demasiado
    pronto, se empieza desde 0 (llegará antes de la revelación); si la canción se acabaría
    antes que el vídeo, se adelanta lo justo."""
    inicio = momento - revelacion
    if inicio < 0:
        return 0.0, (f"el momento fuerte ({momento:g} s) llega antes que la revelación "
                     f"({revelacion:.1f} s): la música empieza desde 0 y sonará {-inicio:.1f} s antes")
    if inicio + total > duracion_cancion:
        nuevo = max(0.0, duracion_cancion - total)
        return round(nuevo, 2), (f"empezando en {inicio:.1f} s la canción se acabaría antes que el vídeo: "
                                 f"empieza en {nuevo:.1f} s y el momento fuerte suena {inicio - nuevo:.1f} s antes")
    return round(inicio, 2), None
