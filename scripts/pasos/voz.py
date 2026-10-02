"""Paso 1: procesar la voz con la cadena de filtros de la configuración."""
from .utilidades import ejecutar


def procesar_voz(original, salida, config):
    ejecutar([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", config["inicio"], "-i", original,
        "-af", config["cadena"],
        "-ac", "1", "-ar", "48000", "-c:a", "pcm_s24le",
        salida,
    ])
