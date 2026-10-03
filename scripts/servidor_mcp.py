"""Servidor MCP de la fábrica de shorts.

Da a Claude herramientas concretas y seguras sobre el proyecto. No fabrica los
shorts directamente: deja la grabación en la bandeja y el vigilante hace el
trabajo, igual que si la hubiera dejado yo.

Importante: el servidor habla con Claude por la salida estándar (stdout), así
que aquí nunca se usa print(): cualquier texto suelto rompería la comunicación.
"""
import csv
import hashlib
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

from mcp.server.mcpserver import MCPServer

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
ENTRADA = DATA / "entrada"
BANDEJA = DATA / "bandeja"
VIDEOS = DATA / "biblioteca" / "video"
INDICE = RAIZ / "biblioteca" / "indice.csv"
EXTENSIONES = {".wav", ".mp3", ".m4a", ".aif", ".aiff"}

CACHE = DATA / "cache"
CADUCIDAD_CACHE = 24 * 60 * 60        # Pixabay exige guardar las búsquedas 24 horas
MAX_CLIPS = 5                         # y no permite descargas masivas
CLAVE_DE_EJEMPLO = "pega_aqui_tu_clave"
# Algunos servidores rechazan el User-Agent que urllib pone por defecto
AGENTE = "fabrica-shorts/1.0 (proyecto personal)"
API_PIXABAY = "https://pixabay.com/api/videos/"

servidor = MCPServer(
    "fabrica-shorts",
    version="1.0",
    instructions=(
        "Herramientas de la fábrica de shorts. Para crear un short, usa "
        "preparar_short con una grabación de data/entrada/ y un tema que exista "
        "en temas_disponibles (si el tema no tiene clips, búscalos antes con buscar_clips); "
        "el vigilante debe estar en marcha para que se procese. "
        "Revisar y aprobar los vídeos (pasar de revision/ a listos/) lo decide el usuario."
    ),
)


def _filas_indice():
    """Lee biblioteca/indice.csv y comprueba que cada línea tenga todas las columnas."""
    with INDICE.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        filas = list(lector)
    for numero, fila in enumerate(filas, start=2):
        if None in fila or None in fila.values():
            raise ValueError(f"La línea {numero} de biblioteca/indice.csv tiene columnas de menos o de más")
    return filas


def _temas():
    """Cuenta cuántos vídeos hay de cada etiqueta."""
    contador = Counter()
    for fila in _filas_indice():
        if fila["tipo"].strip() == "video":
            contador.update(e for e in fila["etiquetas"].strip().split(";") if e)
    return contador


def _siguiente_numero():
    """El siguiente número libre para un short (los 9xx están reservados para pruebas)."""
    lugares = [RAIZ / "shorts", DATA / "archivo", BANDEJA, DATA / "revision", DATA / "listos"]
    usados = set()
    for lugar in lugares:
        if lugar.exists():
            for elemento in lugar.iterdir():
                encontrado = re.match(r"(\d{3})-", elemento.name)
                if encontrado and int(encontrado.group(1)) < 900:
                    usados.add(int(encontrado.group(1)))
    return max(usados, default=0) + 1


def _nombres(carpeta, patron="*"):
    return sorted(p.name for p in carpeta.glob(patron)) if carpeta.exists() else []


# --- Búsqueda de clips -------------------------------------------------------
# Cada fuente tiene su función de búsqueda, que devuelve los vídeos en un formato
# común: {"url": página del vídeo, "autor", "duracion", "versiones": [{"link", "width", "height"}]}.
# El resto (elegir versión, descargar, numerar y registrar) es igual para todas.

class ErrorFuente(Exception):
    """Un fallo al hablar con la fuente de clips, con un mensaje pensado para leerlo.
    Nunca lleva la URL de la petición, porque en Pixabay la clave va dentro."""


def _clave(variable):
    """La clave de la API, o None si no está puesta (o sigue la de ejemplo del .env)."""
    clave = os.environ.get(variable, "").strip()
    return clave if clave and clave != CLAVE_DE_EJEMPLO else None


def _con_cache(fuente, parametros, pedir):
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


def _pedir_pixabay(clave, parametros):
    """Hace la petición a la API de Pixabay. La clave viaja en la URL, así que los errores
    se describen solo por su código y se lanzan fuera del except: así la excepción original
    (que guarda la URL) no queda enganchada al error que llega a Claude."""
    url = f"{API_PIXABAY}?{urllib.parse.urlencode({'key': clave, **parametros})}"
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


