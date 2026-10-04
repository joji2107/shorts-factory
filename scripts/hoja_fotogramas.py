"""Hoja de fotogramas de un clip: un fotograma por segundo en mosaico, con el segundo
escrito encima. Sirve para elegir los planos protagonistas de la fábrica 2.0 (qué clip y
desde qué segundo: [plano clip desde largo]) mirando lo que pasa en cada momento.

Uso: python hoja_fotogramas.py volcan_01 volcan_03 ...   (o un tema: volcan)

Las hojas se guardan en data/cache/fotogramas/<clip>.jpg (la biblioteca no se toca).
"""
import argparse
import math

import material
from crear_short import RAIZ
from pasos.utilidades import duracion, ejecutar

SALIDA = RAIZ / "data" / "cache" / "fotogramas"
COLUMNAS = 6
ALTO = 180          # píxeles de alto de cada fotograma (los verticales salen más estrechos)


def hoja(clip):
    video = material.VIDEOS / f"{clip}.mp4"
    if not video.is_file():
        raise SystemExit(f"No existe data/biblioteca/video/{clip}.mp4")
    segundos = math.ceil(duracion(video))
    filas = math.ceil(segundos / COLUMNAS)
    salida = SALIDA / f"{clip}.jpg"
    ejecutar([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", video, "-an",
        "-vf", (f"fps=1,scale=-2:{ALTO},"
                "drawtext=font='DejaVu Sans':text='%{eif\\:t\\:d} s':x=6:y=6:fontsize=26:"
                "fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=4,"
                f"tile={COLUMNAS}x{filas}:padding=4:color=black"),
        "-frames:v", "1", "-q:v", "3", salida,
    ])
    return salida, segundos


def main():
    parser = argparse.ArgumentParser(description="Hoja de fotogramas (uno por segundo) de unos clips")
    parser.add_argument("clips", nargs="+", help="Nombres de clips (volcan_01) o un tema (volcan)")
    args = parser.parse_args()
    SALIDA.mkdir(parents=True, exist_ok=True)

    clips = []
    for nombre in args.clips:
        clips += [nombre] if (material.VIDEOS / f"{nombre}.mp4").is_file() else material.clips_del_tema(nombre)
    if not clips:
        raise SystemExit(f"Ni clips ni temas con esos nombres: {', '.join(args.clips)}")
    for clip in clips:
        salida, segundos = hoja(clip)
        print(f"{salida.relative_to(RAIZ)}: {segundos} s, del segundo 0 (arriba a la izquierda) "
              f"al {segundos - 1}, {COLUMNAS} por fila")


if __name__ == "__main__":
    main()
