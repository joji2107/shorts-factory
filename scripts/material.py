"""Material de la biblioteca: qué clips hay de un tema, cuánto duran, cuántas veces
se han usado y si alcanzan para un short sin repetir planos.

Lo usan el vigilante (para elegir los clips de cada short) y el servidor MCP (para
evaluar_material). Como lo importa el servidor, aquí tampoco se usa print().

Criterio de "material suficiente":
- Al menos MIN_CLIPS clips distintos, para que haya variedad.
- Que el reparto real de cortes.py (repartir) llegue sin repetir planos con cortes
  de corte_min, de la media y de corte_max. No basta una proporción fija (como 1,6
  veces la duración del short): cada corte gasta 0,5 s de margen y del final de cada
  clip se pierde lo que no llega a un corte entero, así que con clips cortos (6-10 s)
  hacen falta unas 2 veces la duración del short.
"""
import csv
import json
import random
import statistics
from collections import Counter
from pathlib import Path

from crear_short import RAIZ, config_base, fusionar
from pasos.clips import duracion_clip
from pasos.cortes import repartir

INDICE = RAIZ / "biblioteca" / "indice.csv"
VIDEOS = RAIZ / "data" / "biblioteca" / "video"
IMAGENES = RAIZ / "data" / "biblioteca" / "imagen"
MIN_CLIPS = 6
DESCARTADO = "descartado"


def leer_indice():
    """Las líneas de biblioteca/indice.csv, comprobando que tengan todas las columnas."""
    with INDICE.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        filas = list(lector)
    for numero, fila in enumerate(filas, start=2):
        if None in fila or None in fila.values():
            raise RuntimeError(
                f"La línea {numero} de biblioteca/indice.csv no tiene "
                f"{len(lector.fieldnames)} columnas ({', '.join(lector.fieldnames)})"
            )
    return filas


def descartado(fila):
    """Un clip con la etiqueta 'descartado' no se elige nunca (no muestra el tema, por
    ejemplo). Sigue en el índice: la biblioteca no se borra y así no se vuelve a descargar."""
    return DESCARTADO in fila["etiquetas"].strip().split(";")


def clips_del_tema(tema, filas=None):
    """Los vídeos del índice con esa etiqueta (nombre sin extensión), sin los descartados."""
    return [
        Path(fila["archivo"]).stem
        for fila in (filas if filas is not None else leer_indice())
        if fila["tipo"].strip() == "video" and tema in fila["etiquetas"].strip().split(";")
        and not descartado(fila)
    ]


def clips_ia(filas=None):
    """Los vídeos del índice con la etiqueta 'ia' (generados con inteligencia artificial)."""
    return {
        Path(fila["archivo"]).stem
        for fila in (filas if filas is not None else leer_indice())
        if "ia" in fila["etiquetas"].strip().split(";")
    }


def configuracion(plantilla="curiosidades", version=None):
    """La configuración que tendrá un short nuevo: por defecto + versión + plantilla."""
    ruta = RAIZ / "config" / "plantillas" / f"{plantilla}.json"
    return fusionar(config_base(version), json.loads(ruta.read_text(encoding="utf-8")))


def usos():
    """Cuántas veces se ha usado cada clip: en cuántos shorts y en cuántos cortes.
    Mira los cortes.txt de las recetas y los cortes_auto.txt de data/shorts/; si un
    short tiene los dos, cuenta el manual, que es el que manda."""
    listas = {p.parent.name: p for p in (RAIZ / "data" / "shorts").glob("*/cortes_auto.txt")}
    listas.update({p.parent.name: p for p in (RAIZ / "shorts").glob("*/cortes.txt")})
    shorts, cortes = Counter(), Counter()
    for lista in listas.values():
        en_este = [linea.split()[0] for linea in lista.read_text(encoding="utf-8").splitlines() if linea.split()]
        cortes.update(en_este)
        shorts.update(set(en_este))
    return shorts, cortes


