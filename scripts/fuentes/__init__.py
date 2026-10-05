"""Fuentes de clips del servidor MCP: cada una en su módulo, con el mismo formato de salida.

Cada fuente tiene una función buscar(clave, busqueda, pagina, id_video=None) que devuelve
(resultados, hay_mas). Cada resultado es un diccionario común:
    {"id", "url" (página del archivo), "autor", "duracion" (0 en las fotos), "tipo" ("video"
     o "imagen"), "versiones": [{"link", "width", "height"}], "etiquetas", "miniatura", "ia",
     "licencia", "licencia_url", "atribucion", "avisos"}
licencia, licencia_url y atribucion pueden ser None: entonces se usan las de la fuente
(Pixabay tiene una sola licencia para todo y no pide atribución).
El resto (elegir versión, descargar, numerar y registrar) lo hace el servidor, igual para todas.

Aquí tampoco se usa print(): lo importa el servidor MCP, que habla por la salida estándar.
"""
import hashlib
import json
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
CACHE = RAIZ / "data" / "cache"
CADUCIDAD_CACHE = 24 * 60 * 60        # Pixabay exige guardar las búsquedas 24 horas
# Algunos servidores rechazan el User-Agent que urllib pone por defecto
AGENTE = "fabrica-shorts/1.0 (proyecto personal)"


class ErrorFuente(Exception):
    """Un fallo al hablar con la fuente de clips, con un mensaje pensado para leerlo.
    Nunca lleva la URL de la petición, porque en Pixabay la clave va dentro."""


def con_cache(fuente, parametros, pedir):
    """Devuelve la respuesta guardada si tiene menos de 24 horas; si no, la pide y la guarda.
    El nombre del archivo es una huella de los parámetros, que no incluyen la clave."""
    huella = hashlib.sha256(json.dumps(parametros, sort_keys=True).encode()).hexdigest()[:16]
    archivo = CACHE / fuente / f"{huella}.json"
    if archivo.exists() and time.time() - archivo.stat().st_mtime < CADUCIDAD_CACHE:
        try:
            return json.loads(archivo.read_text(encoding="utf-8"))
        except ValueError:
            pass                                       # caché estropeada: se vuelve a pedir
    datos = pedir()
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps(datos), encoding="utf-8")
    return datos


from . import commons, pixabay          # noqa: E402  (usan lo de arriba)

# "variable": la variable de .env que se pasa a buscar() como clave (en Commons, el contacto
# que exige su política de User-Agent). "palabra_clave": exigir la primera palabra de la
# búsqueda en las etiquetas (Pixabay devuelve vídeos que solo se parecen; en Commons se
# busca por categoría, que ya es precisa).
FUENTES = {
    "pixabay": {"buscar": pixabay.buscar, "variable": "PIXABAY_API_KEY", "nombre": "Pixabay",
                "licencia": "Pixabay Content License",
                "licencia_url": "https://pixabay.com/service/license-summary/",
                "web": "https://pixabay.com", "palabra_clave": True},
    "commons": {"buscar": commons.buscar, "variable": "WIKIMEDIA_CONTACTO", "nombre": "Wikimedia Commons",
                "licencia": "", "licencia_url": "", "web": "https://commons.wikimedia.org",
                "palabra_clave": False},
}
