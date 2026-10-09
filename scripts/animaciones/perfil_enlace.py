"""Animación del perfil de un enlace fijo visto de lado (020, el puente de Øresund): un puente
que baja a una isla y se mete bajo el mar en un túnel. Un punto amarillo (un coche) lo recorre
de un extremo a otro, dejando su rastro, y al llegar al túnel se hunde bajo el agua (el agua
se dibuja por encima del coche, así que desaparece de verdad). Al final, si la ficha lo pide,
cruza un avión por encima.

Es un esquema: las distancias en horizontal son a escala (los km de cada tramo y dónde están
las torres) y las alturas van exageradas para que se vean (por encima del agua 2,6 px por metro
y por debajo 10). La pantalla lo dice.

Ficha (shorts/<short>/animaciones/<nombre>.json):
  "tramos": [{"tipo": "puente"|"isla"|"tunel", "km": 7.845, "nombre": "PUENTE · 7,8 km"}, ...]
  "extremos": ["Malmö\\nSuecia", "Copenhague\\nDinamarca"]
  "torres_km": [3.88, 4.37] (desde el principio del primer tramo), "torres_m": 204, "galibo_m": 57
  "titulo", "subtitulo", "nota", "fuente", "avion": true|false, "segundos": 8
"""
import subprocess

from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle

from . import mapa

FPS = 30
COLCHON = 0.5          # como en trayectoria_huracan: el montaje pierde el último fotograma
X0, X1 = 90, 990       # dónde empieza y acaba el enlace en la pantalla (px)
MAR_Y = 1050           # nivel del mar (px desde arriba)
FONDO_Y = MAR_Y + 100  # fondo del mar (unos 10 m, exagerado)
ARRIBA, ABAJO = 2.6, 10.0  # px por metro por encima y por debajo del agua (el túnel no baja
                           # de 1250 px: ahí empiezan los subtítulos)
AGUA = "#1E4A86"
LECHO = "#0B1428"
LENTO_TUNEL = 1.6      # el coche va más despacio en el túnel: es la revelación
VIAJE = (0.06, 0.82)   # fracciones de la duración en las que el coche recorre el enlace


