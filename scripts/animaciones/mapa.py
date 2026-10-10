"""Mapa base para las animaciones: Natural Earth (dominio público) en proyección Mercator, con
los colores de la marca, en un lienzo vertical de 1080x1920.

La proyección se hace a mano: x = longitud, y = la latitud de Mercator, las dos en grados
(así un grado de longitud mide lo mismo en x que en y cerca del ecuador). Para un mapa de una
región no hace falta nada más (cartopy arrastraría GEOS y PROJ).

encuadre() coloca lo importante (la trayectoria, el cono, los lugares) dentro de una ventana
de la pantalla que deja libres la cabecera de arriba y la zona de los subtítulos (que van a
560 px del borde de abajo), y alarga el mapa hasta los bordes del lienzo.
"""
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import patheffects
from matplotlib.collections import LineCollection, PolyCollection

from .nhc import descargar, shapefile

ANCHO, ALTO, DPI = 1080, 1920, 100
NE = "https://naciscdn.org/naturalearth/50m/"
CAPAS = {
    "tierra": "physical/ne_50m_land",
    "paises": "cultural/ne_50m_admin_0_countries",
    "estados": "cultural/ne_50m_admin_1_states_provinces",
    "lagos": "physical/ne_50m_lakes",
}
# Colores de la marca (subtitulos de config/por_defecto.json): azul marino y amarillo
MAR = "#14213D"
TIERRA = "#2B3D63"
FRONTERA = "#7D8DB0"
TEXTO = "#FFFFFF"
AMARILLO = "#FFC93C"
FUENTE = "DejaVu Sans"
# Ventana de la pantalla (en píxeles desde arriba) donde tiene que caber lo importante
VENTANA = {"x": (70, 1010), "y": (400, 1180)}


def pt(px):
    """Píxeles -> puntos de matplotlib (los tamaños de letra y los gruesos van en puntos)."""
    return px * 72 / DPI


def mercator(lat):
    return math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


def proyectar(lon, lat):
    return lon, mercator(lat)


def encuadre(puntos):
    """Límites (x0, x1, y0, y1) del lienzo para que los puntos (lon, lat) queden dentro de
    VENTANA, con la escala más grande posible y sin deformar."""
    xs = [p[0] for p in puntos]
    ys = [mercator(p[1]) for p in puntos]
    (vx0, vx1), (vy0, vy1) = VENTANA["x"], VENTANA["y"]
    escala = min((vx1 - vx0) / (max(xs) - min(xs)), (vy1 - vy0) / (max(ys) - min(ys)))  # px por grado
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    vcx, vcy = (vx0 + vx1) / 2, (vy0 + vy1) / 2
    x0 = cx - vcx / escala
    y1 = cy + vcy / escala                  # el borde de arriba del lienzo (y crece hacia arriba)
    return x0, x0 + ANCHO / escala, y1 - ALTO / escala, y1


def lienzo(limites):
    """Figura de 1080x1920 sin márgenes, con el mar de fondo y los límites dados."""
    fig = plt.figure(figsize=(ANCHO / DPI, ALTO / DPI), dpi=DPI, facecolor=MAR)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(MAR)
    ax.set_xlim(limites[0], limites[1])
    ax.set_ylim(limites[2], limites[3])
    ax.set_axis_off()
    return fig, ax


def _anillos(capa_ne, cache, limites, filtro=None):
    """Los anillos de los polígonos de una capa de Natural Earth que tocan los límites,
    ya proyectados."""
    nombre = CAPAS[capa_ne]
    zip_ = descargar(f"{NE}{nombre}.zip", cache / f"{nombre.split('/')[-1]}.zip")
    lector = shapefile.Reader(str(zip_))
    x0, x1, y0, y1 = limites
    anillos = []
    for s in lector.iterShapeRecords():
        if filtro and not filtro(s.record.as_dict()):
            continue
        b = s.shape.bbox                   # lon y lat (sin proyectar)
        if b[2] < x0 or b[0] > x1 or mercator(min(b[3], 85)) < y0 or mercator(max(b[1], -85)) > y1:
            continue
        partes = list(s.shape.parts) + [len(s.shape.points)]
        for a, z in zip(partes, partes[1:]):
            anillos.append([proyectar(lon, max(-85, min(85, lat))) for lon, lat in s.shape.points[a:z]])
    return anillos


def dibujar_base(ax, limites, cache, estados_de=("USA", "MEX")):
    """Tierra, lagos, fronteras de países y, de los países de estados_de, sus estados."""
    ax.add_collection(PolyCollection(_anillos("tierra", cache, limites), facecolors=TIERRA,
                                     edgecolors="none", zorder=1))
    ax.add_collection(PolyCollection(_anillos("lagos", cache, limites), facecolors=MAR,
                                     edgecolors="none", zorder=2))
    estados = _anillos("estados", cache, limites, lambda r: r.get("adm0_a3") in estados_de)
    ax.add_collection(LineCollection(estados, colors=FRONTERA, linewidths=pt(1.2), alpha=0.45, zorder=3))
    ax.add_collection(LineCollection(_anillos("paises", cache, limites), colors=FRONTERA,
                                     linewidths=pt(2.2), alpha=0.9, zorder=3))


def contorno(px=6):
    """Contorno azul marino para que el texto se lea encima de cualquier cosa (como los
    subtítulos)."""
    return [patheffects.withStroke(linewidth=pt(px), foreground=MAR)]


def texto(ax_o_fig, x, y, cadena, px, color=TEXTO, negrita=False, **kw):
    """Texto con la fuente de la marca y contorno; px es el alto de la letra en píxeles."""
    return ax_o_fig.text(x, y, cadena, fontsize=pt(px), color=color, family=FUENTE,
                         weight="bold" if negrita else "normal", path_effects=contorno(), **kw)


def grabar(fig, total, salida, fotograma, fundido=0.4):
    """Graba total fotogramas de fig en salida (1080x1920, 30 fps): para cada uno llama a
    fotograma(n), que lo prepara, y pasa la imagen a FFmpeg por una tubería, sin guardar PNG.
    Empieza con un fundido desde el azul marino. (Los tipos anteriores llevan esto copiado; el
    de comparacion_escala ya usa esta función.)"""
    import subprocess
    ffmpeg = subprocess.Popen([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{ANCHO}x{ALTO}", "-r", "30", "-i", "-",
        "-vf", f"fade=t=in:st=0:d={fundido}:color={MAR}",
        "-frames:v", str(total), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        str(salida),
    ], stdin=subprocess.PIPE)
    for n in range(total):
        fotograma(n)
        ffmpeg.stdin.write(bytes(fig.canvas.buffer_rgba()))
    ffmpeg.stdin.close()
    if ffmpeg.wait() != 0:
        raise RuntimeError("FFmpeg no ha podido crear el vídeo de la animación")
