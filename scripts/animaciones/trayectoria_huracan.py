"""Animación de la trayectoria de un huracán (019): el punto donde se formó, el recorrido
real que se va dibujando, la previsión del NHC con su cono de incertidumbre y los lugares
importantes. Arriba, siempre, que es una previsión, de qué aviso y de qué hora, y la fuente.

Tiempos, en fracciones de la duración (8 s por defecto):
- 0-0,07: fundido del mapa y pulso en el punto de formación;
- 0,07-0,5: la línea amarilla del recorrido real, con un punto que avanza y su fecha;
- 0,5-0,75: el cono y la línea discontinua de la previsión, con «PREVISIÓN»;
- 0,75-0,92: los lugares, uno detrás de otro; después se queda quieto.

El mapa base (tierra, fronteras, cabecera) se dibuja una vez; en cada fotograma se restaura y
solo se pinta lo que cambia (blitting). Los fotogramas van a FFmpeg por una tubería: no se
guarda ningún PNG y la memoria se queda en unos cientos de MB.
"""
import math
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

from matplotlib.lines import Line2D
from matplotlib.patches import Polygon

from . import mapa, nhc

FPS = 30
# Medio segundo más, quieto, al final: el montaje (filtro fps) pierde el último fotograma de un
# vídeo cortado hasta su final, y así un [plano <animación> 0 8] tiene sus 8 s completos
COLCHON = 0.5
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
TIPOS = {"Major Hurricane": "huracán mayor", "Hurricane": "huracán", "Tropical Storm": "tormenta tropical",
         "Tropical Depression": "depresión tropical", "Subtropical Storm": "tormenta subtropical",
         "Subtropical Depression": "depresión subtropical", "Post-Tropical Cyclone": "ciclón postropical"}
FASES = {"formacion": (0.0, 0.07), "real": (0.07, 0.5), "prevision": (0.5, 0.75), "lugares": (0.75, 0.92)}


def suave(x):
    """0-1 con arranque y llegada suaves."""
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def avance(t, fase):
    a, b = FASES[fase]
    return suave((t - a) / (b - a))


def fecha_corta(cuando):
    return f"{cuando.day} {MESES[cuando.month - 1]}"


def recortar(linea, fraccion):
    """Los puntos de una polilínea hasta esa fracción de su longitud (en el mapa proyectado),
    y el punto final."""
    tramos = [math.dist(a, b) for a, b in zip(linea, linea[1:])]
    falta = sum(tramos) * fraccion
    puntos = [linea[0]]
    for (a, b), largo in zip(zip(linea, linea[1:]), tramos):
        if falta >= largo:
            puntos.append(b)
            falta -= largo
            continue
        if largo > 0:
            k = falta / largo
            puntos.append((a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k))
        break
    return puntos


