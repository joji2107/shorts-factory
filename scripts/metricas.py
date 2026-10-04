"""Publicaciones y métricas de los shorts.

- shorts/publicaciones.csv: una línea por short y plataforma, con la fecha y hora de
  publicación y la versión exacta del vídeo (archivo de data/listos/ y su md5).
- shorts/metricas.csv: una línea por short, plataforma y momento de medida (48h o 7d),
  con las cifras y algunos datos de la ficha (técnica, tema, música, duración) para
  poder compararlos después.

Una celda vacía significa "no lo sé"; un 0 significa "ninguno".

Lo usan registrar_metricas.py, analizar_metricas.py y el servidor MCP (para listar_shorts
y estado_fabrica). Como lo importa el servidor, aquí no se usa print().
"""
import csv
import hashlib
import re
from datetime import datetime, timedelta
from pathlib import Path

from crear_short import RAIZ, cargar_config
from pasos.utilidades import duracion

CARPETA = RAIZ / "shorts"
LISTOS = RAIZ / "data" / "listos"
FORMATO = "%Y-%m-%d %H:%M"
PLATAFORMAS = ["youtube", "instagram", "tiktok", "x"]
MOMENTOS = {"48h": 48, "7d": 168}         # horas desde la publicación
TOLERANCIA = 12                           # horas de retraso antes de avisar de una medida tardía

COLUMNAS_PUBLICACIONES = ["short", "plataforma", "publicado", "archivo", "md5", "notas"]
ENTEROS = ["visualizaciones", "likes", "comentarios", "compartidos", "seguidores"]
NUMEROS = ["visualizaciones", "se_quedaron_pct", "duracion_media_s",
           "likes", "comentarios", "compartidos", "seguidores"]
FICHA = ["tecnica", "tema", "musica", "duracion_s"]
COLUMNAS_METRICAS = ["short", "plataforma", "momento", "medido"] + NUMEROS + FICHA + ["notas"]


def leer(nombre, carpeta=CARPETA):
    """Las líneas de publicaciones.csv o metricas.csv (lista vacía si aún no existe)."""
    ruta = Path(carpeta) / nombre
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def leer_publicaciones(carpeta=CARPETA):
    return leer("publicaciones.csv", carpeta)


def leer_metricas(carpeta=CARPETA):
    return leer("metricas.csv", carpeta)


def _orden(fila):
    """Por short, plataforma (en el orden de PLATAFORMAS) y momento (48h antes que 7d)."""
    return (fila["short"], PLATAFORMAS.index(fila["plataforma"]),
            list(MOMENTOS).index(fila["momento"]) if "momento" in fila else 0)


def escribir(nombre, filas, carpeta=CARPETA):
    """Guarda el CSV entero, ordenado y siempre con las mismas columnas."""
    columnas = COLUMNAS_PUBLICACIONES if nombre == "publicaciones.csv" else COLUMNAS_METRICAS
    ruta = Path(carpeta) / nombre
    with ruta.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(sorted(filas, key=_orden))


def fecha(texto):
    """'2026-10-03 13:45' -> datetime. Lanza ValueError si no tiene ese formato."""
    return datetime.strptime(texto.strip(), FORMATO)


def md5_corto(archivo):
    """Los 8 primeros caracteres del md5: bastan para distinguir dos versiones."""
    return hashlib.md5(Path(archivo).read_bytes()).hexdigest()[:8]


def video_publicado(short, archivo=""):
    """El vídeo de data/listos/ de un short. Si hay más de uno, hay que decir cuál."""
    if archivo:
        ruta = LISTOS / Path(archivo).name
        if not ruta.is_file():
            raise ValueError(f"No existe data/listos/{ruta.name}")
        return ruta
    candidatos = sorted(LISTOS.glob(f"{short}*.mp4"))
    if not candidatos:
        raise ValueError(f"No hay ningún vídeo de {short} en data/listos/")
    if len(candidatos) > 1:
        nombres = ", ".join(c.name for c in candidatos)
        raise ValueError(f"Hay varios vídeos de {short} en data/listos/ ({nombres}): indica cuál")
    return candidatos[0]


def nueva_publicacion(short, plataforma, publicado, archivo="", notas="", carpeta=CARPETA):
    """Añade una línea a publicaciones.csv. Devuelve la línea añadida."""
    if plataforma not in PLATAFORMAS:
        raise ValueError(f"Plataforma '{plataforma}' desconocida: {', '.join(PLATAFORMAS)}")
    fecha(publicado)
    if not (RAIZ / "shorts" / short).is_dir():
        raise ValueError(f"No existe la receta shorts/{short}/")
    filas = leer_publicaciones(carpeta)
    if any(f["short"] == short and f["plataforma"] == plataforma for f in filas):
        raise ValueError(f"{short} ya consta como publicado en {plataforma}")
    video = video_publicado(short, archivo)
    fila = {"short": short, "plataforma": plataforma, "publicado": publicado.strip(),
            "archivo": video.name, "md5": md5_corto(video), "notas": notas}
    escribir("publicaciones.csv", filas + [fila], carpeta)
    return fila


def ficha(short, archivo=""):
    """Datos del short que se guardan junto a cada medida: técnica de interacción (de
    guion.md), tema (del nombre), música (de la receta) y duración del vídeo publicado."""
    guion = RAIZ / "shorts" / short / "guion.md"
    tecnica = ""
    if guion.exists():
        encontrada = re.search(r"\*\*Técnica de interacción:\*\*\s*(.+)", guion.read_text(encoding="utf-8"))
        tecnica = encontrada.group(1).strip() if encontrada else ""
    musica = cargar_config(short)["musica"]["archivo"]
    try:
        segundos = f"{duracion(video_publicado(short, archivo)):.2f}"
    except (ValueError, RuntimeError):
        segundos = ""
    return {"tecnica": tecnica, "tema": short.split("-", 1)[-1],
            "musica": Path(musica).stem if musica else "", "duracion_s": segundos}


