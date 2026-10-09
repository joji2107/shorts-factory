"""Hoja de fotogramas de un clip: un fotograma por segundo en mosaico, con el segundo
escrito encima (de una foto, los de su vídeo virtual: el movimiento Ken Burns). Sirve
para elegir los planos protagonistas de la fábrica 2.0 (qué clip y desde qué segundo:
[plano clip desde largo]) mirando lo que pasa en cada momento.

Uso: python hoja_fotogramas.py volcan_01 volcan_03 ...   (o un tema: volcan)

Las hojas se guardan en data/cache/fotogramas/<clip>.jpg (la biblioteca no se toca).
"""
import argparse
import math

import material
from crear_short import RAIZ, config_base
from pasos.clips import es_foto, existe_clip, filtro_foto, ruta_clip
from pasos.utilidades import duracion, ejecutar

SALIDA = RAIZ / "data" / "cache" / "fotogramas"
COLUMNAS = 6
ALTO = 180          # píxeles de alto de cada fotograma (los verticales salen más estrechos)


def hoja(clip):
    try:
        ruta = ruta_clip(material.VIDEOS, clip)
    except RuntimeError as error:
        raise SystemExit(str(error))
    if es_foto(ruta):
        # Una foto: las hojas enseñan su vídeo virtual (el movimiento que hará en el short)
        imagen = config_base()["video"]["imagen"]
        segundos_imagen = imagen["segundos"]
        segundos = math.ceil(segundos_imagen)
        # -t antes de -i limita la entrada (la foto se repite sin fin con -loop 1)
        entrada = ["-loop", "1", "-framerate", "30", "-t", segundos_imagen, "-i", ruta]
        previo = filtro_foto(ruta, 0.0, imagen) + ","
    else:
        segundos = math.ceil(duracion(ruta))
        entrada = ["-i", ruta]
        previo = ""
    filas = math.ceil(segundos / COLUMNAS)
    salida = SALIDA / f"{clip}.jpg"
    ejecutar([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *entrada, "-an",
        "-vf", (f"{previo}fps=1,scale=-2:{ALTO},"
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
        es_clip = existe_clip(material.VIDEOS, nombre)
        clips += [nombre] if es_clip else material.clips_del_tema(nombre)
    if not clips:
        raise SystemExit(f"Ni clips ni temas con esos nombres: {', '.join(args.clips)}")
    for clip in clips:
        salida, segundos = hoja(clip)
        print(f"{salida.relative_to(RAIZ)}: {segundos} s, del segundo 0 (arriba a la izquierda) "
              f"al {segundos - 1}, {COLUMNAS} por fila")


if __name__ == "__main__":
    main()
