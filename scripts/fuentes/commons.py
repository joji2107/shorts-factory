"""Wikimedia Commons (API de MediaWiki, sin clave): fotos y vídeos con licencia libre.

Solo se aceptan dominio público y CC0: desde la fase 11 los shorts se publican sin créditos
(el autor y la licencia se quedan en biblioteca/indice.csv, en local), y CC BY obliga a citar
al autor allí donde se publica. Se rechazan también CC BY-SA (además obligaría a publicar el
short con la misma licencia), NC (no comercial), ND (sin obras derivadas: el recorte y el
movimiento lo son) y lo que no tenga una licencia clara. La licencia es de cada archivo: se
lee de extmetadata.

Lo que exigen las licencias (Commons:Reusing content outside Wikimedia y Commons:Credit line):
- CC BY: autor, nombre de la licencia, enlace a la licencia, enlace a la fuente si es posible,
  título si lo hay e indicar si se ha modificado (aquí siempre: recorte vertical y movimiento).
- Dominio público y CC0: no obligan, pero se recomienda citar.
- "Restrictions" (derechos de imagen, marcas...) no es de autor, pero se avisa.

Política de Wikimedia: el User-Agent lleva un contacto (WIKIMEDIA_CONTACTO de .env), las
peticiones van de una en una y sin picos, con maxlag=5 (si los servidores van cargados,
responden con un error en vez de servir) y con caché de 24 horas. Sin contacto, Commons
responde 429 ("demasiadas peticiones") enseguida.

La búsqueda útil es por categoría ("Category:Viaduc de Millau"): la de texto devuelve archivos
que no tienen nada que ver.
"""
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from . import ErrorFuente, con_cache

API = "https://commons.wikimedia.org/w/api.php"
POR_PAGINA = 50
ANCHO_FOTO = 3840                     # se descarga la versión escalada a este ancho, no el original
MINIATURA = 500                       # Wikimedia solo sirve anchos estándar (400 da error 400)
LADO_MIN = 1000                      # fotos con el lado corto menor se ven borrosas en 1080x1920
ACEPTADAS = re.compile(r"(pd|cc0)")
FOTOS = {"image/jpeg", "image/png", "image/tiff", "image/webp"}
METADATOS = "License|LicenseShortName|LicenseUrl|Artist|Credit|Restrictions|AttributionRequired"


