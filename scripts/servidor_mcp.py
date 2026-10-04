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

import material
import metricas

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
        "Herramientas de la fábrica de shorts. Para crear un short: primero "
        "evaluar_material con el tema y la duración aproximada; si falta material, "
        "buscar_clips solo con los clips que falten; después preparar_short con una "
        "grabación de data/entrada/. El vigilante debe estar en marcha para que se procese. "
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
    """Cuenta cuántos vídeos utilizables hay de cada etiqueta (sin los descartados)."""
    contador = Counter()
    for fila in _filas_indice():
        if fila["tipo"].strip() == "video" and not material.descartado(fila):
            contador.update(e for e in fila["etiquetas"].strip().split(";") if e)
    return contador


def _generales_del_tema(tema, filas):
    """Las etiquetas que comparten todos los vídeos de un tema, además del tema
    (por ejemplo, 'animal' y 'mar' para 'pulpo'). Vacío si el tema es nuevo."""
    conjuntos = [fila["etiquetas"].strip().split(";") for fila in filas
                 if fila["tipo"].strip() == "video" and tema in fila["etiquetas"].strip().split(";")]
    if not conjuntos:
        return []
    return [e for e in conjuntos[0] if e and e != tema and all(e in otro for otro in conjuntos[1:])]


def _contar(n, palabra):
    """'1 clip', '3 clips'."""
    return f"{n} {palabra}" + ("" if n == 1 else "s")


def _reservadas(tema):
    """Recetas reservadas de un tema: shorts/NNN-tema/ con guion.md, sin grabación
    todavía (su config.json no tiene audio_original) y sin audio esperando en la bandeja."""
    reservadas = []
    for receta in sorted((RAIZ / "shorts").glob(f"[0-9][0-9][0-9]-{tema}")):
        ruta = receta / "config.json"
        if not (receta / "guion.md").exists() or not ruta.exists():
            continue
        if "audio_original" in json.loads(ruta.read_text(encoding="utf-8")):
            continue
        if any(BANDEJA.glob(f"{receta.name}.*")):
            continue
        reservadas.append(receta.name)
    return reservadas


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


def _buscar_pixabay(clave, busqueda, pagina, id_video=None):
    """Una página de resultados de Pixabay en el formato común, y si quedan más páginas.
    Con id_video, solo ese vídeo. "ia": Pixabay lo marca como generado con IA (el campo
    isAiGenerated no sale en su documentación) o lo dice en sus etiquetas; no es infalible."""
    por_pagina = 50
    if id_video:
        parametros = {"id": id_video}
    else:
        parametros = {"q": busqueda, "safesearch": "true", "per_page": por_pagina, "page": pagina}
    datos = _con_cache("pixabay", parametros, lambda: _pedir_pixabay(clave, parametros))
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
                       "versiones": versiones, "etiquetas": etiquetas, "miniatura": miniatura,
                       "ia": bool(video.get("isAiGenerated")) or "ai generated" in etiquetas})
    return videos, pagina * por_pagina < datos.get("totalHits", 0)


# Para añadir Pexels: escribir _buscar_pexels(clave, busqueda, pagina, id_video=None) con el mismo
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


def _palabra_clave(busqueda):
    """La primera palabra de la búsqueda: tiene que estar en las etiquetas del vídeo."""
    return busqueda.lower().split()[0]


