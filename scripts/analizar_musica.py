"""Analiza la energía de las canciones de la biblioteca y la guarda en biblioteca/musica.json.

Uso: python analizar_musica.py [--todas]

Solo analiza las canciones que aún no están en musica.json (con --todas, todas otra vez).
Para cada una guarda su duración, la mediana de sonoridad, el momento fuerte (segundo),
cuánto sube ahí y cuánto queda por encima de la mediana, si es plana (sin momento fuerte)
y la curva de energía (LUFS por segundo). Lo usa el render con musica.inicio "auto".

musica.json va a Git (data/ no): es pequeño y se puede regenerar. Cada canción va en una
sola línea, para que los cambios en Git se lean bien.
"""
import argparse
import json

from crear_short import RAIZ
from pasos.musica import analizar, leer_energia
from pasos.utilidades import duracion

CARPETA = RAIZ / "data" / "biblioteca" / "musica"
SALIDA = RAIZ / "biblioteca" / "musica.json"


def escribir(datos):
    lineas = [f"  {json.dumps(nombre)}: {json.dumps(datos[nombre], ensure_ascii=False)}"
              for nombre in sorted(datos)]
    SALIDA.write_text("{\n" + ",\n".join(lineas) + "\n}\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Energía de las canciones de la biblioteca")
    parser.add_argument("--todas", action="store_true", help="Vuelve a analizar también las ya analizadas")
    args = parser.parse_args()

    datos = leer_energia(RAIZ)
    canciones = sorted(CARPETA.glob("*.mp3"))
    nuevas = [c for c in canciones if args.todas or c.name not in datos]
    for cancion in nuevas:
        datos[cancion.name] = analizar(cancion, duracion(cancion))
    escribir(datos)
    json.loads(SALIDA.read_text(encoding="utf-8"))      # nunca se deja un JSON roto

    print(f"{len(nuevas)} analizadas, {len(datos)} en {SALIDA.relative_to(RAIZ)}\n")
    print(f"{'canción':20} {'dura':>6} {'momento':>8} {'subida':>7} {'sobre med.':>11}")
    for nombre in sorted(datos):
        d = datos[nombre]
        momento = f"{d['momento_fuerte']} s" if d["momento_fuerte"] is not None else "—"
        estado = "plana" if d["plana"] else "sirve"
        print(f"{nombre:20} {d['duracion']:5.0f}s {momento:>8} {d['subida_db']:6.1f}  {d['sobre_mediana_db']:6.1f} dB   {estado}")


if __name__ == "__main__":
    main()
