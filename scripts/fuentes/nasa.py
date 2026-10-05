"""NASA Image and Video Library (images-api.nasa.gov, sin clave): vídeos y fotos de la NASA.

Pautas de uso (nasa.gov/nasa-brand-center/images-and-media): el material de la NASA en general
no tiene copyright en EE. UU.; hay que reconocer a la NASA como fuente (se recomienda, no se
exige); no se puede insinuar que la NASA respalda nada ni usar su logotipo como marca; las
personas reconocibles necesitan permiso para uso comercial; y el material de terceros que hay
en la biblioteca va marcado con su titular y NO queda libre. Por eso se rechaza lo que diga ©,
copyright o courtesy, o lo firme una empresa o agencia que no es la NASA (SpaceX, ESA...).

Solo sirve para temas de la NASA (cohetes, plataformas de lanzamiento, el VAB, el
crawler-transporter, telescopios...): al buscar "hoover dam" devolvió un motor del transbordador.

Los originales pueden ser enormes (un vídeo 4K de 9 minutos pesaba 6,3 GB): se descarga la
versión ~large (o ~medium) de los vídeos y ~orig de las fotos si no pasa de 50 MB (si no,
~large). Las medidas y la duración salen de metadata.json, sin descargar nada. Cada página
pide 12 resultados porque cada uno necesita dos consultas más (versiones y medidas); todo va
a la caché de 24 horas.
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from . import AGENTE, ErrorFuente, con_cache

API = "https://images-api.nasa.gov"
POR_PAGINA = 12
MAX_FOTO = 50 * 1024 * 1024
LICENCIA = "NASA Media Usage Guidelines (sin copyright en EE. UU.)"
LICENCIA_URL = "https://www.nasa.gov/nasa-brand-center/images-and-media/"
TERCEROS = re.compile(r"©|copyright|courtesy|spacex|boeing|blue origin|roscosmos|\besa\b|jaxa|getty|reuters|"
                      r"associated press|\bap photo", re.I)


def pedir(url):
    """GET a la API o a los archivos de la NASA (JSON)."""
    time.sleep(0.2)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENTE}),
                                    timeout=30) as respuesta:
            return json.load(respuesta)
    except urllib.error.HTTPError as e:
        raise ErrorFuente(f"La NASA ha respondido con el error {e.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ErrorFuente("No se puede conectar con la NASA (sin red o no responde a tiempo)") from None
    except ValueError:
        raise ErrorFuente("La NASA ha devuelto una respuesta que no es JSON") from None


def tamano(url):
    """Bytes de un archivo (petición HEAD), o None si no se sabe."""
    try:
        peticion = urllib.request.Request(url, method="HEAD", headers={"User-Agent": AGENTE})
        with urllib.request.urlopen(peticion, timeout=20) as respuesta:
            return int(respuesta.headers.get("Content-Length") or 0) or None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None


def segundos(texto):
    """'0:09:28' -> 568; '12.5 s' -> 12.5; '' -> 0."""
    texto = str(texto or "").strip()
    if re.fullmatch(r"[\d:]+", texto):
        valor = 0.0
        for parte in texto.split(":"):
            valor = valor * 60 + float(parte)
        return valor
    encontrado = re.match(r"([\d.]+)\s*s", texto)
    return float(encontrado.group(1)) if encontrado else 0.0


def a_formato_comun(item, rechazos):
    """Un resultado de la búsqueda en el formato común, o None (y el motivo en rechazos)."""
    datos = (item.get("data") or [{}])[0]
    nasa_id, tipo = datos.get("nasa_id", ""), datos.get("media_type")
    if tipo not in ("video", "image"):
        rechazos["no son foto ni vídeo"] += 1
        return None
    firmas = " ".join(str(datos.get(c) or "") for c in ("photographer", "secondary_creator", "description", "title"))
    if TERCEROS.search(firmas):
        rechazos["son de terceros (©, courtesy o de otra empresa o agencia)"] += 1
        return None

    clave = urllib.parse.quote(nasa_id)
    # Algunas rutas llevan espacios ("SLS Roll Out Beauty Shot"): se codifican (%20)
    versiones = [urllib.parse.quote(i["href"].replace("http://", "https://"), safe=":/~%")
                 for i in con_cache("nasa", {"asset": nasa_id},
                                    lambda: pedir(f"{API}/asset/{clave}")).get("collection", {}).get("items", [])]
    metadatos = next((v for v in versiones if v.endswith("metadata.json")), None)
    meta = con_cache("nasa", {"metadata": nasa_id}, lambda: pedir(metadatos)) if metadatos else {}
    ancho = int(meta.get("QuickTime:ImageWidth") or meta.get("File:ImageWidth") or meta.get("EXIF:ImageWidth") or 0)
    alto = int(meta.get("QuickTime:ImageHeight") or meta.get("File:ImageHeight") or meta.get("EXIF:ImageHeight") or 0)
    if not ancho or not alto:
        rechazos["no dicen sus medidas"] += 1
        return None

    if tipo == "video":
        enlace = next((v for nombre in ("~large.mp4", "~medium.mp4", "~orig.mp4")
                       for v in versiones if v.endswith(nombre)), None)
        escala = min(1.0, 1920 / max(ancho, alto)) if enlace and "~orig" not in enlace else 1.0
    else:
        original = next((v for v in versiones if re.search(r"~orig\.jpe?g$", v, re.I)), None)
        grande = next((v for v in versiones if re.search(r"~large\.jpe?g$", v, re.I)), None)
        enlace = original if original and (tamano(original) or 0) <= MAX_FOTO else grande
        escala = 1.0 if enlace == original else min(1.0, 1920 / max(ancho, alto))
    if not enlace:
        rechazos["sin archivo descargable"] += 1
        return None

    fotografo = re.sub(r"^NASA\s*(or National Aeronautics and Space Administration)?/?", "",
                       str(datos.get("photographer") or "")).strip()
    autor = f"NASA/{datos.get('center') or 'NASA'}" + (f"/{fotografo}" if fotografo else "")
    url = f"https://images.nasa.gov/details/{clave}"
    miniatura = next((urllib.parse.quote(l["href"], safe=":/~%") for l in item.get("links") or []
                      if l.get("rel") == "preview" and l.get("href")), None)
    return {"id": nasa_id, "url": url, "autor": autor,
            "duracion": round(segundos(meta.get("QuickTime:Duration")), 1) if tipo == "video" else 0,
            "tipo": "video" if tipo == "video" else "imagen",
            "versiones": [{"link": enlace, "width": round(ancho * escala), "height": round(alto * escala)}],
            "etiquetas": " ".join([datos.get("title", "")] + list(datos.get("keywords") or [])).lower(),
            "miniatura": miniatura, "ia": False, "licencia": LICENCIA, "licencia_url": LICENCIA_URL,
            "atribucion": f"«{datos.get('title', nasa_id)}», {autor} ({url}). La NASA no respalda este vídeo",
            "avisos": "reconocer a la NASA como fuente; no insinuar respaldo; personas reconocibles: cuidado"}


def buscar(clave, busqueda, pagina, id_video=None, rechazos=None):
    """Una página de resultados (vídeos y fotos) y si quedan más. Con id_video (el nasa_id),
    solo ese. clave no se usa: la API de la NASA no pide clave."""
    from collections import Counter
    rechazos = rechazos if rechazos is not None else Counter()
    if id_video:
        parametros = {"nasa_id": id_video}
    else:
        parametros = {"q": busqueda, "media_type": "video,image", "page": pagina, "page_size": POR_PAGINA}
    datos = con_cache("nasa", parametros, lambda: pedir(f"{API}/search?{urllib.parse.urlencode(parametros)}"))
    coleccion = datos.get("collection", {})
    resultados = [r for r in (a_formato_comun(item, rechazos) for item in coleccion.get("items", [])) if r]
    total = coleccion.get("metadata", {}).get("total_hits", 0)
    return resultados, pagina * POR_PAGINA < total