def _reunir_candidatos(fuente, clave, busqueda, ya_registradas, saltados, cantidad, orientacion="todas", ids=()):
    """Los vídeos que se pueden descargar, en orden de preferencia: primero los que no son
    IA y, entre ellos, los verticales (los horizontales sirven por el fondo desenfocado).
    Pixabay devuelve también vídeos que solo se parecen a la búsqueda (piedras o cielos
    estrellados al buscar rayos), así que se exige la palabra clave en sus etiquetas.
    Con ids, solo esos vídeos y en ese orden (los ha elegido alguien viendo ver_candidatos)."""
    candidatos = []

    def considerar(video, mirar_etiquetas):
        url = video["url"].strip().rstrip("/")
        archivo = _elegir_archivo(video["versiones"])
        vertical = archivo is not None and archivo["height"] > archivo["width"]
        if video["duracion"] < 6:
            saltados["duran menos de 6 s"] += 1
        elif not url or url in ya_registradas:
            saltados["ya estaban en el índice"] += 1
        elif mirar_etiquetas and _palabra_clave(busqueda) not in video["etiquetas"]:
            saltados[f"no tienen '{_palabra_clave(busqueda)}' en sus etiquetas"] += 1
        elif archivo is None:
            saltados["sin archivo descargable"] += 1
        elif orientacion != "todas" and vertical != (orientacion == "vertical"):
            saltados[f"no son {orientacion}es"] += 1
        else:
            ya_registradas.add(url)                     # tampoco se repite entre páginas
            candidatos.append((video, archivo))

    if ids:
        for id_video in ids:
            videos, _ = fuente["buscar"](clave, busqueda, 1, id_video)
            if not videos:
                saltados["ids que no existen"] += 1
            for video in videos:
                considerar(video, mirar_etiquetas=False)
        return candidatos

    # Como mucho 3 páginas, que además quedan en caché 24 horas
    for pagina in range(1, 4):
        videos, hay_mas = fuente["buscar"](clave, busqueda, pagina)
        for video in videos:
            considerar(video, mirar_etiquetas=True)
        if sum(not video["ia"] for video, _ in candidatos) >= cantidad or not hay_mas:
            break
    # sort estable: dentro de cada grupo se mantiene el orden de Pixabay
    candidatos.sort(key=lambda c: (c[0]["ia"], c[1]["height"] <= c[1]["width"]))
    return candidatos


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
    y con errores, qué está publicado, qué medidas de métricas tocan (48h o 7d) y las
    últimas líneas del registro del vigilante."""
    publicados = sorted({p["short"] for p in metricas.leer_publicaciones()})
    medidas = metricas.pendientes()
    ahora = [m for m in medidas if m["estado"] == "pendiente"]
    proximas = [m for m in medidas if m["estado"] == "próxima"][:3]
    partes = [
        f"Bandeja (pendientes): {_nombres(BANDEJA) or 'vacía'}",
        f"En revisión: {_nombres(DATA / 'revision', '*.mp4') or 'ninguno'}",
        f"Listos (aprobados): {_nombres(DATA / 'listos', '*.mp4') or 'ninguno'}",
        f"Publicados: {_contar(len(publicados), 'short')} ({', '.join(publicados) or 'ninguno'})",
        "Medidas pendientes ahora: " + (", ".join(
            f"{m['short']} {m['plataforma']} {m['momento']}" for m in ahora) or "ninguna"),
        "Próximas medidas: " + (", ".join(
            f"{m['short']} {m['plataforma']} {m['momento']} ({m['cuando']:%Y-%m-%d %H:%M})"
            for m in proximas) or "ninguna"),
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
def evaluar_material(tema: str, duracion_segundos: float = 45) -> str:
    """Dice si hay clips suficientes de un tema para un short de esa duración sin repetir
    planos, cuántas veces se ha usado cada clip y, si falta material, cuántos clips más
    hacen falta. Úsala antes de preparar_short y de buscar_clips.
    duracion_segundos: lo que dura la voz, sin la cola del final (se suma aquí)."""
    tema = tema.strip().lower()
    if not 10 <= duracion_segundos <= 180:
        return "La duración tiene que estar entre 10 y 180 segundos."
    config = material.configuracion()
    video = config["video"]
    total = duracion_segundos + config["final"]["cola"]
    try:
        clips = material.clips_del_tema(tema)
        durs = material.duraciones(clips)
    except RuntimeError as e:
        return str(e)
    if not clips:
        return (f"No hay ningún clip de '{tema}'. Para un short de {duracion_segundos:.0f} s hacen falta "
                f"al menos {material.MIN_CLIPS} clips: búscalos con buscar_clips.")

    shorts, cortes = material.usos()
    lineas = [f"Tema '{tema}': {len(clips)} clips, {sum(durs.values()):.1f} s en total "
              f"({sum(durs.values()) / total:.2f} veces un short de {total:.0f} s, contando "
              f"{config['final']['cola']:g} s de cola)."]
    lineas.append("Clips, de menos a más usados:")
    for clip in sorted(clips, key=lambda c: (shorts[c], cortes[c], c)):
        lineas.append(f"  {clip}: {durs[clip]:.1f} s, usado en {_contar(shorts[clip], 'short')} "
                      f"({_contar(cortes[clip], 'corte')})")

    escenarios = material.escenarios(total, video)
    resultado = material.alcanza(durs, total, video)
    lineas.append("¿Llega sin repetir planos? " + "; ".join(
        f"{nombre} de {escenarios[nombre][0]:.1f} s: {'sí' if ok else 'no'}" for nombre, ok in resultado.items()))

    estado = material.estado(durs, total, video)
    if estado == "suficiente":
        lineas.append("Estado: SUFICIENTE. No hace falta descargar nada; el vigilante elegirá los "
                      "clips menos usados.")
    else:
        motivo = (f"hay menos de {material.MIN_CLIPS} clips distintos" if all(resultado.values())
                  else "con cortes muy cortos se repetirían planos" if estado == "justo"
                  else "se repetirían planos")
        lineas.append(f"Estado: {estado.upper()} ({motivo}).")
        faltan, tipica = material.clips_que_faltan(durs, total, video)
        if faltan:
            llamadas = -(-faltan // MAX_CLIPS)
            lineas.append(f"{'Falta' if faltan == 1 else 'Faltan'} {_contar(faltan, 'clip')} de unos {tipica:.0f} s. "
                          f"Con buscar_clips, cantidad "
                          f"{min(faltan, MAX_CLIPS)}" + (f", en {llamadas} llamadas" if llamadas > 1 else "") + ".")
    return "\n".join(lineas)


@servidor.tool()
def listar_shorts() -> list[dict]:
    """Los shorts que tienen receta en shorts/, en qué estado está su vídeo, dónde y
    cuándo se ha publicado (de shorts/publicaciones.csv) y qué medidas de métricas le
    faltan: 'pendiente' si ya toca, 'próxima' con la fecha si todavía no."""
    publicaciones = metricas.leer_publicaciones()
    medidas = metricas.pendientes()
    resultado = []
    for receta in sorted(p for p in (RAIZ / "shorts").iterdir() if p.is_dir()):
        nombre = receta.name
        publicado = {p["plataforma"]: p["publicado"] for p in publicaciones if p["short"] == nombre}
        if publicado:
            estado = "publicado"
        elif any((DATA / "listos").glob(f"{nombre}*.mp4")):
            estado = "listo para publicar"
        elif (DATA / "revision" / f"{nombre}.mp4").exists():
            estado = "pendiente de revisión"
        elif (DATA / "errores" / f"{nombre}.log").exists():
            estado = "con error"
        else:
            estado = "sin vídeo (reservado o pendiente de procesar)"
        ficha = {"short": nombre, "estado": estado}
        if publicado:
            ficha["publicado"] = publicado
            ficha["medidas_pendientes"] = [
                f"{m['plataforma']} {m['momento']}: " + (
                    "ya toca" if m["estado"] == "pendiente" else f"el {m['cuando']:%Y-%m-%d %H:%M}")
                for m in medidas if m["short"] == nombre
            ]
        resultado.append(ficha)
    return resultado


@servidor.tool()
def preparar_short(grabacion: str, tema: str, short: str = "") -> str:
    """Pone una grabación de data/entrada/ en la bandeja como el siguiente short del tema
    (por ejemplo, 'voz_prueba.wav' con el tema 'pulpo' crea '002-pulpo.wav').
    Si hay una receta reservada de ese tema (creada por la skill guion-short, con su
    guion, música y efectos), usa su nombre. Si hubiera varias, indica cuál en 'short'
    (por ejemplo '003-caballo').
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

    reservadas = _reservadas(tema)
    if short:
        if Path(short).name not in reservadas:
            return f"'{short}' no es una receta reservada de '{tema}'. Reservadas: {reservadas or 'ninguna'}"
        nombre = Path(short).name
    elif len(reservadas) > 1:
        return f"Hay varias recetas reservadas de '{tema}': {reservadas}. Indica cuál en 'short'."
    elif reservadas:
        nombre = reservadas[0]
    else:
        nombre = f"{_siguiente_numero():03d}-{tema}"
    BANDEJA.mkdir(parents=True, exist_ok=True)
    shutil.copy2(archivo, BANDEJA / f"{nombre}{archivo.suffix.lower()}")
    origen = " (receta reservada, con su guion, música y efectos)" if nombre in reservadas else ""
    return (f"Grabación copiada a la bandeja como {nombre}{archivo.suffix.lower()}{origen} "
            f"({temas[tema]} clips disponibles de '{tema}'). Cuando el vigilante termine, "
            f"el vídeo estará en data/revision/{nombre}.mp4.")


