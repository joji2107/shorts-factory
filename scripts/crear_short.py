"""Crea un short a partir de su configuración, paso a paso.

Uso: python crear_short.py <nombre-del-short> [--rehacer PASO]
"""
import argparse
import json
import time
from pathlib import Path

from pasos.voz import procesar_voz
from pasos.transcripcion import transcribir
from pasos.subtitulos import generar_ass
from pasos.cortes import crear_edl, elegir_efectos
from pasos.montaje import generar_fondo, render

RAIZ = Path(__file__).resolve().parent.parent   # la carpeta del proyecto

# Cada paso y los pasos de los que depende. El orden es el de ejecución.
DEPENDE_DE = {
    "voz": [],
    "transcripcion": ["voz"],
    "subtitulos": ["transcripcion"],
    "fondo": ["transcripcion"],
    "render": ["fondo", "voz", "subtitulos"],
}
PASOS = list(DEPENDE_DE)


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


def crear(nombre, rehacer=None):
    """Crea (o actualiza) el short 'nombre' y devuelve la ruta del vídeo final."""
    config = cargar_config(nombre)
    receta = RAIZ / "shorts" / nombre
    trabajo = RAIZ / "data" / "shorts" / nombre
    trabajo.mkdir(parents=True, exist_ok=True)
    biblioteca = RAIZ / "data" / "biblioteca" / "video"

    # Con cortes escritos a mano, el fondo no depende de la voz
    edl_manual = receta / "cortes.txt"
    edl = edl_manual if edl_manual.exists() else trabajo / "cortes_auto.txt"
    depende_de = dict(DEPENDE_DE)
    if edl_manual.exists():
        depende_de["fondo"] = []

    archivos = {
        "voz": trabajo / "voz.wav",
        "transcripcion": trabajo / "palabras.json",
        "subtitulos": trabajo / "subtitulos.ass",
        "fondo": trabajo / "fondo.mp4",
        "render": trabajo / "final.mp4",
    }

    inicio = time.perf_counter()
    rehechos = set()
    for paso in PASOS:
        necesario = (
            paso == rehacer
            or not archivos[paso].exists()
            or any(dep in rehechos for dep in depende_de[paso])
        )
        if not necesario:
            print(f"== {paso}: ya existe, se salta")
            continue
        print(f"== {paso}")

        if paso == "voz":
            procesar_voz(RAIZ / config["audio_original"], archivos["voz"], config["voz"])
        elif paso == "transcripcion":
            transcribir(archivos["voz"], trabajo / "subtitulos.srt",
                        archivos["transcripcion"], config["transcripcion"])
        elif paso == "subtitulos":
            generar_ass(archivos["transcripcion"], archivos["subtitulos"], config["subtitulos"])
        elif paso == "fondo":
            if not edl_manual.exists():
                crear_edl(archivos["transcripcion"], archivos["voz"], edl, biblioteca, config)
            generar_fondo(edl, biblioteca, trabajo / "cortes", archivos["fondo"], config["video"])
        elif paso == "render":
            # Efectos escritos a mano en la configuración, o elegidos automáticamente
            efectos = config["efectos"]["lista"]
            if not efectos and config["efectos"]["automaticos"] > 0:
                efectos = elegir_efectos(edl, archivos["transcripcion"], config)
            render(archivos["fondo"], archivos["voz"], archivos["subtitulos"],
                   trabajo / "mezcla.txt", archivos["render"], RAIZ, config, efectos)

        rehechos.add(paso)

    print(f"\nListo en {time.perf_counter() - inicio:.1f} s. Resultados en {trabajo}")
    return archivos["render"]


def main():
    parser = argparse.ArgumentParser(description="Crea un short paso a paso")
    parser.add_argument("short", help="Carpeta del short, por ejemplo 001-pulpo")
    parser.add_argument("--rehacer", choices=PASOS,
                        help="Rehace este paso y los que dependen de él")
    args = parser.parse_args()
    crear(args.short, args.rehacer)


if __name__ == "__main__":
    main()
