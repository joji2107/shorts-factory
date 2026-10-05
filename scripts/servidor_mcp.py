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
import subprocess
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
from fuentes import AGENTE, FUENTES, ErrorFuente

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
ENTRADA = DATA / "entrada"
BANDEJA = DATA / "bandeja"
VIDEOS = DATA / "biblioteca" / "video"
INDICE = RAIZ / "biblioteca" / "indice.csv"
EXTENSIONES = {".wav", ".mp3", ".m4a", ".aif", ".aiff"}

IMAGENES = DATA / "biblioteca" / "imagen"
CACHE = DATA / "cache"
MAX_CLIPS = 5                         # Pixabay no permite descargas masivas (y Commons pide calma)
CLAVE_DE_EJEMPLO = "pega_aqui_tu_clave"

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
    """Cuenta cuántos clips (vídeos y fotos) auténticos hay de cada etiqueta (sin los
    descartados ni los genéricos)."""
    contador = Counter()
    for fila in _filas_indice():
        if fila["tipo"].strip() in material.TIPOS_CLIP and not material.descartado(fila) \
                and not material.generico(fila):
            contador.update(e for e in fila["etiquetas"].strip().split(";") if e)
    return contador


def _generales_del_tema(tema, filas):
    """Las etiquetas que comparten todos los vídeos de un tema, además del tema
    (por ejemplo, 'animal' y 'mar' para 'pulpo'). Vacío si el tema es nuevo."""
    conjuntos = [fila["etiquetas"].strip().split(";") for fila in filas
                 if fila["tipo"].strip() in material.TIPOS_CLIP and tema in fila["etiquetas"].strip().split(";")]
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
# Cada fuente está en su módulo de scripts/fuentes/ (pixabay, commons) y devuelve los
# resultados en un formato común. El resto (elegir versión, descargar, numerar y registrar)
# es igual para todas y está aquí.

def _clave(variable):
    """La clave (o el contacto) de .env, o None si no está puesta (o sigue la de ejemplo)."""
    clave = os.environ.get(variable, "").strip()
    return clave if clave and clave != CLAVE_DE_EJEMPLO else None


def _fuente(nombre):
    """La fuente pedida, o un mensaje de error si no existe."""
    if nombre not in FUENTES:
        return None, f"Fuente desconocida: '{nombre}'. Hay: {', '.join(FUENTES)}."
    return FUENTES[nombre], None


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
    """Lo que se puede descargar, en orden de preferencia: primero lo que no es IA y, entre
    ello, vídeo vertical, vídeo horizontal, foto vertical y foto horizontal.
    Pixabay devuelve también vídeos que solo se parecen a la búsqueda (piedras o cielos
    estrellados al buscar rayos), así que se exige la palabra clave en sus etiquetas.
    Con ids, solo esos vídeos y en ese orden (los ha elegido alguien viendo ver_candidatos)."""
    candidatos = []

    def considerar(video, mirar_etiquetas):
        url = video["url"].strip().rstrip("/")
        archivo = _elegir_archivo(video["versiones"])
        vertical = archivo is not None and archivo["height"] > archivo["width"]
        if video["tipo"] == "video" and video["duracion"] < 6:
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
            videos, _ = fuente["buscar"](clave, busqueda, 1, id_video, rechazos=saltados)
            if not videos:
                saltados["ids que no existen"] += 1
            for video in videos:
                considerar(video, mirar_etiquetas=False)
        return candidatos

    # Como mucho 3 páginas, que además quedan en caché 24 horas
    for pagina in range(1, 4):
        videos, hay_mas = fuente["buscar"](clave, busqueda, pagina, rechazos=saltados)
        for video in videos:
            considerar(video, mirar_etiquetas=fuente["palabra_clave"])
        if sum(not video["ia"] for video, _ in candidatos) >= cantidad or not hay_mas:
            break
    # Orden de preferencia: lo que no es IA primero y, dentro, vídeo vertical, vídeo horizontal,
    # foto vertical, foto horizontal (sort estable: en cada grupo, el orden de la fuente)
    candidatos.sort(key=lambda c: (c[0]["ia"], (2 if c[0]["tipo"] == "imagen" else 0)
                                   + (0 if c[1]["height"] > c[1]["width"] else 1)))
    return candidatos


def _siguiente_clip(tema, filas):
    """El siguiente número libre de <tema>_NN (.mp4 o .jpg), mirando las carpetas y el índice."""
    patron = re.compile(rf"{re.escape(tema)}_(\d+)\.(mp4|jpg)")
    nombres = (_nombres(VIDEOS, f"{tema}_*.mp4") + _nombres(IMAGENES, f"{tema}_*.jpg")
               + [fila["archivo"].strip() for fila in filas])
    numeros = [int(m.group(1)) for m in map(patron.fullmatch, nombres) if m]
    return max(numeros, default=0) + 1