def sin_html(texto):
    """'<a href="...">Ana</a>' -> 'Ana' (los campos de Commons vienen en HTML)."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", texto or ""))).strip()


def pedir(contacto, parametros):
    """Una petición a la API, identificada con el contacto y sin prisas (1 s antes de cada una
    que no esté en caché). Los errores se describen para leerlos."""
    time.sleep(1)
    url = f"{API}?{urllib.parse.urlencode({**parametros, 'format': 'json', 'maxlag': 5})}"
    agente = f"fabrica-shorts/1.0 ({contacto}) python-urllib"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": agente}),
                                    timeout=30) as respuesta:
            datos = json.load(respuesta)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise ErrorFuente("Commons pide ir más despacio (error 429): espera unos minutos") from None
        raise ErrorFuente(f"Commons ha respondido con el error {e.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ErrorFuente("No se puede conectar con Commons (sin red o no responde a tiempo)") from None
    except ValueError:
        raise ErrorFuente("Commons ha devuelto una respuesta que no es JSON") from None
    if "error" in datos:
        codigo = datos["error"].get("code", "")
        if codigo == "maxlag":
            raise ErrorFuente("Commons está muy cargado ahora mismo (maxlag): prueba en unos minutos")
        raise ErrorFuente(f"Commons ha respondido con un error: {codigo}")
    return datos


def motivo_rechazo(licencia):
    """Por qué no se acepta una licencia (None si se acepta)."""
    if ACEPTADAS.fullmatch(licencia):
        return None
    if "-sa" in licencia:
        return "son CC BY-SA"
    if "-nc" in licencia or "-nd" in licencia:
        return "son NC o ND"
    if licencia.startswith("cc-by"):
        return "piden citar al autor (CC BY) y los shorts van sin créditos"
    return "no tienen una licencia aceptada (dominio público o CC0)"


def nombre_licencia(codigo, corto):
    if codigo == "pd":
        return "Dominio público"
    if codigo == "cc0":
        return "CC0 1.0"
    return corto or codigo.upper()


def atribucion(titulo, autor, licencia, licencia_url, url):
    """El texto de crédito de la fuente, para el registro local del índice."""
    if licencia.startswith("CC BY"):
        return (f"«{titulo}», de {autor}, {licencia} ({licencia_url}), vía Wikimedia Commons "
                f"({url}). Recortada y con movimiento")
    return f"«{titulo}», de {autor} ({licencia}), vía Wikimedia Commons ({url})"


def a_formato_comun(pagina, rechazos):
    """Un archivo de la respuesta en el formato común, o None (y el motivo en rechazos)."""
    info = (pagina.get("imageinfo") or [{}])[0]
    meta = info.get("extmetadata") or {}
    codigo = (meta.get("License") or {}).get("value", "").strip().lower()
    mime = info.get("mime", "")
    if mime in FOTOS:
        tipo = "imagen"
    elif mime.startswith("video/") or mime == "application/ogg":
        tipo = "video"
    else:
        rechazos["no son foto ni vídeo"] += 1
        return None
    motivo = motivo_rechazo(codigo)
    if motivo:
        rechazos[motivo] += 1
        return None
    if tipo == "imagen" and min(info.get("width", 0), info.get("height", 0)) < LADO_MIN:
        rechazos[f"son fotos de menos de {LADO_MIN} px"] += 1
        return None

    titulo = re.sub(r"\.[a-z0-9]+$", "", pagina["title"].split(":", 1)[-1], flags=re.I)
    autor = sin_html((meta.get("Artist") or {}).get("value"))
    if not autor and sin_html((meta.get("Credit") or {}).get("value")).lower() in ("own work", "trabajo propio"):
        autor = info.get("user", "")           # "obra propia" sin autor escrito: es quien la subió
    if not autor:
        rechazos["no dicen quién es el autor"] += 1
        return None
    licencia = nombre_licencia(codigo, sin_html((meta.get("LicenseShortName") or {}).get("value")))
    licencia_url = sin_html((meta.get("LicenseUrl") or {}).get("value"))
    url = info.get("descriptionurl", "")
    if tipo == "imagen":
        # Versión escalada a ANCHO_FOTO (si la foto es más pequeña, Commons da el original)
        version = {"link": info.get("thumburl") or info.get("url"),
                   "width": info.get("thumbwidth") or info.get("width"),
                   "height": info.get("thumbheight") or info.get("height")}
        miniatura = (info.get("thumburl") or "").replace(f"/{ANCHO_FOTO}px-", f"/{MINIATURA}px-")
    else:
        version = {"link": info.get("url"), "width": info.get("width"), "height": info.get("height")}
        miniatura = (info.get("thumburl") or "").replace(f"/{ANCHO_FOTO}px-", f"/{MINIATURA}px-")
    return {"id": str(pagina.get("pageid", "")), "url": url, "autor": autor,
            "duracion": round(float(info.get("duration") or 0), 1) if tipo == "video" else 0,
            "tipo": tipo, "versiones": [version], "etiquetas": titulo.lower(), "miniatura": miniatura or None,
            "ia": False, "licencia": licencia, "licencia_url": licencia_url,
            "atribucion": atribucion(titulo, autor, licencia, licencia_url, url),
            "avisos": sin_html((meta.get("Restrictions") or {}).get("value"))}


def buscar(contacto, busqueda, pagina, id_video=None, rechazos=None):
    """Una página de archivos aceptables y si quedan más. busqueda: 'Category:...' (lo
    recomendable) o un texto. Con id_video (el id de página de Commons), solo ese archivo.
    rechazos (un Counter) recoge cuántos se han rechazado y por qué."""
    from collections import Counter
    rechazos = rechazos if rechazos is not None else Counter()
    if not contacto:
        raise ErrorFuente("Falta WIKIMEDIA_CONTACTO en .env (email o web): lo exige la política de Wikimedia")
    base = {"action": "query", "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata|user",
            "iiurlwidth": ANCHO_FOTO, "iiextmetadatafilter": METADATOS}
    if id_video:
        base["pageids"] = id_video
    elif busqueda.lower().startswith(("category:", "categoría:", "categoria:")):
        base.update({"generator": "categorymembers", "gcmtype": "file", "gcmlimit": POR_PAGINA,
                     "gcmtitle": "Category:" + busqueda.split(":", 1)[1].strip()})
    else:
        base.update({"generator": "search", "gsrnamespace": 6, "gsrlimit": POR_PAGINA,
                     "gsrsearch": f"{busqueda} filetype:bitmap|video"})

    # Las páginas siguientes necesitan el "continue" de la anterior (que está en caché)
    seguir, datos = {}, {}
    for numero in range(1, pagina + 1):
        parametros = {**base, **seguir}
        datos = con_cache("commons", parametros, lambda: pedir(contacto, parametros))
        seguir = datos.get("continue", {})
        if numero < pagina and not seguir:
            return [], False

    paginas = sorted((datos.get("query", {}).get("pages") or {}).values(), key=lambda p: p.get("title", ""))
    resultados = [r for r in (a_formato_comun(p, rechazos) for p in paginas) if r]
    return resultados, bool(seguir)