@servidor.tool()
def ver_candidatos(busqueda_en_ingles: str, cantidad: int = 8, orientacion: str = "todas") -> str:
    """Enseña los vídeos de Pixabay que buscar_clips descargaría, SIN descargarlos a la
    biblioteca: id, orientación, duración, si Pixabay lo marca como IA, sus etiquetas y su
    miniatura (guardada en data/cache/miniaturas/ para verla). Sirve para elegir los que
    de verdad muestran el tema y pasar sus ids a buscar_clips. La primera palabra de la
    búsqueda tiene que estar en las etiquetas del vídeo. orientacion: 'todas', 'vertical'
    u 'horizontal' (lo grabado de verdad suele ser horizontal; queda bien por el fondo
    desenfocado). Como mucho 12 candidatos."""
    busqueda = busqueda_en_ingles.strip()
    if not busqueda:
        return "Falta la búsqueda en inglés (por ejemplo, 'lightning')."
    if orientacion not in ("todas", "vertical", "horizontal"):
        return "orientacion tiene que ser 'todas', 'vertical' u 'horizontal'."
    cantidad = max(1, min(cantidad, 12))
    fuente = FUENTES[FUENTE]
    clave = _clave(fuente["variable"])
    if not clave:
        return f"Falta la clave de {fuente['nombre']} en .env ({fuente['variable']}=...)."

    ya_registradas = {fila["url"].strip().rstrip("/") for fila in _filas_indice()}
    saltados = Counter()
    try:
        candidatos = _reunir_candidatos(fuente, clave, busqueda, ya_registradas, saltados, cantidad, orientacion)
    except ErrorFuente as e:
        return f"No se ha podido buscar: {e}"

    carpeta = CACHE / "miniaturas"
    carpeta.mkdir(parents=True, exist_ok=True)
    lineas = []
    for video, archivo in candidatos[:cantidad]:
        miniatura = carpeta / f"{FUENTE}_{video['id']}.jpg"
        if video["miniatura"] and not miniatura.exists():
            try:                                     # la miniatura no lleva la clave en la url
                peticion = urllib.request.Request(video["miniatura"], headers={"User-Agent": AGENTE})
                with urllib.request.urlopen(peticion, timeout=20) as respuesta:
                    miniatura.write_bytes(respuesta.read())
            except (urllib.error.URLError, TimeoutError, OSError):
                pass
        forma = "vertical" if archivo["height"] > archivo["width"] else "horizontal"
        lineas.append(f"{video['id']}: {forma} {archivo['width']}x{archivo['height']}, {video['duracion']} s"
                      f"{', IA' if video['ia'] else ''}, de {video['autor']} | {video['etiquetas']}"
                      + (f" | {miniatura.relative_to(RAIZ)}" if miniatura.exists() else ""))
    partes = [f"Candidatos de '{busqueda}' ({len(lineas)}, primero los que no son IA):"] + (lineas or ["(ninguno)"])
    if saltados:
        partes.append("Descartados: " + ", ".join(f"{n} {motivo}" for motivo, n in saltados.items()))
    partes.append("Para descargar los elegidos: buscar_clips(tema, ids='id1,id2'). "
                  "La marca de IA de Pixabay no es infalible: mira las miniaturas.")
    return "\n".join(partes)


