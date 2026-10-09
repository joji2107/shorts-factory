"""Genera una animación por código para un short y la registra como clip de tipo 'animacion'.

    docker run --rm -t -v "$PWD:/proyecto" shorts-mapas \
        python /proyecto/scripts/animar.py 019-huracan_isaias huracan_isaias_mapa

Lee la ficha shorts/<short>/animaciones/<nombre>.json (su "tipo" dice qué módulo de
scripts/animaciones/ la dibuja), deja el vídeo en data/animaciones/<nombre>.mp4 con un
<nombre>.json al lado (aviso, hora y fuentes usadas) y añade o actualiza su línea en
biblioteca/indice.csv (tipo 'animacion': solo entra en un short con [plano], nunca en el
relleno). En el guion se usa como cualquier clip: [plano <nombre> 0 8].

Va en su propia imagen (Dockerfile.mapas: matplotlib y pyshp) para que shorts-whisper siga
con lo justo. Se vuelve a lanzar cuando cambien los datos (un aviso nuevo del NHC).
"""
import argparse
import csv
import importlib
import json
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ANIMACIONES = RAIZ / "data" / "animaciones"
CACHE = RAIZ / "data" / "cache"
INDICE = RAIZ / "biblioteca" / "indice.csv"
sys.path.insert(0, str(RAIZ / "scripts"))

from animaciones import TIPOS  # noqa: E402

COLUMNAS = ["archivo", "tipo", "fuente", "autor", "url", "licencia", "licencia_url", "atribucion",
            "fecha", "etiquetas"]


def registrar(nombre, ficha, usado):
    """Añade (o sustituye) la línea de la animación en el índice, con sus fuentes."""
    fila = {
        "archivo": f"{nombre}.mp4", "tipo": "animacion", "fuente": usado["fuente"],
        "autor": "Generada con scripts/animar.py", "url": usado["url"],
        "licencia": usado["licencia"], "licencia_url": usado.get("licencia_url", ""),
        "atribucion": "", "fecha": date.today().isoformat(),
        "etiquetas": ";".join(ficha.get("etiquetas", [nombre.rsplit("_", 1)[0]]) + ["animacion"]),
    }
    # Las demás líneas se dejan tal cual (sin volver a escribirlas con csv, que podría cambiar
    # sus comillas): solo se quita la de esta animación, si ya estaba, y se añade la nueva
    lineas = INDICE.read_text(encoding="utf-8").splitlines(keepends=True)
    lineas = [l for l in lineas if not l.startswith(f"{fila['archivo']},")]
    if lineas and not lineas[-1].endswith("\n"):
        lineas[-1] += "\n"
    with INDICE.open("w", encoding="utf-8", newline="") as f:
        f.writelines(lineas)
        csv.writer(f, lineterminator="\n").writerow([fila[c] for c in COLUMNAS])


def main():
    parser = argparse.ArgumentParser(description="Genera una animación por código para un short")
    parser.add_argument("short", help="carpeta del short en shorts/ (019-huracan_isaias)")
    parser.add_argument("nombre", help="nombre de la animación (su ficha y el clip)")
    args = parser.parse_args()

    ruta_ficha = RAIZ / "shorts" / args.short / "animaciones" / f"{args.nombre}.json"
    if not ruta_ficha.exists():
        raise SystemExit(f"No está la ficha {ruta_ficha.relative_to(RAIZ)}")
    ficha = json.loads(ruta_ficha.read_text(encoding="utf-8"))
    if ficha.get("tipo") not in TIPOS:
        raise SystemExit(f"Tipo de animación desconocido: {ficha.get('tipo')!r} (hay: {', '.join(TIPOS)})")

    ANIMACIONES.mkdir(parents=True, exist_ok=True)
    salida = ANIMACIONES / f"{args.nombre}.mp4"
    print(f"Generando {salida.relative_to(RAIZ)} ({ficha['tipo']})...")
    usado = importlib.import_module(TIPOS[ficha["tipo"]]).crear(ficha, salida, CACHE)
    usado.update({"short": args.short, "tipo": ficha["tipo"]})
    (ANIMACIONES / f"{args.nombre}.json").write_text(json.dumps(usado, ensure_ascii=False, indent=2) + "\n",
                                                     encoding="utf-8")
    registrar(args.nombre, ficha, usado)
    print(f"Listo: {usado['fotogramas']} fotogramas. Aviso {usado.get('aviso', '-')}. "
          f"Registrada en biblioteca/indice.csv como 'animacion'.")


if __name__ == "__main__":
    main()
