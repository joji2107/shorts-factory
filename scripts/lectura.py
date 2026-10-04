"""Velocidad de lectura: cuántas palabras por segundo digo al grabar.

Sirve para estimar la duración de un guion antes de grabarlo (la skill guion-short
la usa para evaluar_material). Se guarda en config/lectura.json y se afina sola:
el vigilante añade una muestra por cada short terminado (palabras transcritas y
segundos de la primera a la última palabra, pausas incluidas; lo grabado después no cuenta) y la velocidad pasa a ser la mediana de las
últimas muestras. La mediana evita que una grabación rara desvíe la estimación.
"""
import json
import statistics

from crear_short import RAIZ

ARCHIVO = RAIZ / "config" / "lectura.json"


def leer():
    return json.loads(ARCHIVO.read_text(encoding="utf-8"))


def estimar(palabras):
    """Duración estimada de un short con ese número de palabras (voz + cola por defecto)."""
    por_defecto = json.loads((RAIZ / "config" / "por_defecto.json").read_text(encoding="utf-8"))
    return palabras / leer()["palabras_por_segundo"] + por_defecto["final"]["cola"]


def anadir_muestra(short, palabras, segundos):
    """Añade (o sustituye, si se rehízo el short) la muestra y recalcula la velocidad.
    Devuelve la velocidad de esta grabación y la nueva velocidad de referencia."""
    datos = leer()
    muestras = [m for m in datos["muestras"] if m["short"] != short]
    muestras.append({"short": short, "palabras": palabras, "segundos": round(segundos, 2)})
    ultimas = muestras[-datos["ultimas_muestras"]:]
    datos["muestras"] = muestras
    datos["palabras_por_segundo"] = round(statistics.median(m["palabras"] / m["segundos"] for m in ultimas), 2)
    # Una muestra por línea: así el diff de Git enseña solo la nueva
    lineas = ",\n    ".join(json.dumps(m, ensure_ascii=False) for m in muestras)
    ARCHIVO.write_text(
        "{\n"
        f'  "palabras_por_segundo": {datos["palabras_por_segundo"]},\n'
        f'  "ultimas_muestras": {datos["ultimas_muestras"]},\n'
        f'  "muestras": [\n    {lineas}\n  ]\n'
        "}\n",
        encoding="utf-8",
    )
    return palabras / segundos, datos["palabras_por_segundo"]
