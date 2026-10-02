"""Crea un short a partir de su configuración, paso a paso.

Uso: python crear_short.py <nombre-del-short> [--desde PASO]
"""
import argparse
import json
import time
from pathlib import Path

from pasos.voz import procesar_voz
from pasos.transcripcion import transcribir
from pasos.subtitulos import generar_ass

RAIZ = Path(__file__).resolve().parent.parent   # la carpeta del proyecto
PASOS = ["voz", "transcripcion", "subtitulos"]


def fusionar(base, cambios):
    """Combina dos configuraciones: los cambios sustituyen a la base."""
    resultado = dict(base)
    for clave, valor in cambios.items():
        if isinstance(valor, dict) and isinstance(resultado.get(clave), dict):
            resultado[clave] = fusionar(resultado[clave], valor)
        else:
            resultado[clave] = valor
    return resultado


def cargar_config(nombre):
    base = json.loads((RAIZ / "config" / "por_defecto.json").read_text(encoding="utf-8"))
    ruta_propia = RAIZ / "shorts" / nombre / "config.json"
    propia = json.loads(ruta_propia.read_text(encoding="utf-8")) if ruta_propia.exists() else {}
    return fusionar(base, propia)


def main():
    parser = argparse.ArgumentParser(description="Crea un short paso a paso")
    parser.add_argument("short", help="Carpeta del short, por ejemplo 001-pulpo")
    parser.add_argument("--desde", choices=PASOS, help="Rehacer a partir de este paso")
    args = parser.parse_args()

    config = cargar_config(args.short)
    trabajo = RAIZ / "data" / "shorts" / args.short
    trabajo.mkdir(parents=True, exist_ok=True)

    archivos = {
        "voz": trabajo / "voz.wav",
        "transcripcion": trabajo / "palabras.json",
        "subtitulos": trabajo / "subtitulos.ass",
    }

    inicio = time.perf_counter()
    rehacer = False
    for paso in PASOS:
        if args.desde == paso:
            rehacer = True
        if not rehacer and archivos[paso].exists():
            print(f"== {paso}: ya existe, se salta")
            continue
        rehacer = True   # si un paso se rehace, todos los siguientes también
        print(f"== {paso}")

        if paso == "voz":
            procesar_voz(RAIZ / config["audio_original"], archivos["voz"], config["voz"])
        elif paso == "transcripcion":
            transcribir(archivos["voz"], trabajo / "subtitulos.srt",
                        archivos["transcripcion"], config["transcripcion"])
        elif paso == "subtitulos":
            generar_ass(archivos["transcripcion"], archivos["subtitulos"], config["subtitulos"])

    print(f"\nListo en {time.perf_counter() - inicio:.1f} s. Resultados en {trabajo}")


if __name__ == "__main__":
    main()
