"""Pixabay (API de vídeos). Condiciones: las búsquedas se guardan 24 horas, no se permiten
descargas masivas y hay que indicar que los vídeos son de Pixabay. La clave viaja dentro de
la URL: nunca se muestra ni se registra una URL completa de la API."""
import json
import urllib.error
import urllib.parse
import urllib.request

from . import AGENTE, ErrorFuente, con_cache

API = "https://pixabay.com/api/videos/"


def pedir(clave, parametros):
    """Hace la petición a la API de Pixabay. La clave viaja en la URL, así que los errores
    se describen solo por su código y se lanzan fuera del except: así la excepción original
    (que guarda la URL) no queda enganchada al error que llega a Claude."""
    url = f"{API}?{urllib.parse.urlencode({'key': clave, **parametros})}"
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    try:
        with urllib.request.urlopen(peticion, timeout=20) as respuesta:
            return json.load(respuesta)
    except urllib.error.HTTPError as e:
        if e.code == 400:
            problema = "Pixabay rechaza la petición (error 400): lo normal es que PIXABAY_API_KEY no sea válida"
        elif e.code == 429:
            problema = "Se ha alcanzado el límite de Pixabay (100 peticiones por minuto): prueba en un rato"
        else:
            problema = f"Pixabay ha respondido con el error {e.code}"
    except (urllib.error.URLError, TimeoutError, OSError):
        problema = "No se puede conectar con Pixabay (sin red o no responde a tiempo)"
    except ValueError:
        problema = "Pixabay ha devuelto una respuesta que no es JSON"
    raise ErrorFuente(problema)


def buscar(clave, busqueda, pagina, id_video=None, rechazos=None):
    """Una página de resultados de Pixabay en el formato común, y si quedan más páginas.
    Con id_video, solo ese vídeo. "ia": Pixabay lo marca como generado con IA (el campo
    isAiGenerated no sale en su documentación) o lo dice en sus etiquetas; no es infalible."""
    por_pagina = 50
    if id_video:
        parametros = {"id": id_video}
    else:
        parametros = {"q": busqueda, "safesearch": "true", "per_page": por_pagina, "page": pagina}
    datos = con_cache("pixabay", parametros, lambda: pedir(clave, parametros))
    videos = []
    for video in datos.get("hits", []):
        tamanos = video.get("videos") or {}
        versiones = [{"link": v.get("url"), "width": v.get("width"), "height": v.get("height")}
                     for v in tamanos.values()]
        etiquetas = (video.get("tags") or "").lower()
        miniatura = next((tamanos[t].get("thumbnail") for t in ("small", "tiny", "medium")
                          if tamanos.get(t, {}).get("thumbnail")), None)
        videos.append({"id": str(video.get("id") or ""), "url": video.get("pageURL") or "",
                       "autor": video.get("user") or "desconocido", "duracion": video.get("duration") or 0,
                       "tipo": "video", "versiones": versiones, "etiquetas": etiquetas, "miniatura": miniatura,
                       "ia": bool(video.get("isAiGenerated")) or "ai generated" in etiquetas,
                       "licencia": None, "licencia_url": None, "atribucion": "", "avisos": ""})
    return videos, pagina * por_pagina < datos.get("totalHits", 0)