def pendientes(ahora=None, carpeta=CARPETA):
    """Las medidas que faltan de cada publicación: 'pendiente' si ya ha llegado su hora,
    'próxima' si todavía no. Ordenadas por la hora a la que tocan."""
    ahora = ahora or datetime.now()
    hechas = {(m["short"], m["plataforma"], m["momento"]) for m in leer_metricas(carpeta)}
    resultado = []
    for p in leer_publicaciones(carpeta):
        for momento, horas in MOMENTOS.items():
            if (p["short"], p["plataforma"], momento) in hechas:
                continue
            cuando = fecha(p["publicado"]) + timedelta(hours=horas)
            resultado.append({"short": p["short"], "plataforma": p["plataforma"], "momento": momento,
                              "cuando": cuando, "estado": "pendiente" if cuando <= ahora else "próxima"})
    return sorted(resultado, key=lambda m: (m["cuando"], _orden(m)))


def _numero(campo, texto):
    """Convierte una cifra del CSV o de la línea de órdenes. Vacío -> None."""
    texto = str(texto).strip().replace(",", ".")
    if not texto:
        return None
    valor = float(texto)
    if campo in ENTEROS:
        if valor != int(valor):
            raise ValueError(f"{campo} tiene que ser un número entero ({texto})")
        valor = int(valor)
    return valor


def nueva_medida(datos, reemplazar=False, carpeta=CARPETA):
    """Valida una medida y la guarda en metricas.csv. 'datos' trae short, plataforma,
    momento, medido y las cifras que se sepan. Devuelve (fila, faltan, avisos); si algo
    está mal, lanza ValueError sin escribir nada."""
    short, plataforma, momento = datos["short"], datos["plataforma"], datos["momento"]
    if plataforma not in PLATAFORMAS:
        raise ValueError(f"Plataforma '{plataforma}' desconocida: {', '.join(PLATAFORMAS)}")
    if momento not in MOMENTOS:
        raise ValueError(f"Momento '{momento}' desconocido: {', '.join(MOMENTOS)}")
    publicacion = next((p for p in leer_publicaciones(carpeta)
                        if p["short"] == short and p["plataforma"] == plataforma), None)
    if not publicacion:
        raise ValueError(f"{short} no consta como publicado en {plataforma}: "
                         f"regístralo antes con 'publicacion'")

    metricas = leer_metricas(carpeta)
    clave = (short, plataforma, momento)
    anterior = next((m for m in metricas if (m["short"], m["plataforma"], m["momento"]) == clave), None)
    if anterior and not reemplazar:
        raise ValueError(f"Ya hay una medida de {short} en {plataforma} a las {momento}: "
                         f"usa --reemplazar para corregirla o completarla")
    if anterior:
        # Al corregir o completar, lo que no se indica se conserva de la medida anterior
        datos = {**datos, **{campo: anterior[campo] for campo in NUMEROS + ["medido", "notas"]
                             if datos.get(campo) in (None, "")}}
    medido = fecha(datos.get("medido") or datetime.now().strftime(FORMATO))

    fila = {"short": short, "plataforma": plataforma, "momento": momento,
            "medido": medido.strftime(FORMATO), "notas": datos.get("notas", "")}
    valores = {}
    for campo in NUMEROS:
        valor = _numero(campo, datos.get(campo, "") if datos.get(campo) is not None else "")
        if valor is not None and valor < 0:
            raise ValueError(f"{campo} no puede ser negativo ({valor})")
        valores[campo] = valor
        fila[campo] = "" if valor is None else f"{valor:g}"
    if valores["se_quedaron_pct"] is not None:
        if plataforma != "youtube":
            raise ValueError("El porcentaje que se quedó a verlo solo existe en YouTube")
        if valores["se_quedaron_pct"] > 100:
            raise ValueError(f"se_quedaron_pct es un porcentaje: de 0 a 100 ({valores['se_quedaron_pct']:g})")
    fila.update(ficha(short, publicacion["archivo"]))

    faltan = [c for c in NUMEROS if valores[c] is None
              and not (c == "se_quedaron_pct" and plataforma != "youtube")]
    avisos = []
    if valores["visualizaciones"] is not None:
        for campo in ("likes", "comentarios", "compartidos"):
            if valores[campo] is not None and valores[campo] > valores["visualizaciones"]:
                avisos.append(f"Hay más {campo} ({valores[campo]}) que visualizaciones "
                              f"({valores['visualizaciones']}): ¿se ha leído bien?")
    horas = (medido - fecha(publicacion["publicado"])).total_seconds() / 3600
    diferencia = horas - MOMENTOS[momento]
    if diferencia > TOLERANCIA:
        avisos.append(f"Medida {diferencia:.0f} h después de las {momento}: las cifras serán algo más altas")
    elif diferencia < -TOLERANCIA:
        avisos.append(f"Medida {-diferencia:.0f} h antes de las {momento}: las cifras serán algo más bajas")

    otras = [m for m in metricas if (m["short"], m["plataforma"], m["momento"]) != clave]
    escribir("metricas.csv", otras + [fila], carpeta)
    return fila, faltan, avisos
