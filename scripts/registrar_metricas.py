"""Registra publicaciones y métricas de los shorts (shorts/publicaciones.csv y
shorts/metricas.csv). Lo usa la skill registrar-metricas.

Uso:
  python registrar_metricas.py publicacion 007-tema youtube "2026-10-05 18:00" [--archivo X.mp4]
  python registrar_metricas.py medida 001-pulpo youtube 48h --visualizaciones 1200 \\
      --se-quedaron 71.5 --duracion-media 29 --likes 40 --comentarios 3 [--medido "..."]
  python registrar_metricas.py pendientes

Las cifras que no se sepan se dejan sin poner: quedan vacías y se avisa de que faltan.
Con --carpeta se trabaja sobre otra carpeta (para probar sin tocar los archivos reales).
"""
import argparse
import sys
from pathlib import Path

import metricas
from crear_short import RAIZ


def mostrar_pendientes(carpeta):
    lista = metricas.pendientes(carpeta=carpeta)
    ahora = [m for m in lista if m["estado"] == "pendiente"]
    proximas = [m for m in lista if m["estado"] == "próxima"]
    print(f"Medidas pendientes ahora: {len(ahora) or 'ninguna'}")
    for m in ahora:
        print(f"  {m['short']} {m['plataforma']} {m['momento']} (desde {m['cuando']:%Y-%m-%d %H:%M})")
    print(f"Próximas: {len(proximas) or 'ninguna'}")
    for m in proximas[:8]:
        print(f"  {m['short']} {m['plataforma']} {m['momento']} ({m['cuando']:%Y-%m-%d %H:%M})")
    if len(proximas) > 8:
        print(f"  ... y {len(proximas) - 8} más")


def main():
    parser = argparse.ArgumentParser(description="Publicaciones y métricas de los shorts")
    parser.add_argument("--carpeta", default=str(metricas.CARPETA),
                        help="Carpeta de los CSV (relativa a la raíz del proyecto)")
    ordenes = parser.add_subparsers(dest="orden", required=True)

    p = ordenes.add_parser("publicacion", help="Anota que un short se ha publicado en una plataforma")
    p.add_argument("short")
    p.add_argument("plataforma", choices=metricas.PLATAFORMAS)
    p.add_argument("publicado", help="Fecha y hora: 'AAAA-MM-DD HH:MM'")
    p.add_argument("--archivo", default="", help="Vídeo de data/listos/ si hay más de uno")
    p.add_argument("--notas", default="")

    m = ordenes.add_parser("medida", help="Añade las cifras de un short a las 48h o a los 7d")
    m.add_argument("short")
    m.add_argument("plataforma", choices=metricas.PLATAFORMAS)
    m.add_argument("momento", choices=list(metricas.MOMENTOS))
    m.add_argument("--medido", default="", help="Cuándo se miraron: 'AAAA-MM-DD HH:MM' (por defecto, ahora)")
    m.add_argument("--visualizaciones")
    m.add_argument("--se-quedaron", dest="se_quedaron_pct", help="%% que se quedó a verlo (solo YouTube)")
    m.add_argument("--duracion-media", dest="duracion_media_s", help="Duración media vista, en segundos")
    m.add_argument("--likes")
    m.add_argument("--comentarios")
    m.add_argument("--compartidos")
    m.add_argument("--seguidores", help="Seguidores ganados con este short")
    m.add_argument("--notas", default="")
    m.add_argument("--reemplazar", action="store_true",
                   help="Corrige o completa una medida ya registrada (lo que no se indica se conserva)")

    ordenes.add_parser("pendientes", help="Medidas que tocan ahora y las próximas")
    args = parser.parse_args()

    carpeta = RAIZ / args.carpeta if not Path(args.carpeta).is_absolute() else Path(args.carpeta)
    try:
        if args.orden == "publicacion":
            fila = metricas.nueva_publicacion(args.short, args.plataforma, args.publicado,
                                              args.archivo, args.notas, carpeta)
            print(f"Publicación anotada: {fila['short']} en {fila['plataforma']} el {fila['publicado']} "
                  f"({fila['archivo']}, md5 {fila['md5']})")
        elif args.orden == "medida":
            fila, faltan, avisos = metricas.nueva_medida(vars(args), args.reemplazar, carpeta)
            print(f"Medida anotada: {fila['short']} {fila['plataforma']} {fila['momento']} "
                  f"(medida el {fila['medido']})")
            for campo in metricas.NUMEROS + metricas.FICHA:
                if fila[campo]:
                    print(f"  {campo}: {fila[campo]}")
            print(f"Faltan: {', '.join(faltan)}" if faltan else "No falta ningún dato.")
            for aviso in avisos:
                print(f"AVISO: {aviso}")
        else:
            mostrar_pendientes(carpeta)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