@servidor.tool()
def buscar_clips(tema: str, busqueda_en_ingles: str = "", cantidad: int = 4, etiquetas_generales: str = "",
                 ids: str = "") -> str:
    """Descarga vídeos de Pixabay a la biblioteca como <tema>_NN.mp4 y los registra en
    biblioteca/indice.csv con su licencia. Máximo 5 clips.
    Lo mejor es mirar antes ver_candidatos y pasar aquí los ids elegidos ('123,456'): así
    se descarga solo lo que se ha visto que sirve. Sin ids, busca (en inglés: tema 'caballo',
    búsqueda 'horse'; la primera palabra tiene que estar en las etiquetas del vídeo) y se
    queda con los primeros de 6 s o más, primero los que no son IA y después los verticales.
    Antes, usa evaluar_material para saber cuántos clips faltan y pide solo esos.
    etiquetas_generales: una o dos categorías más amplias que el tema, en singular, sin
    tildes y separadas por punto y coma (caballo -> 'animal'; pulpo -> 'animal;mar').
    Si el tema ya existe y no se indican, se usan las que ya tiene. Los vídeos que Pixabay
    marca como IA se registran además con la etiqueta 'ia'.
    No vuelve a descargar vídeos que ya estén en el índice."""
    tema = tema.strip().lower()
    busqueda = busqueda_en_ingles.strip()
    lista_ids = [i.strip() for i in ids.split(",") if i.strip()]
    if not re.fullmatch(r"[a-z0-9_]+", tema):
        return "El tema solo puede tener minúsculas sin tildes, números y guiones bajos."
    if any(not i.isdigit() for i in lista_ids):
        return "Los ids son los números de ver_candidatos, separados por comas ('123,456')."
    if lista_ids:
        cantidad = len(lista_ids)
    elif not busqueda:
        return "Falta la búsqueda en inglés (por ejemplo, 'horse' para el tema 'caballo') o los ids."
    if not 1 <= cantidad <= MAX_CLIPS:
        return f"La cantidad tiene que estar entre 1 y {MAX_CLIPS} (no se permiten descargas masivas)."

    filas = _filas_indice()
    generales = [e.strip().lower() for e in etiquetas_generales.split(";") if e.strip()]
    if not generales:
        generales = _generales_del_tema(tema, filas)
        if not generales:
            return (f"'{tema}' es un tema nuevo: indica en etiquetas_generales una o dos categorías "
                    f"más amplias, en singular y sin tildes (por ejemplo 'animal' o 'animal;mar').")
    if any(not re.fullmatch(r"[a-z0-9_]+", e) for e in generales):
        return "Las etiquetas generales solo pueden tener minúsculas sin tildes, números y guiones bajos."
    generales = [e for e in dict.fromkeys(generales) if e != tema]
    if not 1 <= len(generales) <= 2:
        return "Indica una o dos etiquetas generales distintas del tema (por ejemplo 'animal')."
    etiquetas = ";".join([tema] + generales)                       # el tema siempre primero

    fuente = FUENTES[FUENTE]
    clave = _clave(fuente["variable"])
    if not clave:
        return (f"Falta la clave de {fuente['nombre']}: pega tu clave en el archivo .env "
                f"({fuente['variable']}=...) y vuelve a registrar el servidor MCP con --env-file.")

    ya_registradas = {fila["url"].strip().rstrip("/") for fila in filas}
    saltados = Counter()
    problema = None

    # 1. Reunir candidatos, en orden de preferencia
    candidatos = []
    try:
        candidatos = _reunir_candidatos(fuente, clave, busqueda, ya_registradas, saltados, cantidad, ids=lista_ids)
    except ErrorFuente as e:
        problema = str(e)

    # 3. Descargar y registrar uno a uno: lo que ya se ha bajado queda registrado aunque luego falle algo
    VIDEOS.mkdir(parents=True, exist_ok=True)
    numero = _siguiente_clip(tema, filas)
    anadidos = []
    try:
        for video, archivo in candidatos[:cantidad]:
            destino = VIDEOS / f"{tema}_{numero:02d}.mp4"
            _descargar(archivo["link"], destino)
            _anadir_al_indice([destino.name, "video", fuente["nombre"], video["autor"], video["url"],
                               fuente["licencia"], date.today().isoformat(),
                               etiquetas + (";ia" if video["ia"] else "")])
            forma = "vertical" if archivo["height"] > archivo["width"] else "horizontal"
            anadidos.append(f"{destino.name}: {archivo['width']}x{archivo['height']} {forma}, "
                            f"{video['duracion']} s{', IA' if video['ia'] else ''}, de {video['autor']} ({video['url']})")
            numero += 1
    except ErrorFuente as e:
        problema = str(e)

    partes = []
    if anadidos:
        partes.append(f"Clips añadidos ({len(anadidos)} de {cantidad}):\n" + "\n".join(anadidos))
    else:
        partes.append(f"No se ha añadido ningún clip de '{busqueda or ids}'.")
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
