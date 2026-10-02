"""Vigila la carpeta bandeja: cada audio que aparece se convierte en un short.

Uso: python vigilar_bandeja.py [--plantilla curiosidades] [--intervalo 5]

El nombre del archivo decide el short y el tema: "002-caballo.wav" crea el short
"002-caballo" usando los clips del índice con la etiqueta "caballo".

Flujo:
  data/bandeja/  -> el audio pasa a data/archivo/ y se crea el short
                 -> el vídeo terminado se copia a data/revision/ para revisarlo
                 -> si algo falla, el audio va a data/errores/ con un .log del error
Todo queda anotado en data/registro.log.
"""
import argparse
import csv
import json
import shutil
import time
import traceback
from datetime import datetime
from pathlib import Path

from crear_short import RAIZ, crear

DATA = RAIZ / "data"
BANDEJA = DATA / "bandeja"
ARCHIVO = DATA / "archivo"
ERRORES = DATA / "errores"
REVISION = DATA / "revision"
REGISTRO = DATA / "registro.log"
EXTENSIONES = {".wav", ".mp3", ".m4a", ".aif", ".aiff"}


def registrar(mensaje):
    """Escribe un mensaje con fecha y hora en pantalla y en el registro."""
    linea = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {mensaje}"
    print(linea, flush=True)
    with REGISTRO.open("a", encoding="utf-8") as f:
        f.write(linea + "\n")


def esta_completo(archivo, espera=3):
    """Un archivo está completo si su tamaño no cambia durante unos segundos
    (evita empezar con un archivo que todavía se está copiando)."""
    tamano = archivo.stat().st_size
    time.sleep(espera)
    return tamano > 0 and archivo.stat().st_size == tamano


def clips_por_tema(tema):
    """Busca en el índice de la biblioteca los vídeos con esa etiqueta."""
    indice = RAIZ / "biblioteca" / "indice.csv"
    with indice.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        filas = list(lector)
    # Cada línea debe tener tantas columnas como la cabecera
    for numero, fila in enumerate(filas, start=2):
        if None in fila or None in fila.values():
            raise RuntimeError(
                f"La línea {numero} de biblioteca/indice.csv no tiene "
                f"{len(lector.fieldnames)} columnas ({', '.join(lector.fieldnames)})"
            )
    return [
        Path(fila["archivo"]).stem
        for fila in filas
        if fila["tipo"].strip() == "video" and tema in fila["etiquetas"].strip().split(";")
    ]


def preparar_receta(nombre, audio, plantilla):
    """Crea (o actualiza) shorts/<nombre>/config.json a partir de la plantilla."""
    receta = RAIZ / "shorts" / nombre
    ruta = receta / "config.json"
    if ruta.exists():
        config = json.loads(ruta.read_text(encoding="utf-8"))
    else:
        ruta_plantilla = RAIZ / "config" / "plantillas" / f"{plantilla}.json"
        config = json.loads(ruta_plantilla.read_text(encoding="utf-8"))

    config["audio_original"] = str(audio.relative_to(RAIZ))

    # Si la receta no dice qué clips usar, se eligen por el tema del nombre
    tiene_clips = config.get("video", {}).get("clips")
    if not tiene_clips and not (receta / "cortes.txt").exists():
        tema = nombre.split("-", 1)[-1]          # "002-caballo" -> "caballo"
        clips = clips_por_tema(tema)
        if not clips:
            raise RuntimeError(f"No hay vídeos con la etiqueta '{tema}' en biblioteca/indice.csv")
        config.setdefault("video", {})["clips"] = clips
        registrar(f"       {len(clips)} clips con la etiqueta '{tema}': {', '.join(clips)}")

    receta.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# Archivos de trabajo pesados que se borran al terminar un short. Se conservan
# los pequeños (voz, palabras, subtítulos, listas de cortes y mezcla), que permiten
# retocar el short después sin repetir la transcripción.
PESADOS = ["fondo.mp4", "mezcla.wav"]


def limpiar(nombre):
    trabajo = DATA / "shorts" / nombre
    liberado = 0
    for archivo in PESADOS:
        ruta = trabajo / archivo
        if ruta.exists():
            liberado += ruta.stat().st_size
            ruta.unlink()
    return liberado / 1_000_000


def procesar(audio, plantilla):
    nombre = audio.stem
    archivado = ARCHIVO / audio.name
    shutil.move(audio, archivado)   # sale de la bandeja: no se procesa dos veces
    registrar(f"INICIO {nombre}")
    inicio = time.perf_counter()
    try:
        preparar_receta(nombre, archivado, plantilla)
        final = crear(nombre, rehacer="voz")   # audio nuevo: se rehace todo desde la voz
        destino = REVISION / f"{nombre}.mp4"
        shutil.move(final, destino)            # se mueve: el vídeo no queda duplicado
        megas = limpiar(nombre)
        minutos = (time.perf_counter() - inicio) / 60
        registrar(f"OK     {nombre} en {minutos:.1f} min -> {destino.relative_to(RAIZ)} "
                  f"({megas:.0f} MB de archivos temporales borrados)")
    except Exception as error:
        shutil.move(archivado, ERRORES / audio.name)
        (ERRORES / f"{nombre}.log").write_text(traceback.format_exc(), encoding="utf-8")
        registrar(f"ERROR  {nombre}: {error} (detalles en data/errores/{nombre}.log)")


def main():
    parser = argparse.ArgumentParser(description="Vigila la bandeja y crea un short por audio")
    parser.add_argument("--plantilla", default="curiosidades",
                        help="Plantilla de config/plantillas/ para los shorts nuevos")
    parser.add_argument("--intervalo", type=int, default=5,
                        help="Segundos entre cada revisión de la bandeja")
    args = parser.parse_args()

    for carpeta in (BANDEJA, ARCHIVO, ERRORES, REVISION):
        carpeta.mkdir(parents=True, exist_ok=True)

    registrar(f"Vigilando data/bandeja cada {args.intervalo} s "
              f"(plantilla '{args.plantilla}'). Ctrl+C para parar.")
    try:
        while True:
            for audio in sorted(BANDEJA.iterdir()):
                if audio.suffix.lower() in EXTENSIONES and esta_completo(audio):
                    procesar(audio, args.plantilla)
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        registrar("Vigilancia detenida")


if __name__ == "__main__":
    main()
