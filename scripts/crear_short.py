"""Crea un short a partir de su configuración, paso a paso.

Uso: python crear_short.py <nombre-del-short> [--rehacer PASO]
"""
import argparse
import json
import time
from pathlib import Path

from pasos.voz import procesar_voz
from pasos.transcripcion import transcribir
from pasos.respiros import crear_respiros
from pasos.clips import en_pantalla, es_foto, marcas_de_agua, medidas, ruta_clip
from pasos.marcas import en_la_transcripcion, flechas_del_guion, leer_marcas, respiros_del_guion
from pasos.subtitulos import generar_ass, palabras_del_guion
from pasos.cortes import crear_edl, elegir_efectos
from pasos.montaje import generar_fondo, render
from pasos.utilidades import duracion, silencio_inicial

RAIZ = Path(__file__).resolve().parent.parent   # la carpeta del proyecto

# Cada paso y los pasos de los que depende. El orden es el de ejecución.
# "respiros" (fábrica 2.0) solo se ejecuta con respiros.activo: si no, se salta sin
# contar como rehecho y los pasos siguientes trabajan con voz.wav y palabras.json.
DEPENDE_DE = {
    "voz": [],
    "transcripcion": ["voz"],
    "respiros": ["transcripcion"],
    "subtitulos": ["transcripcion", "respiros"],
    "fondo": ["transcripcion", "respiros"],
    "render": ["fondo", "voz", "subtitulos", "respiros"],
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


def anclar_a_palabras(efectos, json_palabras):
    """Los efectos con "palabra" (y "vez", si se repite: 1 la primera) empiezan justo al
    terminar esa palabra. Así siguen en su sitio aunque se vuelva a grabar la voz;
    los que llevan "momento" (segundo exacto, en el centro del efecto) no cambian.
    Si el archivo empieza con silencio, se adelanta ese silencio: lo que tiene que
    empezar al terminar la palabra es el sonido, no el archivo."""
    def limpia(texto):
        return texto.lower().strip("¿?¡!.,;:…\"'«»()")

    palabras = json.loads(json_palabras.read_text(encoding="utf-8"))
    resultado = []
    for efecto in efectos:
        if "palabra" in efecto:
            finales = [p["fin"] for p in palabras if limpia(p["palabra"]) == limpia(efecto["palabra"])]
            vez = efecto.get("vez", 1)
            if len(finales) < vez:
                # Whisper puede escribirla de otra manera ("1,5 km" por "un kilómetro y medio"):
                # sin ese efecto el short sigue saliendo, así que se avisa y se sigue
                print(f"   AVISO: la palabra '{efecto['palabra']}' (vez {vez}) del efecto "
                      f"{Path(efecto['archivo']).name} no está en la transcripción: el efecto no suena")
                continue
            # render centra cada efecto en su momento: medio efecto después del final de la palabra
            archivo = RAIZ / efecto["archivo"]
            momento = finales[vez - 1] + duracion(archivo) / 2 - silencio_inicial(archivo)
            print(f"   efecto {Path(efecto['archivo']).name} tras «{efecto['palabra']}» ({finales[vez - 1]:.2f} s)")
            efecto = {**efecto, "momento": momento}
        resultado.append(efecto)
    return resultado


def situar_flechas(guion, palabras, edl, biblioteca, config):
    """Las flechas del guion ([flecha x y]) en el vídeo: (inicio, fin, x, y) en la pantalla, y
    sus sonidos (efectos con "momento", que es el centro del efecto). Cada flecha aparece al
    empezar la palabra que va detrás de la marca, sobre el clip que se ve en ese momento
    (según la lista de cortes): x e y son de ese clip y se pasan a la pantalla con su encuadre."""
    marcas = flechas_del_guion(guion, config["flechas"]["segundos"]) if guion.exists() else []
    if not marcas:
        return [], []
    indices = en_la_transcripcion([m[0] for m in marcas], palabras, palabras_del_guion(guion))
    tramos, t = [], 0.0                 # (inicio, fin, clip), redondeado a fotogramas como el fondo
    for linea in edl.read_text(encoding="utf-8").splitlines():
        campos = linea.split()
        if campos:
            largo = round(float(campos[2] if len(campos) > 2 else config["video"]["segundos_corte"]) * 30) / 30
            tramos.append((t, t + largo, campos[0]))
            t += largo
    flechas, sonidos = [], []
    for (_, x, y, segundos, contexto), i in zip(marcas, indices):
        if i is None or i >= len(palabras):
            raise RuntimeError(f"[flecha {x:g} {y:g}] antes de «{contexto}»: no se encuentra en la transcripción")
        inicio = palabras[i]["inicio"]
        clip = next((c for a, b, c in tramos if a <= inicio < b), tramos[-1][2])
        ruta = ruta_clip(biblioteca, clip)
        ancho, alto = medidas(ruta)
        if es_foto(ruta):
            print(f"   AVISO: la flecha antes de «{contexto}» cae sobre una foto que se mueve: su sitio es aproximado")
        encuadre = "relleno" if es_foto(ruta) else config["video"]["encuadre"]
        px, py = en_pantalla(x, y, ancho, alto, encuadre)
        flechas.append((inicio, inicio + segundos, px, py))
        print(f"   flecha de {inicio:.2f} a {inicio + segundos:.2f} s sobre {clip} ({x:g}, {y:g}) "
              f"-> pantalla ({px:.0f}, {py:.0f}), antes de «{contexto}»")
        if config["flechas"].get("sonido"):
            archivo = RAIZ / config["flechas"]["sonido"]
            sonidos.append({"archivo": config["flechas"]["sonido"],
                            "momento": inicio + duracion(archivo) / 2 - silencio_inicial(archivo)})
    return flechas, sonidos


def config_base(version=None):
    """Valores por defecto + los de una versión de la fábrica (config/versiones/<v>.json).
    Los de cada versión están congelados en su archivo: un short hecho con la 1.0 sigue
    saliendo igual aunque los valores por defecto pasen a ser los de la 2.0.
    Sin versión, se usa la de por_defecto.json."""
    base = json.loads((RAIZ / "config" / "por_defecto.json").read_text(encoding="utf-8"))
    version = version or base["version_fabrica"]
    ruta = RAIZ / "config" / "versiones" / f"{version}.json"
    if not ruta.exists():
        raise RuntimeError(f"La versión de la fábrica '{version}' no está en config/versiones/")
    base = fusionar(base, json.loads(ruta.read_text(encoding="utf-8")))
    base["version_fabrica"] = version
    return base


def cargar_config(nombre):
    """Por defecto -> versión de la receta (o la por defecto) -> receta."""
    ruta_propia = RAIZ / "shorts" / nombre / "config.json"
    propia = json.loads(ruta_propia.read_text(encoding="utf-8")) if ruta_propia.exists() else {}
    try:
        base = config_base(propia.get("version_fabrica"))
    except RuntimeError as error:
        raise RuntimeError(f"{nombre}: {error}") from None
    return fusionar(base, propia)


def crear(nombre, rehacer=None, despues_de_voz=None, al_paso=None):
    """Crea (o actualiza) el short 'nombre' y devuelve la ruta del vídeo final.
    despues_de_voz(config, segundos) es opcional: se llama cuando la voz ya está lista
    (con la duración real del short: voz + cola) y antes del resto de pasos. El vigilante
    la usa para elegir o comprobar los clips; puede cambiar config["video"]["clips"].
    al_paso(paso, saltado=False) es opcional: se llama al empezar cada paso (el vigilante la
    usa para la ventana de progreso)."""
    avisar = al_paso or (lambda paso, saltado=False: None)
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
        "respiros": trabajo / "respiros.json",
        "subtitulos": trabajo / "subtitulos.ass",
        "fondo": trabajo / "fondo.mp4",
        "render": trabajo / "final.mp4",
    }

    # Con respiros, lo que viene después de la transcripción usa la voz con los silencios
    # y los tiempos desplazados
    guion = receta / "guion.md"
    con_respiros = config["respiros"]["activo"]
    voz_final = trabajo / "voz_respiros.wav" if con_respiros else archivos["voz"]
    palabras_final = trabajo / "palabras_respiros.json" if con_respiros else archivos["transcripcion"]
    if not con_respiros and any(m["tipo"] == "respiro" for m in leer_marcas(guion)):
        print("AVISO: el guion tiene [respiro], pero respiros.activo es false: se ignoran")

    inicio = time.perf_counter()
    rehechos = set()
    for paso in PASOS:
        if paso == "respiros" and not con_respiros:
            avisar(paso, saltado=True)
            continue
        avisar(paso)
        if paso == "transcripcion" and despues_de_voz:
            silencios = (sum(s for _, s, _ in respiros_del_guion(guion, config["respiros"]["segundos"]))
                         if con_respiros else 0)
            despues_de_voz(config, duracion(archivos["voz"]) + silencios + config["final"]["cola"])
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
        elif paso == "respiros":
            crear_respiros(archivos["voz"], archivos["transcripcion"], guion, voz_final,
                           palabras_final, archivos["respiros"], config["respiros"])
        elif paso == "subtitulos":
            generar_ass(palabras_final, archivos["subtitulos"], config["subtitulos"], guion)
        elif paso == "fondo":
            if not edl_manual.exists():
                respiros = (json.loads(archivos["respiros"].read_text(encoding="utf-8"))
                            if con_respiros else [])
                crear_edl(palabras_final, voz_final, edl, biblioteca, config, guion, respiros)
            generar_fondo(edl, biblioteca, trabajo / "cortes", archivos["fondo"], config["video"],
                          marcas_de_agua(RAIZ))
        elif paso == "render":
            # Efectos escritos a mano en la configuración, o elegidos automáticamente
            efectos = anclar_a_palabras(config["efectos"]["lista"], palabras_final)
            if not efectos and config["efectos"]["automaticos"] > 0:
                efectos = elegir_efectos(edl, palabras_final, config)
            palabras = json.loads(palabras_final.read_text(encoding="utf-8"))
            respiros = (json.loads(archivos["respiros"].read_text(encoding="utf-8"))
                        if con_respiros else [])
            # Flechas del guion ([flecha x y]): su dibujo y su sonido (si no hay, nada cambia)
            flechas, sonidos = situar_flechas(guion, palabras, edl, biblioteca, config)
            render(archivos["fondo"], voz_final, archivos["subtitulos"],
                   trabajo / "mezcla.txt", archivos["render"], RAIZ, config, efectos + sonidos,
                   palabras[-1]["fin"] if palabras else None, respiros, flechas)

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