def suave(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def crear(ficha, salida, cache):
    segundos = float(ficha.get("segundos", 8))
    tramos = ficha["tramos"]
    total_km = sum(t["km"] for t in tramos)
    escala = (X1 - X0) / total_km
    x = lambda km: X0 + km * escala
    y = lambda m: MAR_Y - m * (ARRIBA if m >= 0 else ABAJO)

    fig, ax = mapa.lienzo((0, mapa.ANCHO, mapa.ALTO, 0))      # coordenadas en píxeles, y hacia abajo

    # Agua y fondo (el agua de verdad se pinta encima del coche, más abajo)
    ax.add_patch(Rectangle((0, MAR_Y), mapa.ANCHO, mapa.ALTO - MAR_Y, color=LECHO, zorder=1))
    ax.add_patch(Rectangle((0, MAR_Y), mapa.ANCHO, FONDO_Y - MAR_Y, color=AGUA, zorder=1))
    # Tierra en los dos extremos
    for pts in ([(0, y(14)), (X0 + 4, y(10)), (X0 + 4, FONDO_Y + 200), (0, FONDO_Y + 200)],
                [(X1 - 4, y(6)), (mapa.ANCHO, y(12)), (mapa.ANCHO, FONDO_Y + 200), (X1 - 4, FONDO_Y + 200)]):
        ax.add_patch(Polygon(pts, closed=True, facecolor=mapa.TIERRA, edgecolor=mapa.FRONTERA,
                             linewidth=mapa.pt(1.5), zorder=2))

    # El recorrido del coche: [(km, metros)], tramo a tramo
    camino = [(-1.2, 12), (0.0, 10)]
    inicio = 0.0
    torres_km = ficha.get("torres_km", [])
    galibo = ficha.get("galibo_m", 50)
    etiquetas = []                       # (texto, x, y, km de inicio del tramo, tipo)
    tunel = None
    for t in tramos:
        fin = inicio + t["km"]
        if t["tipo"] == "puente":
            if torres_km:
                a, b = min(torres_km) - 0.15, max(torres_km) + 0.15
                camino += [(a, galibo), (b, galibo)]
            camino.append((fin, 10))
            # Pilas cada 200 m (en el dibujo)
            for k in [inicio + 0.2 * i for i in range(1, int(t["km"] / 0.2))]:
                h = altura(camino, k)
                ax.plot([x(k), x(k)], [y(h) + 4, MAR_Y], color=mapa.FRONTERA, linewidth=mapa.pt(2), zorder=3)
            for k in torres_km:
                tope = y(ficha.get("torres_m", 200))
                ax.plot([x(k), x(k)], [tope, MAR_Y], color="#C9D1E3", linewidth=mapa.pt(6), zorder=4)
                for d in (-0.45, -0.3, -0.15, 0.15, 0.3, 0.45):          # tirantes en abanico
                    ax.plot([x(k), x(k + d)], [tope + 6, y(galibo)], color="#C9D1E3", linewidth=mapa.pt(1.2),
                            alpha=0.7, zorder=3)
            if torres_km:
                mapa.texto(ax, x(max(torres_km)) + 14, y(ficha.get("torres_m", 200)) + 4,
                           f"{ficha.get('torres_m')} m", 30, ha="left", va="center", zorder=8)
            etiquetas.append((t["nombre"], x((inicio + fin) / 2), y(galibo) - 90, inicio, t["tipo"]))
        elif t["tipo"] == "isla":
            camino.append((fin - 0.15, 8))
            ax.add_patch(Polygon([(x(inicio) - 6, MAR_Y + 3), (x(inicio + 0.3), y(10)), (x(fin - 0.6), y(14)),
                                  (x(fin), MAR_Y + 3)], closed=True, facecolor="#4F6B4A",
                                 edgecolor="#8FAF86", linewidth=mapa.pt(1.5), zorder=2))
            etiquetas.append((t["nombre"], x((inicio + fin) / 2), y(14) - 80, inicio, t["tipo"]))
        elif t["tipo"] == "tunel":
            camino += [(inicio + 0.35, -17), (fin - 0.3, -17), (fin, 4)]
            tunel = (x(inicio + 0.2), x(fin - 0.15))
            etiquetas.append((t["nombre"], x((inicio + fin) / 2), MAR_Y - 60, inicio, t["tipo"]))  # sobre el agua, encima del tubo
        inicio = fin
    camino.append((total_km + 1.2, 10))
    puntos = [(x(k), y(m)) for k, m in camino]

    # La calzada entera, gris; el coche la irá pintando de amarillo
    xs, ys = zip(*puntos)
    ax.plot(xs, ys, color="#DDE3F0", linewidth=mapa.pt(5), solid_capstyle="round", zorder=5)

    # Cabecera: qué es, que es un esquema con alturas exageradas, y la fuente
    for yy, cadena, px, color, negrita in [
        (150, ficha.get("titulo", "").upper(), 66, mapa.TEXTO, True),
        (228, ficha.get("subtitulo", "").upper(), 38, mapa.AMARILLO, True),
        (282, ficha.get("nota", "Esquema: alturas exageradas"), 34, mapa.TEXTO, False),
        (335, ficha.get("fuente", ""), 27, "#C9D1E3", False),
    ]:
        mapa.texto(ax, mapa.ANCHO / 2, yy, cadena, px, color=color, negrita=negrita, ha="center",
                   va="center", zorder=20)
    izq, der = ficha.get("extremos", ["", ""])
    # Los nombres de los extremos, más altos que las etiquetas de los tramos (no se pisan)
    mapa.texto(ax, 20, y(14) - 170, izq, 34, negrita=True, ha="left", va="center", zorder=8)
    mapa.texto(ax, mapa.ANCHO - 20, y(12) - 170, der, 34, negrita=True, ha="right", va="center", zorder=8)

    fig.canvas.draw()
    fondo = fig.canvas.copy_from_bbox(fig.bbox)

    # Lo que se mueve
    rastro_brillo = ax.add_line(Line2D([], [], color=mapa.AMARILLO, linewidth=mapa.pt(20), alpha=0.3,
                                       solid_capstyle="round", zorder=6, animated=True))
    rastro = ax.add_line(Line2D([], [], color=mapa.AMARILLO, linewidth=mapa.pt(7), solid_capstyle="round",
                                zorder=7, animated=True))
    coche = ax.add_line(Line2D([], [], marker="o", markersize=mapa.pt(28), color=mapa.AMARILLO,
                               markeredgecolor="white", markeredgewidth=mapa.pt(4), zorder=8, animated=True))
    # El agua otra vez, semitransparente, por encima del coche: al entrar en el túnel se hunde
    agua = ax.add_patch(Rectangle((0, MAR_Y), mapa.ANCHO, FONDO_Y - MAR_Y + 300, facecolor=AGUA, alpha=0.62,
                                  zorder=9, animated=True))
    lecho = ax.add_patch(Rectangle((0, FONDO_Y), mapa.ANCHO, mapa.ALTO - FONDO_Y, facecolor=LECHO,
                                   alpha=0.55, zorder=10, animated=True))
    # El tubo del túnel, por encima del agua (si no, el agua lo taparía)
    tubo = ax.add_patch(FancyBboxPatch((tunel[0], y(-17) - 22), tunel[1] - tunel[0], 44,
                                       boxstyle="round,pad=0,rounding_size=20", facecolor="none",
                                       edgecolor="white", linewidth=mapa.pt(2.5), alpha=0.6, zorder=11,
                                       animated=True)) if tunel else None
    textos = [(km, mapa.texto(ax, xx, yy, cadena, 38, color=mapa.AMARILLO if tipo == "tunel" else mapa.TEXTO,
                              negrita=True, ha="center", va="center", zorder=12, animated=True))
              for cadena, xx, yy, km, tipo in etiquetas]
    avion = mapa.texto(ax, 0, 0, "✈", 90, ha="center", va="center", zorder=13, animated=True) \
        if ficha.get("avion") else None

    # Avance del coche: km recorridos según el tiempo (más despacio en el túnel)
    pesos, tramos_km, k = [], [], 0.0
    for t in tramos:
        pesos.append(t["km"] * (LENTO_TUNEL if t["tipo"] == "tunel" else 1))
        tramos_km.append((k, k + t["km"]))
        k += t["km"]

    def km_en(f):
        objetivo = f * sum(pesos)
        for peso, (a, b) in zip(pesos, tramos_km):
            if objetivo <= peso:
                return a + (b - a) * objetivo / peso
            objetivo -= peso
        return total_km

    def hasta(km):
        """Los puntos del camino hasta ese km, y el punto donde está el coche."""
        hechos = [puntos[0]]
        for (k0, m0), (k1, m1), p1 in zip(camino, camino[1:], puntos[1:]):
            if km >= k1:
                hechos.append(p1)
                continue
            if km > k0:
                f = (km - k0) / (k1 - k0)
                hechos.append((x(km), y(m0 + (m1 - m0) * f)))
            break
        return hechos

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
        f = suave((t - VIAJE[0]) / (VIAJE[1] - VIAJE[0]))
        km = km_en(f) if f > 0 else camino[0][0]      # antes de salir, en tierra
        hechos = hasta(km) if f > 0 else [puntos[0]]
        xs, ys = zip(*hechos)
        visibles = []
        if len(hechos) > 1:
            rastro.set_data(xs, ys)
            rastro_brillo.set_data(xs, ys)
            visibles += [rastro_brillo, rastro]
        coche.set_data([xs[-1]], [ys[-1]])
        visibles += [coche, agua, lecho] + ([tubo] if tubo else [])
        for km0, texto in textos:
            alfa = suave((km - km0) / 0.8) if f > 0 else 0
            if alfa > 0:
                texto.set_alpha(alfa)
                visibles.append(texto)
        if avion is not None and t > 0.6:
            # Baja hacia el lado del túnel (el del aeropuerto), lejos de las torres
            g = (t - 0.6) / 0.4
            avion.set_position((x(total_km * 0.45) + g * (mapa.ANCHO + 120 - x(total_km * 0.45)), 640 + g * 260))
            avion.set_rotation(-18)
            visibles.append(avion)
        for artista in sorted(visibles, key=lambda a: a.get_zorder()):
            ax.draw_artist(artista)
        ffmpeg.stdin.write(bytes(fig.canvas.buffer_rgba()))
    ffmpeg.stdin.close()
    if ffmpeg.wait() != 0:
        raise RuntimeError("FFmpeg no ha podido crear el vídeo de la animación")
    # Es un dibujo propio, hecho con medidas públicas: no hay que citar a nadie
    fuentes = ficha.get("fuentes", [])
    return {"fotogramas": total, "fuentes": fuentes, "fuente": "Esquema propio (scripts/animar.py)",
            "url": fuentes[0] if fuentes else "", "licencia": "Obra propia (sin restricciones)"}


def altura(camino, km):
    """Metros de la calzada en ese km (interpolando entre los puntos del camino)."""
    for (k0, m0), (k1, m1) in zip(camino, camino[1:]):
        if k0 <= km <= k1:
            return m0 + (m1 - m0) * (km - k0) / (k1 - k0) if k1 > k0 else m1
    return camino[-1][1]
