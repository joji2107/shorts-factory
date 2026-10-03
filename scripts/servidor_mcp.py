"""Servidor MCP de la fábrica de shorts.

Da a Claude herramientas concretas y seguras sobre el proyecto. No fabrica los
shorts directamente: deja la grabación en la bandeja y el vigilante hace el
trabajo, igual que si la hubiera dejado yo.

Importante: el servidor habla con Claude por la salida estándar (stdout), así
que aquí nunca se usa print(): cualquier texto suelto rompería la comunicación.
"""
import csv
import re
import shutil
from collections import Counter
from pathlib import Path

from mcp.server.mcpserver import MCPServer

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
ENTRADA = DATA / "entrada"
BANDEJA = DATA / "bandeja"
EXTENSIONES = {".wav", ".mp3", ".m4a", ".aif", ".aiff"}

servidor = MCPServer(
    "fabrica-shorts",
    version="1.0",
    instructions=(
        "Herramientas de la fábrica de shorts. Para crear un short, usa "
        "preparar_short con una grabación de data/entrada/ y un tema que exista "
        "en temas_disponibles; el vigilante debe estar en marcha para que se procese. "
        "Revisar y aprobar los vídeos (pasar de revision/ a listos/) lo decide el usuario."
    ),
)


def _filas_indice():
    """Lee biblioteca/indice.csv y comprueba que cada línea tenga todas las columnas."""
    with (RAIZ / "biblioteca" / "indice.csv").open(encoding="utf-8-sig", newline="") as f:
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
def ver_error(nombre: str) -> str:
    """El detalle del error de un short que ha fallado (su archivo .log en data/errores/)."""
    log = DATA / "errores" / f"{Path(nombre).stem}.log"
    if not log.exists():
        return f"No hay ningún error registrado para '{nombre}'. Con errores: {_nombres(DATA / 'errores', '*.log')}"
    return log.read_text(encoding="utf-8")[-3000:]


if __name__ == "__main__":
    servidor.run(transport="stdio")
