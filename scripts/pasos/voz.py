"""Paso 1: procesar la voz con la cadena de filtros de la configuración."""
from .utilidades import ejecutar


def procesar_voz(original, salida, config):
    ejecutar([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", config["inicio"], "-i", original,
        # Primero a mono: así la normalización final de la cadena mide la señal
        # tal como se va a guardar (si se pasa a mono al final, pierde 3 dB)
        "-af", "aformat=channel_layouts=mono," + config["cadena"],
        "-ac", "1", "-ar", "48000", "-c:a", "pcm_s24le",
        salida,
    ])
