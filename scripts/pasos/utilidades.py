"""Herramientas comunes a todos los pasos."""
import re
import subprocess


def ejecutar(comando):
    """Ejecuta un comando externo (como ffmpeg) y detiene todo si falla."""
    comando = [str(parte) for parte in comando]
    resultado = subprocess.run(comando, capture_output=True, text=True)
    if resultado.returncode != 0:
        print(resultado.stderr[-2000:])
        raise RuntimeError(f"Ha fallado el comando: {comando[0]}")
    return resultado


def duracion(archivo):
    """Devuelve la duración de un archivo de audio o vídeo, en segundos."""
    resultado = ejecutar([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration", "-of", "csv=p=0", archivo,
    ])
    return float(resultado.stdout.strip())


def silencio_inicial(archivo, umbral="-45dB"):
    """Segundos de silencio al principio de un audio (0 si empieza sonando).
    Algunos efectos traen silencio delante (error_01: 0,6 s) y sonarían tarde."""
    resultado = ejecutar([
        "ffmpeg", "-hide_banner", "-nostats", "-i", archivo,
        "-af", f"silencedetect=n={umbral}:d=0.02", "-f", "null", "-",
    ])
    inicio = re.search(r"silence_start: (-?[\d.]+)", resultado.stderr)
    fin = re.search(r"silence_end: ([\d.]+)", resultado.stderr)
    if inicio and fin and float(inicio.group(1)) <= 0.01:
        return float(fin.group(1))
    return 0.0
