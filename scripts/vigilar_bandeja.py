"""Vigila la carpeta bandeja: cada audio que aparece se convierte en un short.

Uso: python vigilar_bandeja.py [--plantilla curiosidades] [--intervalo 5]

El nombre del archivo decide el short y el tema: "002-caballo.wav" crea el short
"002-caballo" usando los clips del índice con la etiqueta "caballo".

Flujo:
  data/bandeja/  -> el audio pasa a data/archivo/ y se crea el short
                 -> el vídeo terminado se mueve a data/revision/ para revisarlo
                 -> si algo falla, el audio va a data/errores/ con un .log del error
Todo queda anotado en data/registro.log.
"""
import argparse
import json
import shutil
import time
import traceback
from datetime import datetime
from pathlib import Path

import lectura
import material
from crear_short import RAIZ, crear, fusionar

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


def preparar_receta(nombre, audio, plantilla):
    """Crea (o actualiza) shorts/<nombre>/config.json a partir de la plantilla.
    Una receta *reservada* (la crea la skill guion-short antes de grabar: tiene guion
    pero aún no audio_original) solo guarda lo que cambia, así que se pone encima de
    la plantilla. Una receta de un short ya grabado se usa tal cual."""
    receta = RAIZ / "shorts" / nombre
    ruta = receta / "config.json"
    ruta_plantilla = RAIZ / "config" / "plantillas" / f"{plantilla}.json"
    config_plantilla = json.loads(ruta_plantilla.read_text(encoding="utf-8"))
    if ruta.exists():
        config = json.loads(ruta.read_text(encoding="utf-8"))
        if "audio_original" not in config:
            config = fusionar(config_plantilla, config)
            registrar(f"       Receta reservada: se aplica encima de la plantilla '{plantilla}'")
    else:
        config = config_plantilla

    config["audio_original"] = str(audio.relative_to(RAIZ))

    # Los clips se eligen después de la voz, con la duración real (despues_de_voz).
    # Aquí solo se comprueba que el tema tenga alguno, para fallar antes de procesar.
    tema = nombre.split("-", 1)[-1]              # "002-caballo" -> "caballo"
    tiene_clips = config.get("video", {}).get("clips")
    if not tiene_clips and not (receta / "cortes.txt").exists() and not material.clips_del_tema(tema):
        raise RuntimeError(f"No hay vídeos con la etiqueta '{tema}' en biblioteca/indice.csv")

    receta.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def material_despues_de_voz(nombre):
    """Devuelve la función que crear() llama cuando la voz está lista, con la duración
    real del short (voz detectada + cola). Si la receta no tiene clips, los elige: solo
    los necesarios, empezando por los menos usados (al azar entre empatados), y los
    escribe en la receta (al rehacer se usan los mismos). Si ya tiene clips, comprueba
    que alcancen. Si no hay material suficiente, lo anota antes de renderizar."""
    receta = RAIZ / "shorts" / nombre

    def comprobar(config, total):
        if (receta / "cortes.txt").exists():
            return                               # cortes a mano: no hay nada que elegir
        tema = nombre.split("-", 1)[-1]
        clips = config["video"]["clips"]
        if not clips:
            clips, estado = material.elegir_clips(tema, total, config)
            config["video"]["clips"] = clips
            ruta = receta / "config.json"
            propia = json.loads(ruta.read_text(encoding="utf-8"))
            propia.setdefault("video", {})["clips"] = clips
            ruta.write_text(json.dumps(propia, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            registrar(f"       {len(clips)} de {len(material.clips_del_tema(tema))} clips de '{tema}' "
                      f"para {total:.1f} s (material {estado}): {', '.join(clips)}")
        else:
            estado = material.estado(material.duraciones(clips), total, config["video"])
            registrar(f"       Los {len(clips)} clips de la receta para {total:.1f} s: material {estado}")
        if estado != "suficiente":
            registrar(f"       AVISO: material {estado} para {total:.1f} s (menos de {material.MIN_CLIPS} "
                      f"clips o se repetirían planos). Usa evaluar_material para ver cuántos faltan")

    return comprobar


def anotar_lectura(nombre):
    """Añade la velocidad de lectura de esta grabación a config/lectura.json. Se mide de
    la primera palabra a la última: el silencio o el ruido grabados después no cuentan."""
    trabajo = DATA / "shorts" / nombre
    transcritas = json.loads((trabajo / "palabras.json").read_text(encoding="utf-8"))
    palabras = len(transcritas)
    segundos = transcritas[-1]["fin"] - transcritas[0]["inicio"]
    esta, media = lectura.anadir_muestra(nombre, palabras, segundos)
    registrar(f"       Lectura: {palabras} palabras en {segundos:.1f} s ({esta:.2f} por segundo); "
              f"velocidad de referencia: {media:.2f}")


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
    if archivado.exists():
        # Nunca se sobrescribe una grabación archivada: la nueva lleva la fecha y la hora
        archivado = ARCHIVO / f"{nombre}_{datetime.now():%Y%m%d-%H%M}{audio.suffix}"
    shutil.move(audio, archivado)   # sale de la bandeja: no se procesa dos veces
    registrar(f"INICIO {nombre}")
    if archivado.name != audio.name:
        registrar(f"       Ya había un {audio.name} archivado: el nuevo se guarda como {archivado.name}")
    inicio = time.perf_counter()
    try:
        preparar_receta(nombre, archivado, plantilla)
        # Audio nuevo: se rehace todo desde la voz
        final = crear(nombre, rehacer="voz", despues_de_voz=material_despues_de_voz(nombre))
        destino = REVISION / f"{nombre}.mp4"
        shutil.move(final, destino)            # se mueve: el vídeo no queda duplicado
        megas = limpiar(nombre)
        minutos = (time.perf_counter() - inicio) / 60
        registrar(f"OK     {nombre} en {minutos:.1f} min -> {destino.relative_to(RAIZ)} "
                  f"({megas:.0f} MB de archivos temporales borrados)")
        try:                                   # si falla, el short ya está hecho: solo se avisa
            anotar_lectura(nombre)
        except Exception as error:
            registrar(f"       AVISO: no se ha podido anotar la velocidad de lectura: {error}")
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
    vacios = set()   # archivos de 0 bytes ya anotados en el registro
    try:
        while True:
            for audio in sorted(BANDEJA.iterdir()):
                if audio.suffix.lower() not in EXTENSIONES:
                    continue
                # Un archivo vacío se salta sin esperar y se anota una sola vez
                if audio.stat().st_size == 0:
                    if audio.name not in vacios:
                        registrar(f"VACÍO  {audio.name} ocupa 0 bytes: se ignora hasta que tenga contenido")
                        vacios.add(audio.name)
                    continue
                vacios.discard(audio.name)
                if esta_completo(audio):
                    procesar(audio, args.plantilla)
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        registrar("Vigilancia detenida")


if __name__ == "__main__":
    main()
