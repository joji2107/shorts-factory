"""Herramientas comunes a todos los pasos."""
import subprocess


def ejecutar(comando):
    """Ejecuta un comando externo (como ffmpeg) y detiene todo si falla."""
    comando = [str(parte) for parte in comando]
    resultado = subprocess.run(comando, capture_output=True, text=True)
    if resultado.returncode != 0:
        print(resultado.stderr[-2000:])
        raise RuntimeError(f"Ha fallado el comando: {comando[0]}")
    return resultado