def crear(ficha, salida, cache):
    """Genera el vídeo y devuelve lo que se ha usado (aviso, hora, fuentes) para registrarlo."""
    segundos = float(ficha.get("segundos", 8))
    real = nhc.trayectoria_real(ficha["tormenta"], cache / "nhc")
    prev = nhc.prevision(ficha["tormenta"], ficha.get("aviso", "ultimo"), cache / "nhc")
    lugares = ficha.get("lugares", [])

    # Recorrido real: desde la formación hasta la posición del aviso (el "ahora")
    ahora = prev["linea"][0]
    recorrido = [(lon, lat) for _, lon, lat, _, _ in real]
    tiempos = [p[0] for p in real]
    if prev["hora"] > tiempos[-1] and math.dist(recorrido[-1], ahora) > 0.05:
        recorrido.append(ahora)
        tiempos.append(prev["hora"])

    todo = recorrido + prev["linea"] + [p for anillo in prev["cono"] for p in anillo] \
        + [(lon, lat) for _, lat, lon, *_ in lugares]
    limites = mapa.encuadre(todo)
    fig, ax = mapa.lienzo(limites)
    mapa.dibujar_base(ax, limites, cache / "mapas")

    # Cabecera fija: qué es, que es una previsión, de qué aviso y hora, y la fuente
    hora_es = prev["hora"].astimezone(ZoneInfo("Europe/Madrid"))
    alto = lambda px: 1 - px / mapa.ALTO
    fig.patches.append(Polygon([(0, 1), (1, 1), (1, alto(370)), (0, alto(370))], closed=True,
                               transform=fig.transFigure, facecolor=mapa.MAR, alpha=0.82, zorder=5))
    for y, cadena, px, color, negrita in [
        (150, ficha.get("titulo", "Huracán").upper(), 66, mapa.TEXTO, True),
        (228, f"PREVISIÓN DEL AVISO {prev['numero']} DEL NHC", 38, mapa.AMARILLO, True),
        (282, f"{fecha_corta(hora_es)} {hora_es.year} · {hora_es:%H:%M} hora de España", 36, mapa.TEXTO, False),
        (335, "Fuente: NHC/NOAA · Mapa: Natural Earth", 27, "#C9D1E3", False),
    ]:
        mapa.texto(fig, 0.5, alto(y), cadena, px, color=color, negrita=negrita, ha="center",
                   va="center", zorder=6)

    fig.canvas.draw()
    fondo = fig.canvas.copy_from_bbox(fig.bbox)

    # Lo que se mueve (animated=True: no entra en el dibujo del fondo)
    proy = lambda lonlat: mapa.proyectar(*lonlat)
    recorrido_p = [proy(p) for p in recorrido]
    linea_prev = [proy(p) for p in prev["linea"]]
    cono = [Polygon([proy(p) for p in anillo], closed=True, facecolor="white", edgecolor="white",
                    linewidth=mapa.pt(2.5), zorder=4, animated=True) for anillo in prev["cono"]]
    for c in cono:
        ax.add_patch(c)
    trazo_prev = ax.add_line(Line2D([], [], color="white", linewidth=mapa.pt(6), dashes=(2.2, 1.6),
                                    zorder=5, animated=True))
    brillo = ax.add_line(Line2D([], [], color=mapa.AMARILLO, linewidth=mapa.pt(24), alpha=0.28,
                                solid_capstyle="round", zorder=6, animated=True))
    trazo = ax.add_line(Line2D([], [], color=mapa.AMARILLO, linewidth=mapa.pt(9),
                               solid_capstyle="round", solid_joinstyle="round", zorder=7, animated=True))
    origen = recorrido_p[0]
    pulso = ax.add_line(Line2D([origen[0]], [origen[1]], marker="o", markersize=mapa.pt(30),
                               markerfacecolor="none", markeredgecolor=mapa.AMARILLO, zorder=8, animated=True))
    punto_origen = ax.add_line(Line2D([origen[0]], [origen[1]], marker="o", markersize=mapa.pt(22),
                                      color=mapa.AMARILLO, markeredgecolor="white",
                                      markeredgewidth=mapa.pt(3), zorder=9, animated=True))
    cabeza = ax.add_line(Line2D([], [], marker="o", markersize=mapa.pt(30), color=mapa.AMARILLO,
                                markeredgecolor="white", markeredgewidth=mapa.pt(4), zorder=10, animated=True))

    def etiqueta(xy, cadena, px, dx, dy, color=mapa.TEXTO, negrita=True, ha="left"):
        return ax.annotate(cadena, xy=xy, xytext=(mapa.pt(dx), mapa.pt(dy)), textcoords="offset points",
                           fontsize=mapa.pt(px), color=color, family=mapa.FUENTE,
                           weight="bold" if negrita else "normal", ha=ha, va="center",
                           path_effects=mapa.contorno(7), zorder=11, animated=True)

    lado = 1 if origen[0] < (limites[0] + limites[1]) / 2 else -1
    texto_origen = etiqueta(origen, f"Se formó aquí\n{fecha_corta(tiempos[0])}", 40, 0, -78,
                            ha="center")
    texto_fecha = etiqueta(origen, "", 38, 36 * lado, 0, color=mapa.AMARILLO, ha="left" if lado > 0 else "right")
    tipo_ahora = prev["puntos"][0]
    km_h = round(tipo_ahora[3] * 1.852 / 5) * 5
    categoria = (f"categoría {tipo_ahora[4]}" if tipo_ahora[4] else TIPOS.get(tipo_ahora[5], tipo_ahora[5]))
    texto_ahora = etiqueta(proy(ahora), f"AHORA\n{categoria}\n{km_h} km/h", 38, 40, 0)  # corto: cabe a la derecha
    centro_cono = linea_prev[len(linea_prev) // 2]
    texto_prev = etiqueta(centro_cono, "PREVISIÓN", 46, 70, 0, color=mapa.MAR)
    texto_prev.set_bbox({"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "none"})
    texto_prev.set_path_effects([])

    # Etiquetas de día de la previsión: una por día nuevo (sáb 10, dom 11...), sin la de hoy
    dias = []
    visto = {prev["hora"].astimezone(ZoneInfo("America/Chicago")).date()}
    for lon, lat, fecha, *_ in prev["puntos"][1:]:
        dia = datetime.strptime(fecha.split()[0], "%Y-%m-%d").date()
        if dia not in visto:
            visto.add(dia)
            xy = proy((lon, lat))
            marca = ax.add_line(Line2D([xy[0]], [xy[1]], marker="o", markersize=mapa.pt(14), color="white",
                                       zorder=6, animated=True))
            # A la derecha (tierra adentro): a la izquierda chocaban con los lugares de la costa
            dias.append((xy, marca, etiqueta(xy, f"{DIAS[dia.weekday()]} {dia.day}", 32, 24, 0,
                                             negrita=False, ha="left")))

    # Dónde va el nombre de cada lugar respecto a su punto (cuarto valor de la ficha)
    posiciones = {"derecha": (20, 0, "left"), "izquierda": (-20, 0, "right"),
                  "abajo": (0, -34, "center"), "arriba": (0, 34, "center")}
    sitios = []
    for nombre, lat, lon, *resto in lugares:
        xy = proy((lon, lat))
        dx, dy, ha = posiciones[resto[0] if resto else "derecha"]
        marca = ax.add_line(Line2D([xy[0]], [xy[1]], marker="o", markersize=mapa.pt(13), color="white",
                                   markeredgecolor=mapa.MAR, markeredgewidth=mapa.pt(3), zorder=9, animated=True))
        sitios.append((marca, etiqueta(xy, nombre, 34, dx, dy, negrita=False, ha=ha)))

    # Longitud acumulada del recorrido real, para saber qué fecha toca a cada fracción
    acumulado = [0.0]
    for a, b in zip(recorrido_p, recorrido_p[1:]):
        acumulado.append(acumulado[-1] + math.dist(a, b))

    animados = round(segundos * FPS)
    total = round((segundos + COLCHON) * FPS)
    ffmpeg = subprocess.Popen([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{mapa.ANCHO}x{mapa.ALTO}", "-r", str(FPS), "-i", "-",
        "-vf", f"fade=t=in:st=0:d=0.4:color={mapa.MAR}",
        "-frames:v", str(total), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        str(salida),
    ], stdin=subprocess.PIPE)
    for n in range(total):
        t = min(1.0, n / animados)
        fig.canvas.restore_region(fondo)
        visibles = []

        # Formación: un pulso que se abre y se apaga, y el punto
        p = (t * segundos) / 1.2
        if p < 1:
            pulso.set_markersize(mapa.pt(30 + 90 * p))
            pulso.set_alpha(1 - p)
            pulso.set_markeredgewidth(mapa.pt(6 * (1 - p) + 1))
            visibles.append(pulso)
        texto_origen.set_alpha(avance(t, "formacion"))
        visibles += [punto_origen, texto_origen]

        # Previsión (debajo del recorrido real)
        a_prev = avance(t, "prevision")
        if a_prev > 0:
            for c in cono:
                c.set_facecolor((1, 1, 1, 0.20 * a_prev))
                c.set_edgecolor((1, 1, 1, 0.75 * a_prev))
            visibles += cono
            xs, ys = zip(*recortar(linea_prev, a_prev))
            trazo_prev.set_data(xs, ys)
            visibles.append(trazo_prev)
            alfa_prev = suave((a_prev - 0.4) / 0.3)
            texto_prev.set_alpha(alfa_prev)
            texto_prev.get_bbox_patch().set_alpha(alfa_prev)     # el recuadro, con el texto
            visibles.append(texto_prev)
            for xy, marca, texto_dia in dias:
                hecho = math.dist(linea_prev[0], xy) <= math.dist(linea_prev[0], (xs[-1], ys[-1])) + 1e-6
                if hecho:
                    visibles += [marca, texto_dia]

        # Recorrido real
        a_real = avance(t, "real")
        if a_real > 0:
            parte = recortar(recorrido_p, a_real)
            xs, ys = zip(*parte)
            for linea in (brillo, trazo):
                linea.set_data(xs, ys)
            cabeza.set_data([xs[-1]], [ys[-1]])
            hecho = acumulado[-1] * a_real
            i = max(k for k, largo in enumerate(acumulado) if largo <= hecho + 1e-9)
            texto_fecha.xy = (xs[-1], ys[-1])
            texto_fecha.set_text(fecha_corta(tiempos[i]))
            visibles += [brillo, trazo, cabeza]
            if a_real < 1:
                visibles.append(texto_fecha)
            else:
                texto_ahora.set_alpha(suave((t - FASES["real"][1]) / 0.05))
                visibles.append(texto_ahora)

        # Lugares, uno detrás de otro
        a_lug = avance(t, "lugares")
        for k, (marca, nombre) in enumerate(sitios):
            alfa = suave(a_lug * len(sitios) - k)
            if alfa > 0:
                marca.set_alpha(alfa)
                nombre.set_alpha(alfa)
                visibles += [marca, nombre]

        for artista in sorted(visibles, key=lambda a: a.get_zorder()):
            ax.draw_artist(artista)
        ffmpeg.stdin.write(bytes(fig.canvas.buffer_rgba()))
    ffmpeg.stdin.close()
    if ffmpeg.wait() != 0:
        raise RuntimeError("FFmpeg no ha podido crear el vídeo de la animación")

    return {
        "aviso": prev["numero"],
        "hora_aviso_utc": prev["hora"].isoformat(),
        "hora_aviso_espana": hora_es.isoformat(),
        "fotogramas": total,
        "fuentes": ["https://www.nhc.noaa.gov/gis/", prev["url"], "https://www.naturalearthdata.com/"],
        "fuente": "NHC/NOAA + Natural Earth", "url": prev["url"], "licencia": "Dominio público",
        "licencia_url": "https://www.naturalearthdata.com/about/terms-of-use/",
    }