def duraciones(clips, segundos_imagen=None):
    """La duración de cada clip (de una foto, la de su vídeo virtual: video.imagen.segundos).
    Se comprueba antes que exista: si ffprobe fallara, ejecutar() imprimiría su error y eso
    rompería el servidor MCP."""
    faltan = [clip for clip in clips if not ((VIDEOS / f"{clip}.mp4").is_file()
                                             or (IMAGENES / f"{clip}.jpg").is_file())]
    if faltan:
        raise RuntimeError(f"Están en el índice pero no en data/biblioteca/video ni imagen: {', '.join(faltan)}")
    if segundos_imagen is None:
        segundos_imagen = config_base()["video"]["imagen"]["segundos"]
    return {clip: duracion_clip(VIDEOS, clip, segundos_imagen) for clip in clips}


def escenarios(total, video):
    """Tres maneras de cortar el short: todo con cortes mínimos, medios o máximos.
    Con ritmo (fábrica 2.0), lo que se reparte es el relleno, con sus cortes rápidos;
    'total' es entonces lo que no cubren los planos protagonistas."""
    ritmo = video.get("ritmo", {})
    if ritmo.get("activo"):
        minimo, maximo = ritmo["relleno_min"], ritmo["relleno_max"]
    else:
        minimo, maximo = video["corte_min"], video["corte_max"]
    numeros = {
        "cortes cortos": int(total // minimo),                       # cada corte >= corte_min
        "cortes medios": max(1, round(total / ((minimo + maximo) / 2))),
        "cortes largos": -int(-total // maximo),                     # cada corte <= corte_max
    }
    return {nombre: [total / n] * n for nombre, n in numeros.items()}


def alcanza(durs, total, video):
    """Para cada escenario, si los clips llegan sin repetir planos."""
    return {nombre: not repartir(largos, list(durs), durs)[1]
            for nombre, largos in escenarios(total, video).items()}


def estado(durs, total, video):
    """'suficiente', 'justo' (solo falla con cortes muy cortos) o 'insuficiente'."""
    resultado = alcanza(durs, total, video)
    if all(resultado.values()) and len(durs) >= MIN_CLIPS:
        return "suficiente"
    if resultado["cortes medios"] and resultado["cortes largos"]:
        return "justo"
    return "insuficiente"


def clips_que_faltan(durs, total, video):
    """Cuántos clips más (de la duración mediana del tema) harían falta para que sea suficiente."""
    tipica = statistics.median(durs.values()) if durs else 10.0
    prueba = dict(durs)
    for extra in range(1, 31):
        prueba[f"nuevo_{extra}"] = tipica
        if estado(prueba, total, video) == "suficiente":
            return extra, tipica
    return None, tipica


def elegir_clips(tema, total, config, azar=random, protagonistas=()):
    """Los clips justos para el short: primero los que no son IA (un short hecho solo
    con clips de IA queda pobre) y, entre ellos, los menos usados (al azar entre los
    empatados). Devuelve (clips, estado). Si ni con todos es suficiente, usa todos.
    Los protagonistas (fábrica 2.0) no son relleno: no se eligen aquí."""
    filas = leer_indice()
    candidatos = [clip for clip in clips_del_tema(tema, filas) if clip not in protagonistas]
    if not candidatos:
        return [], "insuficiente"
    shorts, cortes = usos()
    ia = clips_ia(filas)
    candidatos.sort(key=lambda clip: (clip in ia, shorts[clip], cortes[clip], azar.random()))
    durs = duraciones(candidatos)
    for cuantos in range(min(MIN_CLIPS, len(candidatos)), len(candidatos) + 1):
        elegidos = candidatos[:cuantos]
        resultado = estado({c: durs[c] for c in elegidos}, total, config["video"])
        if resultado == "suficiente":
            return elegidos, resultado
    return candidatos, resultado
