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

from crear_short import RAIZ, fusionar
from pasos.cortes import repartir
from pasos.utilidades import duracion

INDICE = RAIZ / "biblioteca" / "indice.csv"
VIDEOS = RAIZ / "data" / "biblioteca" / "video"
MIN_CLIPS = 6


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


def clips_del_tema(tema, filas=None):
    """Los vídeos del índice con esa etiqueta (nombre sin extensión)."""
    return [
        Path(fila["archivo"]).stem
        for fila in (filas if filas is not None else leer_indice())
        if fila["tipo"].strip() == "video" and tema in fila["etiquetas"].strip().split(";")
    ]


def configuracion(plantilla="curiosidades"):
    """La configuración que tendrá un short nuevo: por defecto + plantilla."""
    base = json.loads((RAIZ / "config" / "por_defecto.json").read_text(encoding="utf-8"))
    ruta = RAIZ / "config" / "plantillas" / f"{plantilla}.json"
    return fusionar(base, json.loads(ruta.read_text(encoding="utf-8")))


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


def duraciones(clips):
    """La duración de cada clip. Se comprueba antes que exista: si ffprobe fallara,
    ejecutar() imprimiría su error y eso rompería el servidor MCP."""
    faltan = [clip for clip in clips if not (VIDEOS / f"{clip}.mp4").is_file()]
    if faltan:
        raise RuntimeError(f"Están en el índice pero no en data/biblioteca/video: {', '.join(faltan)}")
    return {clip: duracion(VIDEOS / f"{clip}.mp4") for clip in clips}


def escenarios(total, video):
    """Tres maneras de cortar el short: todo con cortes mínimos, medios o máximos."""
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


def elegir_clips(tema, total, config, azar=random):
    """Los clips justos para el short, empezando por los menos usados (al azar entre
    los empatados). Devuelve (clips, estado). Si ni con todos es suficiente, usa todos."""
    candidatos = clips_del_tema(tema)
    if not candidatos:
        return [], "insuficiente"
    shorts, cortes = usos()
    candidatos.sort(key=lambda clip: (shorts[clip], cortes[clip], azar.random()))
    durs = duraciones(candidatos)
    for cuantos in range(min(MIN_CLIPS, len(candidatos)), len(candidatos) + 1):
        elegidos = candidatos[:cuantos]
        resultado = estado({c: durs[c] for c in elegidos}, total, config["video"])
        if resultado == "suficiente":
            return elegidos, resultado
    return candidatos, resultado