def _buscar_pixabay(clave, busqueda, pagina):
    """Una página de resultados de Pixabay en el formato común, y si quedan más páginas."""
    por_pagina = 50
    parametros = {"q": busqueda, "safesearch": "true", "per_page": por_pagina, "page": pagina}
    datos = _con_cache("pixabay", parametros, lambda: _pedir_pixabay(clave, parametros))
    videos = []
    for video in datos.get("hits", []):
        versiones = [{"link": v.get("url"), "width": v.get("width"), "height": v.get("height")}
                     for v in (video.get("videos") or {}).values()]
        videos.append({"url": video.get("pageURL") or "", "autor": video.get("user") or "desconocido",
                       "duracion": video.get("duration") or 0, "versiones": versiones})
    return videos, pagina * por_pagina < datos.get("totalHits", 0)


# Para añadir Pexels: escribir _buscar_pexels(clave, busqueda, pagina) con el mismo
# formato de salida, añadirla aquí y cambiar FUENTE.
FUENTES = {
    "pixabay": {"buscar": _buscar_pixabay, "variable": "PIXABAY_API_KEY", "nombre": "Pixabay",
                "licencia": "Pixabay Content License", "web": "https://pixabay.com"},
}
FUENTE = "pixabay"


def _elegir_archivo(versiones):
    """La versión más pequeña cuyo lado corto sea de 1080 px o más (así 1080 gana a 4K);
    si no hay ninguna, la mayor. Se ignoran las versiones vacías o sin medidas."""
    candidatos = [v for v in versiones if v.get("link") and v.get("width") and v.get("height")]
    suficientes = [v for v in candidatos if min(v["width"], v["height"]) >= 1080]
    if suficientes:
        return min(suficientes, key=lambda v: v["width"] * v["height"])
    if candidatos:
        return max(candidatos, key=lambda v: v["width"] * v["height"])
    return None


def _siguiente_clip(tema, filas):
    """El siguiente número libre de <tema>_NN.mp4, mirando la carpeta y el índice."""
    patron = re.compile(rf"{re.escape(tema)}_(\d+)\.mp4")
    nombres = _nombres(VIDEOS, f"{tema}_*.mp4") + [fila["archivo"].strip() for fila in filas]
    numeros = [int(m.group(1)) for m in map(patron.fullmatch, nombres) if m]
    return max(numeros, default=0) + 1


def _descargar(url, destino):
    """Descarga a un .part y lo renombra al terminar: nunca queda un .mp4 a medias
    ni se sobrescribe un archivo de la biblioteca."""
    if destino.exists():
        raise ErrorFuente(f"{destino.name} ya existe en la biblioteca y no se sobrescribe")
    parcial = destino.with_name(destino.name + ".part")
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})   # aquí no va la clave
    try:
        with urllib.request.urlopen(peticion, timeout=60) as respuesta, parcial.open("wb") as f:
            shutil.copyfileobj(respuesta, f, 1024 * 1024)
        parcial.rename(destino)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        parcial.unlink(missing_ok=True)
        raise ErrorFuente(f"Falló la descarga de {destino.name}: {e}")


def _anadir_al_indice(fila):
    """Añade una línea a biblioteca/indice.csv (csv pone comillas solo si hacen falta)."""
    with INDICE.open("rb") as f:                       # por si la última línea no acaba en salto
        f.seek(-1, os.SEEK_END)
        falta_salto = f.read(1) != b"\n"
    with INDICE.open("a", encoding="utf-8", newline="") as f:
        if falta_salto:
            f.write("\n")
        csv.writer(f, lineterminator="\n").writerow(fila)


@servidor.tool()
def estado_fabrica(lineas_registro: int = 15) -> str:
    """Resumen de la fábrica: qué hay en la bandeja, en revisión, listo para publicar
    y con errores, y las últimas líneas del registro del vigilante."""
    partes = [
        f"Bandeja (pendientes): {_nombres(BANDEJA) or 'vacía'}",
        f"En revisión: {_nombres(DATA / 'revision', '*.mp4') or 'ninguno'}",
        f"Listos para publicar: {_nombres(DATA / 'listos', '*.mp4') or 'ninguno'}",
        f"Con errores: {_nombres(DATA / 'errores', '*.log') or 'ninguno'}",
        f"Grabaciones disponibles en data/entrada: {_nombres(ENTRADA) or 'ninguna'}",
    ]
    registro = DATA / "registro.log"
    if registro.exists():
        ultimas = registro.read_text(encoding="utf-8").splitlines()[-lineas_registro:]
        partes.append("Últimas líneas del registro:\n" + "\n".join(ultimas))
    return "\n".join(partes)


