"""Paso 1: procesar la voz con la cadena de filtros de la configuración."""
import re

from .utilidades import ejecutar, duracion


def detectar_voz(original, umbral="-45dB"):
    """Devuelve (inicio, fin) de la parte con voz, saltando el silencio del principio
    y del final de la grabación. Se usa cuando la configuración dice "inicio": "auto"."""
    texto = ejecutar([
        "ffmpeg", "-hide_banner", "-nostats", "-i", original,
        "-af", f"silencedetect=noise={umbral}:d=0.5", "-f", "null", "-",
    ]).stderr
    total = duracion(original)
    comienzos = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", texto)]
    finales = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", texto)]

    inicio, fin = 0.0, total
    # Si la grabación empieza en silencio, la voz empieza donde acaba ese silencio
    if comienzos and comienzos[0] <= 0.1 and finales:
        inicio = max(0.0, finales[0] - 0.3)
    # Si termina en silencio, se corta medio segundo después de la última palabra
    if comienzos and comienzos[-1] > inicio and (len(finales) < len(comienzos) or finales[-1] >= total - 0.1):
        fin = min(total, comienzos[-1] + 0.5)
    return inicio, fin


def procesar_voz(original, salida, config):
    if config["inicio"] == "auto":
        inicio, fin = detectar_voz(original)
        print(f"   voz detectada entre {inicio:.2f} y {fin:.2f} s")
        recorte = ["-ss", f"{inicio:.3f}", "-t", f"{fin - inicio:.3f}"]
    else:
        recorte = ["-ss", config["inicio"]]

    ejecutar([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        *recorte, "-i", original,
        # Primero a mono: así la normalización final de la cadena mide la señal
        # tal como se va a guardar (si se pasa a mono al final, pierde 3 dB)
        "-af", "aformat=channel_layouts=mono," + config["cadena"],
        "-ac", "1", "-ar", "48000", "-c:a", "pcm_s24le",
        salida,
    ])
