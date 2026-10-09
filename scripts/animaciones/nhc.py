"""Datos del Centro Nacional de Huracanes de EE. UU. (NHC/NOAA, dominio público) para las
animaciones: la trayectoria real (best track preliminar) y la previsión de un aviso (línea,
puntos y cono de incertidumbre), de sus shapefiles en https://www.nhc.noaa.gov/gis/.

Se guardan en data/cache/nhc/. La previsión de un aviso no cambia nunca (forecast/archive/
<tormenta>_5day_NNN.zip), así que se descarga una vez; la trayectoria real se actualiza con
cada aviso y se vuelve a pedir si tiene más de una hora. Con aviso "ultimo" se pide
<tormenta>_5day_latest.zip y el número sale del nombre de sus archivos.

Las tablas de los puntos traen la latitud y la longitud redondeadas a grados enteros: las
posiciones se toman de la geometría del shapefile, que lleva los decimales.
"""
import re
import shutil
import time
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone

import shapefile

GIS = "https://www.nhc.noaa.gov/gis/"
AGENTE = "fabrica-de-shorts (proyecto de aprendizaje)"
CADUCIDAD = 3600          # segundos que vale la trayectoria real guardada
# Zonas horarias de los avisos (ADVDATE: "400 AM CDT Fri Oct 09 2026")
HUSOS = {"UTC": 0, "AST": -4, "EDT": -4, "EST": -5, "CDT": -5, "CST": -6, "MDT": -6, "PDT": -7}
MESES_EN = {m: n for n, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug",
                                        "Sep", "Oct", "Nov", "Dec"], start=1)}


def descargar(url, destino, caducidad=None):
    """Descarga url en destino, salvo que ya esté (y no tenga más de caducidad segundos)."""
    if destino.exists() and (caducidad is None or time.time() - destino.stat().st_mtime < caducidad):
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    temporal = destino.with_suffix(".parcial")
    with urllib.request.urlopen(peticion, timeout=60) as respuesta, temporal.open("wb") as f:
        shutil.copyfileobj(respuesta, f)
    temporal.replace(destino)
    return destino


def capa(zip_, final):
    """La capa del zip cuyo nombre acaba en final ("_pts", "5day_pgn"...), con pyshp."""
    with zipfile.ZipFile(zip_) as z:
        nombres = [n for n in z.namelist() if n.endswith(f"{final}.shp")]
    if not nombres:
        raise RuntimeError(f"{zip_.name} no tiene la capa {final}")
    return shapefile.Reader(f"{zip_}/{nombres[0]}")


def hora_del_aviso(advdate):
    """'400 AM CDT Fri Oct 09 2026' -> datetime en UTC."""
    m = re.match(r"(\d{1,2})(\d\d) (AM|PM) (\w+) \w+ (\w+) (\d+) (\d{4})", advdate.strip())
    if not m or m.group(4) not in HUSOS:
        raise RuntimeError(f"No sé leer la hora del aviso: {advdate!r}")
    hora = int(m.group(1)) % 12 + (12 if m.group(3) == "PM" else 0)
    local = datetime(int(m.group(7)), MESES_EN[m.group(5)], int(m.group(6)), hora, int(m.group(2)))
    return (local - timedelta(hours=HUSOS[m.group(4)])).replace(tzinfo=timezone.utc)


def trayectoria_real(tormenta, cache):
    """[(datetime UTC, lon, lat, tipo, viento en nudos)] desde que es depresión tropical (antes,
    el NHC la sigue como perturbación: 'DB', 'LO'...)."""
    zip_ = descargar(f"{GIS}best_track/{tormenta}_best_track.zip",
                     cache / f"{tormenta}_best_track.zip", CADUCIDAD)
    puntos = []
    for s in capa(zip_, "_pts").iterShapeRecords():
        r = s.record.as_dict()
        lon, lat = s.shape.points[0]
        cuando = datetime.strptime(str(r["DTG"]), "%Y%m%d%H").replace(tzinfo=timezone.utc)
        puntos.append((cuando, lon, lat, r["STORMTYPE"].strip(), r["INTENSITY"]))
    puntos.sort()
    ciclon = [i for i, p in enumerate(puntos) if p[3] in ("TD", "TS", "HU", "SD", "SS", "MH")]
    if not ciclon:
        raise RuntimeError(f"{tormenta}: la trayectoria real todavía no tiene ningún punto de ciclón")
    return puntos[ciclon[0]:]


def prevision(tormenta, aviso, cache):
    """La previsión de un aviso ("ultimo" o su número): un diccionario con el número, la hora
    (UTC), la línea [(lon, lat)], los puntos [(lon, lat, etiqueta de fecha, viento, categoría,
    tipo)] y el cono [[(lon, lat)], ...] (una lista por cada anillo)."""
    if str(aviso) == "ultimo":
        temporal = descargar(f"{GIS}forecast/archive/{tormenta}_5day_latest.zip",
                             cache / f"{tormenta}_5day_latest.zip", CADUCIDAD)
        with zipfile.ZipFile(temporal) as z:
            numeros = {re.search(r"-(\d{3})[A-Z]?_5day", n).group(1) for n in z.namelist() if "_5day" in n}
        aviso = max(numeros)
        destino = cache / f"{tormenta}_5day_{aviso}.zip"
        if not destino.exists():
            shutil.copy(temporal, destino)
    aviso = f"{int(aviso):03}"
    zip_ = descargar(f"{GIS}forecast/archive/{tormenta}_5day_{aviso}.zip", cache / f"{tormenta}_5day_{aviso}.zip")

    lin = capa(zip_, "5day_lin")
    datos = lin.record(0).as_dict()
    puntos = []
    for s in capa(zip_, "5day_pts").iterShapeRecords():
        r = s.record.as_dict()
        lon, lat = s.shape.points[0]
        puntos.append((lon, lat, r["FLDATELBL"].strip(), r["MAXWIND"], r["SSNUM"], r["TCDVLP"].strip()))
    cono = capa(zip_, "5day_pgn").shape(0)
    partes = list(cono.parts) + [len(cono.points)]
    return {
        "numero": int(aviso),
        "hora": hora_del_aviso(datos["ADVDATE"]),
        "linea": [tuple(p) for p in lin.shape(0).points],
        "puntos": puntos,
        "cono": [cono.points[a:b] for a, b in zip(partes, partes[1:])],
        "url": f"{GIS}forecast/archive/{tormenta}_5day_{aviso}.zip",
    }