@servidor.tool()
def temas_disponibles() -> dict[str, int]:
    """Etiquetas de vídeo de la biblioteca y cuántos clips tiene cada una.
    Un short solo se puede hacer sobre un tema que aparezca aquí."""
    return dict(sorted(_temas().items()))


@servidor.tool()
def listar_shorts() -> list[dict]:
    """Los shorts que tienen receta en shorts/ y en qué estado está su vídeo."""
    resultado = []
    for receta in sorted(p for p in (RAIZ / "shorts").iterdir() if p.is_dir()):
        nombre = receta.name
        if (DATA / "listos" / f"{nombre}.mp4").exists():
            estado = "listo para publicar"
        elif (DATA / "revision" / f"{nombre}.mp4").exists():
            estado = "pendiente de revisión"
        elif (DATA / "errores" / f"{nombre}.log").exists():
            estado = "con error"
        else:
            estado = "sin vídeo (publicado o pendiente de procesar)"
        resultado.append({"short": nombre, "estado": estado})
    return resultado


@servidor.tool()
def preparar_short(grabacion: str, tema: str) -> str:
    """Pone una grabación de data/entrada/ en la bandeja como el siguiente short del tema
    (por ejemplo, 'voz_prueba.wav' con el tema 'pulpo' crea '002-pulpo.wav').
    Si el vigilante está en marcha, el vídeo estará en data/revision/ en unos 5 minutos."""
    archivo = ENTRADA / Path(grabacion).name          # solo el nombre: nunca rutas fuera de entrada/
    if not archivo.is_file():
        return f"No existe la grabación '{archivo.name}' en data/entrada/. Disponibles: {_nombres(ENTRADA)}"
    if archivo.suffix.lower() not in EXTENSIONES:
        return f"'{archivo.name}' no es un audio admitido ({', '.join(sorted(EXTENSIONES))})."

    tema = tema.strip().lower()
    if not re.fullmatch(r"[a-z0-9_]+", tema):
        return "El tema solo puede tener minúsculas sin tildes, números y guiones bajos."
    temas = _temas()
    if tema not in temas:
        return f"No hay vídeos con la etiqueta '{tema}'. Temas disponibles: {sorted(temas)}"

    nombre = f"{_siguiente_numero():03d}-{tema}"
    BANDEJA.mkdir(parents=True, exist_ok=True)
    shutil.copy2(archivo, BANDEJA / f"{nombre}{archivo.suffix.lower()}")
    return (f"Grabación copiada a la bandeja como {nombre}{archivo.suffix.lower()} "
            f"({temas[tema]} clips disponibles de '{tema}'). Cuando el vigilante termine, "
            f"el vídeo estará en data/revision/{nombre}.mp4.")