def _agente(nombre_fuente, clave):
    """User-Agent para hablar con la fuente: Wikimedia exige un contacto (en Pixabay la clave
    no se pone nunca aquí)."""
    if nombre_fuente == "commons":
        return f"fabrica-shorts/1.0 ({clave}) python-urllib"
    return AGENTE


def _descargar(url, destino, agente=AGENTE):
    """Descarga a un .part y lo renombra al terminar: nunca queda un archivo a medias ni se
    sobrescribe uno de la biblioteca. Si lo descargado no es ya del formato del destino (una
    foto PNG o TIFF, un vídeo webm de Commons), se convierte con FFmpeg a .jpg o .mp4."""
    if destino.exists():
        raise ErrorFuente(f"{destino.name} ya existe en la biblioteca y no se sobrescribe")
    parcial = destino.with_name(destino.name + ".part")
    peticion = urllib.request.Request(url, headers={"User-Agent": agente})   # aquí no va la clave
    try:
        with urllib.request.urlopen(peticion, timeout=120) as respuesta, parcial.open("wb") as f:
            shutil.copyfileobj(respuesta, f, 1024 * 1024)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        parcial.unlink(missing_ok=True)
        raise ErrorFuente(f"Falló la descarga de {destino.name}: {e}")
    extension = urllib.parse.urlparse(url).path.lower().rsplit(".", 1)[-1]
    mismo_formato = extension in (("jpg", "jpeg") if destino.suffix == ".jpg" else ("mp4",))
    if mismo_formato:
        parcial.rename(destino)
        return
    # Conversión (sin print: el resultado de FFmpeg se captura)
    opciones = (["-q:v", "2"] if destino.suffix == ".jpg" else
                ["-an", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
                 "-movflags", "+faststart"])
    convertido = destino.with_name(destino.stem + ".convirtiendo" + destino.suffix)
    resultado = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", parcial,
                                *opciones, convertido], capture_output=True, text=True)
    parcial.unlink(missing_ok=True)
    if resultado.returncode != 0:
        convertido.unlink(missing_ok=True)
        raise ErrorFuente(f"No se ha podido convertir {destino.name} a {destino.suffix}")
    convertido.rename(destino)


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
def evaluar_material(tema: str, duracion_segundos: float = 45, version: str = "") -> str:
    """Dice si hay clips suficientes de un tema para un short de esa duración sin repetir
    planos, cuántas veces se ha usado cada clip y, si falta material, cuántos clips más
    hacen falta. Úsala antes de preparar_short y de buscar_clips.
    duracion_segundos: lo que dura la voz, sin la cola del final (se suma aquí).
    version: la de la fábrica del short ('2.0'); vacío, la por defecto. En la 2.0 el
    relleno se corta más rápido (hacen falta más clips): pasa como duración la voz + los
    respiros − los planos protagonistas, que no son relleno."""
    tema = tema.strip().lower()
    if not 5 <= duracion_segundos <= 180:
        return "La duración tiene que estar entre 5 y 180 segundos."
    try:
        config = material.configuracion(version=version.strip() or None)
    except RuntimeError as e:
        return str(e)
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
    """Los shorts que tienen receta en shorts/, con qué versión de la fábrica se hacen
    (version_fabrica de la receta, o la por defecto si no la dice), en qué estado está su vídeo, dónde y
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
        try:
            version = metricas.cargar_config(nombre)["version_fabrica"]
        except RuntimeError as error:
            version = f"error: {error}"
        ficha = {"short": nombre, "version_fabrica": version, "estado": estado}
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
def ver_candidatos(busqueda_en_ingles: str, cantidad: int = 8, orientacion: str = "todas",
                   fuente: str = "pixabay") -> str:
    """Enseña lo que buscar_clips descargaría, SIN descargarlo a la biblioteca: id, tipo
    (vídeo o foto), orientación, duración, licencia, si es IA, autor y miniatura (guardada en
    data/cache/miniaturas/ para verla). Sirve para elegir lo que de verdad muestra el tema (el
    objeto concreto) y pasar sus ids a buscar_clips. orientacion: 'todas', 'vertical' u
    'horizontal'. Como mucho 12 candidatos.
    fuente: 'pixabay' (vídeos; la primera palabra de la búsqueda, en inglés, tiene que estar
    en sus etiquetas) o 'commons' (Wikimedia Commons, fotos y vídeos; mejor por categoría:
    'Category:Viaduc de Millau'; solo dominio público, CC0 y CC BY: rechaza BY-SA, NC y ND)."""
    busqueda = busqueda_en_ingles.strip()
    if not busqueda:
        return "Falta la búsqueda en inglés (por ejemplo, 'lightning')."
    if orientacion not in ("todas", "vertical", "horizontal"):
        return "orientacion tiene que ser 'todas', 'vertical' u 'horizontal'."
    cantidad = max(1, min(cantidad, 12))
    nombre_fuente = fuente
    fuente, error = _fuente(nombre_fuente)
    if error:
        return error
    clave = _clave(fuente["variable"])
    if not clave:
        return f"Falta {fuente['variable']} en .env para usar {fuente['nombre']}."

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
        miniatura = carpeta / f"{nombre_fuente}_{video['id']}.jpg"
        if video["miniatura"] and not miniatura.exists():
            try:                                     # la miniatura no lleva la clave en la url
                peticion = urllib.request.Request(video["miniatura"],
                                                  headers={"User-Agent": _agente(nombre_fuente, clave)})
                with urllib.request.urlopen(peticion, timeout=20) as respuesta:
                    miniatura.write_bytes(respuesta.read())
            except (urllib.error.URLError, TimeoutError, OSError):
                pass
        forma = "vertical" if archivo["height"] > archivo["width"] else "horizontal"
        tipo = "foto" if video["tipo"] == "imagen" else f"vídeo de {video['duracion']} s"
        lineas.append(f"{video['id']}: {tipo} {forma} {archivo['width']}x{archivo['height']}"
                      f"{', IA' if video['ia'] else ''}, {video['licencia'] or fuente['licencia']}, "
                      f"de {video['autor']} | {video['etiquetas'][:80]}"
                      + (f" | AVISO: {video['avisos']}" if video["avisos"] else "")
                      + (f" | {miniatura.relative_to(RAIZ)}" if miniatura.exists() else ""))
    partes = [f"Candidatos de '{busqueda}' en {fuente['nombre']} ({len(lineas)}, primero los que no son IA):"]
    partes += lineas or ["(ninguno)"]
    if saltados:
        partes.append("Descartados: " + ", ".join(f"{n} {motivo}" for motivo, n in saltados.items()))
    partes.append(f"Para descargar los elegidos: buscar_clips(tema, ids='id1,id2', fuente='{nombre_fuente}'). "
                  "Mira las miniaturas: que sea el objeto concreto y no IA.")
    return "\n".join(partes)


@servidor.tool()
def buscar_clips(tema: str, busqueda_en_ingles: str = "", cantidad: int = 4, etiquetas_generales: str = "",
                 ids: str = "", fuente: str = "pixabay") -> str:
    """Descarga clips a la biblioteca y los registra en biblioteca/indice.csv con su licencia
    exacta, la url de la licencia y el texto de atribución que pide: vídeos como
    data/biblioteca/video/<tema>_NN.mp4 y fotos como data/biblioteca/imagen/<tema>_NN.jpg
    (en el montaje se mueven con efecto Ken Burns). Máximo 5 clips.
    fuente: 'pixabay' (vídeos) o 'commons' (Wikimedia Commons: fotos y vídeos con dominio
    público, CC0 o CC BY; mejor buscar por categoría y pasar ids de ver_candidatos).
    Lo mejor es mirar antes ver_candidatos y pasar aquí los ids elegidos ('123,456'): así
    se descarga solo lo que se ha visto que sirve. Sin ids, busca (en inglés: tema 'caballo',
    búsqueda 'horse'; la primera palabra tiene que estar en las etiquetas del vídeo) y se
    queda con los primeros de 6 s o más, primero los que no son IA y, entre ellos, por este orden:
    vídeo vertical, vídeo horizontal, foto vertical, foto horizontal.
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
    if any(not re.fullmatch(r"[A-Za-z0-9_.\-]+", i) for i in lista_ids):
        return "Los ids son los de ver_candidatos, separados por comas ('123,456')."
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

    nombre_fuente = fuente
    fuente, error = _fuente(nombre_fuente)
    if error:
        return error
    clave = _clave(fuente["variable"])
    if not clave:
        return (f"Falta {fuente['variable']} en el archivo .env para usar {fuente['nombre']}; "
                f"después hay que volver a conectar el servidor MCP (/mcp) para que la lea.")

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
    IMAGENES.mkdir(parents=True, exist_ok=True)
    numero = _siguiente_clip(tema, filas)
    anadidos = []
    try:
        for video, archivo in candidatos[:cantidad]:
            es_foto = video["tipo"] == "imagen"
            destino = (IMAGENES / f"{tema}_{numero:02d}.jpg") if es_foto else (VIDEOS / f"{tema}_{numero:02d}.mp4")
            _descargar(archivo["link"], destino, _agente(nombre_fuente, clave))
            licencia = video["licencia"] or fuente["licencia"]
            _anadir_al_indice([destino.name, video["tipo"], fuente["nombre"], video["autor"], video["url"],
                               licencia, video["licencia_url"] or fuente["licencia_url"], video["atribucion"],
                               date.today().isoformat(), etiquetas + (";ia" if video["ia"] else "")])
            forma = "vertical" if archivo["height"] > archivo["width"] else "horizontal"
            tipo = "foto" if es_foto else f"vídeo de {video['duracion']} s"
            anadidos.append(f"{destino.name}: {tipo}, {archivo['width']}x{archivo['height']} {forma}, "
                            f"{licencia}{', IA' if video['ia'] else ''}, de {video['autor']} ({video['url']})")
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
    partes.append(f"Material de {fuente['nombre']} ({fuente['web']}): los créditos (creditos.py) citan a cada "
                  "autor con el texto de atribución del índice.")
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