@servidor.tool()
def buscar_clips(tema: str, busqueda_en_ingles: str, cantidad: int = 4, otras_etiquetas: str = "") -> str:
    """Busca vídeos de 6 segundos o más en Pixabay (primero los verticales), los descarga
    a la biblioteca como <tema>_NN.mp4 y los registra en biblioteca/indice.csv con su licencia.
    La búsqueda va en inglés (por ejemplo, tema 'caballo' y búsqueda 'horse'). Máximo 5 clips.
    otras_etiquetas es opcional, separadas por punto y coma (por ejemplo 'animal;campo').
    No vuelve a descargar vídeos que ya estén en el índice."""
    tema = tema.strip().lower()
    busqueda = busqueda_en_ingles.strip()
    if not re.fullmatch(r"[a-z0-9_]+", tema):
        return "El tema solo puede tener minúsculas sin tildes, números y guiones bajos."
    if not busqueda:
        return "Falta la búsqueda en inglés (por ejemplo, 'horse' para el tema 'caballo')."
    if not 1 <= cantidad <= MAX_CLIPS:
        return f"La cantidad tiene que estar entre 1 y {MAX_CLIPS} (no se permiten descargas masivas)."
    extra = [e.strip().lower() for e in otras_etiquetas.split(";") if e.strip()]
    if any(not re.fullmatch(r"[a-z0-9_]+", e) for e in extra):
        return "Las otras etiquetas solo pueden tener minúsculas sin tildes, números y guiones bajos."
    etiquetas = ";".join(dict.fromkeys([tema] + extra))           # el tema primero y sin repetir

    fuente = FUENTES[FUENTE]
    clave = _clave(fuente["variable"])
    if not clave:
        return (f"Falta la clave de {fuente['nombre']}: pega tu clave en el archivo .env "
                f"({fuente['variable']}=...) y vuelve a registrar el servidor MCP con --env-file.")

    filas = _filas_indice()
    ya_registradas = {fila["url"].strip().rstrip("/") for fila in filas}
    saltados = Counter()
    problema = None

    # 1. Reunir candidatos (como mucho 3 páginas, que además quedan en caché 24 horas)
    candidatos = []
    try:
        for pagina in range(1, 4):
            videos, hay_mas = fuente["buscar"](clave, busqueda, pagina)
            for video in videos:
                url = video["url"].strip().rstrip("/")
                if video["duracion"] < 6:
                    saltados["duran menos de 6 s"] += 1
                elif not url or url in ya_registradas:
                    saltados["ya estaban en el índice"] += 1
                elif (archivo := _elegir_archivo(video["versiones"])) is None:
                    saltados["sin archivo descargable"] += 1
                else:
                    ya_registradas.add(url)                     # tampoco se repite entre páginas
                    candidatos.append((video, archivo))
            verticales = sum(a["height"] > a["width"] for _, a in candidatos)
            if verticales >= cantidad or not hay_mas:
                break
    except ErrorFuente as e:
        problema = str(e)

    # 2. Primero los verticales; los horizontales sirven gracias al fondo desenfocado
    candidatos.sort(key=lambda c: c[1]["height"] <= c[1]["width"])   # sort estable: no cambia el orden de Pixabay

    # 3. Descargar y registrar uno a uno: lo que ya se ha bajado queda registrado aunque luego falle algo
    VIDEOS.mkdir(parents=True, exist_ok=True)
    numero = _siguiente_clip(tema, filas)
    anadidos = []
    try:
        for video, archivo in candidatos[:cantidad]:
            destino = VIDEOS / f"{tema}_{numero:02d}.mp4"
            _descargar(archivo["link"], destino)
            _anadir_al_indice([destino.name, "video", fuente["nombre"], video["autor"], video["url"],
                               fuente["licencia"], date.today().isoformat(), etiquetas])
            forma = "vertical" if archivo["height"] > archivo["width"] else "horizontal"
            anadidos.append(f"{destino.name}: {archivo['width']}x{archivo['height']} {forma}, "
                            f"{video['duracion']} s, de {video['autor']} ({video['url']})")
            numero += 1
    except ErrorFuente as e:
        problema = str(e)

    partes = []
    if anadidos:
        partes.append(f"Clips añadidos ({len(anadidos)} de {cantidad}):\n" + "\n".join(anadidos))
    else:
        partes.append(f"No se ha añadido ningún clip de '{busqueda}'.")
    if saltados:
        partes.append("Vídeos saltados: " + ", ".join(f"{n} {motivo}" for motivo, n in saltados.items()))
    if problema:
        partes.append(f"Se ha parado por un error: {problema}"
                      + (" (lo descargado antes del error ya está en el índice)." if anadidos else ""))
    partes.append(f"Ahora '{tema}' tiene {_temas()[tema]} clips en total.")
    partes.append(f"Vídeos de {fuente['nombre']} ({fuente['web']}): conviene citar a los autores en la descripción.")
    return "\n".join(partes)


@servidor.tool()
def ver_error(nombre: str) -> str:
    """El detalle del error de un short que ha fallado (su archivo .log en data/errores/)."""
    log = DATA / "errores" / f"{Path(nombre).stem}.log"
    if not log.exists():
        return f"No hay ningún error registrado para '{nombre}'. Con errores: {_nombres(DATA / 'errores', '*.log')}"
    return log.read_text(encoding="utf-8")[-3000:]


if __name__ == "__main__":
    servidor.run(transport="stdio")
