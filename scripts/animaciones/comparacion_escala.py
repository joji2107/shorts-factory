"""Animación de comparación de escala: dos o más objetos dibujados a la misma escala, con sus
cifras, que aparecen uno tras otro. Plantilla general: cada short solo le da los objetos.

Ficha (shorts/<short>/animaciones/<nombre>.json):
  "orientacion": "vertical" (alturas y profundidades) u "horizontal" (longitudes)
  "objetos": [{"ref": "torre_eiffel"}, {"nombre": "...", "medida_m": 1000, "forma": "rascacielos",
              "destacado": true, "texto": "1 km"}]
  "titulo", "subtitulo", "nota", "fuente", "segundos" (8), "segundos_objeto" (opcional, para
  anclar cada objeto a su frase), "final" (texto) o "proporcion": true (× N del destacado)

Las referencias ("ref") están en config/referencias_escala.json, con su medida comprobada con dos
fuentes. Una profundidad es una medida hacia abajo (dimension "profundidad" o medida negativa).

Solo la medida está a escala (la altura en vertical, la longitud en horizontal): la silueta es
esquemática y su ancho, orientativo, y la pantalla lo dice. Un objeto que a escala mediría menos
de MINIMO px se dibuja con MINIMO px y una flecha que avisa de que está «casi invisible».
"""
import json
import math
import textwrap
from pathlib import Path

from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle

from . import mapa

FPS = 30
COLCHON = 0.5
REFERENCIAS = Path(__file__).resolve().parents[2] / "config" / "referencias_escala.json"
ARRIBA = 430          # nada por encima (la cabecera)
ABAJO = 1235          # nada por debajo (los subtítulos, a 560 px del borde)
SITIO_ETIQUETA = 150  # alto que se reserva para el nombre y la cifra (hasta 4 líneas) de cada objeto
MINIMO = 6            # px que mide como mínimo un objeto diminuto
CRECER = 0.8          # segundos que tarda en crecer cada objeto
GRIS = "#C9D1E3"
AGUA = "#1E4A86"
CESPED = "#2E7D4F"

# Siluetas, en una caja unidad: en vertical, x de -0,5 a 0,5 (ancho) e y de 0 a 1 (altura, desde
# el suelo); en horizontal, x de 0 a 1 (longitud) e y de -0,5 a 0,5 (grosor). "aspecto" es el
# ancho/alto aproximado de la silueta en vertical (en horizontal, el grosor es fijo).
FORMAS = {
    "persona": {"aspecto": 0.3, "piezas": [
        [(-0.3, 0), (0.3, 0), (0.42, 0.78), (-0.42, 0.78)],
        [(0.3 * math.cos(a * math.pi / 4), 0.89 + 0.11 * math.sin(a * math.pi / 4)) for a in range(8)]]},
    "eiffel": {"aspecto": 0.38, "piezas": [[(-0.5, 0), (-0.3, 0), (-0.18, 0.17), (0.18, 0.17), (0.3, 0), (0.5, 0),
                                             (0.3, 0.27), (0.12, 0.6), (0.04, 0.93), (0, 1), (-0.04, 0.93),
                                             (-0.12, 0.6), (-0.3, 0.27)]]},
    "piramide": {"aspecto": 1.6, "piezas": [[(-0.5, 0), (0.5, 0), (0, 1)]]},
    "rascacielos": {"aspecto": 0.16, "piezas": [[(-0.5, 0), (0.5, 0), (0.38, 0.35), (0.22, 0.6), (0.12, 0.8),
                                                  (0.04, 0.92), (0, 1), (-0.04, 0.92), (-0.12, 0.8), (-0.22, 0.6),
                                                  (-0.38, 0.35)]]},
    "torre": {"aspecto": 0.35, "piezas": [[(-0.5, 0), (0.5, 0), (0.5, 0.55), (0.3, 0.75), (0.08, 0.95), (0, 1),
                                            (-0.08, 0.95), (-0.3, 0.75), (-0.5, 0.55)]]},
    "estatua": {"aspecto": 0.35, "piezas": [[(-0.5, 0), (0.5, 0), (0.35, 0.5), (-0.35, 0.5)],
                                             [(-0.2, 0.5), (0.2, 0.5), (0.13, 0.88), (-0.13, 0.88)],
                                             [(0.08, 0.84), (0.16, 0.84), (0.24, 1.0), (0.16, 1.0)]]},
    "montana": {"aspecto": 1.5, "piezas": [[(-0.5, 0), (-0.22, 0.55), (-0.12, 0.5), (0, 1), (0.14, 0.7),
                                             (0.24, 0.76), (0.5, 0)]]},
    "fosa": {"aspecto": 1.2, "piezas": [[(-0.5, 0), (-0.22, 0.4), (-0.06, 1), (0.06, 1), (0.22, 0.5), (0.5, 0)]]},
    "barra": {"aspecto": 0.3, "piezas": [[(-0.5, 0), (0.5, 0), (0.5, 1), (-0.5, 1)]]},
}
FORMAS_H = {
    "avion": [[(0, -0.12), (0.9, -0.12), (1, 0), (0.9, 0.12), (0.04, 0.12)],
              [(0, 0.12), (0.1, 0.12), (0.02, 0.5)], [(0.4, -0.05), (0.56, -0.05), (0.44, -0.5)]],
    "barco": [[(0, 0.1), (1, 0.1), (0.94, -0.42), (0.05, -0.42)], [(0.22, 0.1), (0.76, 0.1), (0.73, 0.32), (0.25, 0.32)],
              [(0.32, 0.32), (0.37, 0.32), (0.37, 0.5), (0.32, 0.5)], [(0.52, 0.32), (0.57, 0.32), (0.57, 0.5), (0.52, 0.5)]],
    "campo": [[(0, -0.5), (1, -0.5), (1, 0.5), (0, 0.5)]],
    "puente": [[(0, -0.08), (1, -0.08), (1, 0.06), (0, 0.06)], [(0.3, -0.5), (0.33, -0.5), (0.33, 0.5), (0.3, 0.5)],
               [(0.67, -0.5), (0.7, -0.5), (0.7, 0.5), (0.67, 0.5)]],
    "barra": [[(0, -0.3), (1, -0.3), (1, 0.3), (0, 0.3)]],
}


def suave(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def cifra(metros):
    """La medida en metros escrita en español: 8.849 m, 172,5 m, 72,7 m, 1,75 m."""
    m = abs(metros)
    if m >= 1000:
        texto = f"{round(m):,}".replace(",", ".")
    elif m >= 100:
        texto = f"{m:.1f}".replace(".", ",") if round(m, 1) != round(m) else f"{round(m)}"
    elif m >= 10:
        texto = f"{m:.1f}".replace(".", ",") if round(m, 1) != round(m) else f"{round(m)}"
    else:
        texto = f"{m:.2f}".replace(".", ",").rstrip("0").rstrip(",")
    return f"{texto} m"


def objetos_de(ficha):
    """Los objetos de la ficha con las referencias resueltas: nombre, medida (negativa si es una
    profundidad), texto, forma, destacado y fuentes."""
    referencias = json.loads(REFERENCIAS.read_text(encoding="utf-8"))
    lista = []
    for o in ficha["objetos"]:
        if "ref" in o:
            if o["ref"] not in referencias or o["ref"].startswith("_"):
                validas = ", ".join(k for k in referencias if not k.startswith("_"))
                raise RuntimeError(f"Referencia desconocida: {o['ref']!r} (hay: {validas})")
            base = dict(referencias[o["ref"]])
            base.update({k: v for k, v in o.items() if k != "ref"})
            o = base
        medida = float(o["medida_m"])
        if o.get("dimension") == "profundidad" and medida > 0:
            medida = -medida
        lista.append({"nombre": o["nombre"], "medida": medida, "texto": o.get("texto") or cifra(medida),
                      "forma": o.get("forma", "barra"), "destacado": bool(o.get("destacado")),
                      "fuentes": o.get("fuentes", [])})
    if len(lista) < 2:
        raise RuntimeError("Una comparación necesita al menos dos objetos")
    return lista


def crear(ficha, salida, cache):
    objetos = objetos_de(ficha)
    vertical = ficha.get("orientacion", "vertical") == "vertical"
    segundos = float(ficha.get("segundos", 8))
    final = ficha.get("final")
    if not final and ficha.get("proporcion"):
        destacado = next((o for o in objetos if o["destacado"]), objetos[-1])
        otros = [abs(o["medida"]) for o in objetos if o is not destacado]
        veces = abs(destacado["medida"]) / max(otros)
        final = f"× {veces:.1f}".replace(".", ",")
    n = len(objetos)
    por_objeto = float(ficha.get("segundos_objeto", (segundos - (1.6 if final else 0.6)) / n))
    if por_objeto * n > segundos:
        raise RuntimeError(f"{n} objetos de {por_objeto:g} s no caben en {segundos:g} s")
    abajo = ABAJO - (110 if final else 0)

    fig, ax = mapa.lienzo((0, mapa.ANCHO, mapa.ALTO, 0))
    for y, cadena, px, color, negrita in [
        (140, ficha.get("titulo", "").upper(), 66, mapa.TEXTO, True),
        (215, ficha.get("subtitulo", "A la misma escala").upper(), 36, mapa.AMARILLO, True),
        (268, ficha.get("nota", "Siluetas esquemáticas; medidas a escala"), 32, mapa.TEXTO, False),
        (318, ficha.get("fuente", "Fuentes de las medidas: en la descripción"), 26, GRIS, False),
    ]:
        mapa.texto(ax, mapa.ANCHO / 2, y, cadena, px, color=color, negrita=negrita, ha="center", va="center", zorder=8)

    piezas, etiquetas = [], []          # por objeto: (patches, puntos base) y textos/flechas
    if vertical:
        alto_max = max([o["medida"] for o in objetos if o["medida"] > 0] + [0])
        hondo_max = max([-o["medida"] for o in objetos if o["medida"] < 0] + [0])
        reservas = SITIO_ETIQUETA * ((alto_max > 0) + (hondo_max > 0))
        escala = (abajo - ARRIBA - reservas) / (alto_max + hondo_max)          # px por metro
        suelo = ARRIBA + (SITIO_ETIQUETA if alto_max else 0) + alto_max * escala
        if hondo_max:
            ax.add_patch(Rectangle((0, suelo), mapa.ANCHO, abajo - suelo, facecolor=AGUA, alpha=0.55, zorder=1))
        ax.plot([40, mapa.ANCHO - 40], [suelo, suelo], color=GRIS, linewidth=mapa.pt(3), zorder=2)
        columna = (mapa.ANCHO - 120) / n
        for i, o in enumerate(objetos):
            cx = 60 + columna * (i + 0.5)
            alto = o["medida"] * escala                    # negativo hacia abajo
            diminuto = abs(alto) < MINIMO
            if diminuto:
                alto = MINIMO if alto >= 0 else -MINIMO
            forma = FORMAS.get(o["forma"], FORMAS["barra"])
            ancho = max(14, min(columna * 0.8, forma["aspecto"] * abs(alto)))
            color = mapa.AMARILLO if o["destacado"] else ("#E6EAF2" if o["forma"] != "fosa" else "#0B1428")
            patches = []
            for pieza in forma["piezas"]:
                puntos = [(cx + px * ancho, py) for px, py in pieza]
                patches.append((ax.add_patch(Polygon([(x, suelo) for x, _ in puntos], closed=True,
                                                     facecolor=color, edgecolor="white" if o["forma"] == "fosa" else "none",
                                                     linewidth=mapa.pt(2), zorder=4, animated=True)), puntos))
            piezas.append((patches, alto))
            # Nombre y cifra: encima de lo que sube, debajo de lo que baja
            ancho_txt = max(8, int(columna / 19))
            nombre = textwrap.fill(o["nombre"], ancho_txt)
            arriba_del = suelo - alto                    # la punta: arriba si sube, abajo si baja
            if diminuto:
                arriba_del = suelo - 160 if alto > 0 else suelo + 160
            signo = -1 if alto > 0 else 1
            # La cifra también se parte si no cabe en la columna («más de / 1.000 m»)
            valor = textwrap.fill(o["texto"], max(6, int(columna / 24)))
            lineas_valor = valor.count("\n")
            y_cifra = arriba_del + signo * (28 + 22 * lineas_valor)
            y_nombre = y_cifra + signo * (34 + 22 * lineas_valor + 18 * nombre.count("\n"))
            textos = [mapa.texto(ax, cx, y_cifra, valor, 40, color=mapa.AMARILLO if o["destacado"] else mapa.TEXTO,
                                 negrita=True, ha="center", va="center", zorder=7, animated=True),
                      mapa.texto(ax, cx, y_nombre, nombre, 30, ha="center", va="center", zorder=7, animated=True,
                                 linespacing=1.1)]
            if diminuto:
                textos.append(ax.add_line(Line2D([cx, cx], [arriba_del - signo * 4, suelo - alto + signo * 10],
                                                 color=mapa.AMARILLO, linewidth=mapa.pt(3), zorder=6, animated=True)))
                textos.append(mapa.texto(ax, cx + 12, (arriba_del + suelo) / 2, "a escala,\ncasi\ninvisible", 21,
                                         color=GRIS, ha="left", va="center", zorder=7, animated=True))
            etiquetas.append(textos)
    else:
        largo_max = max(abs(o["medida"]) for o in objetos)
        x0, x1 = 80, 1000
        escala = (x1 - x0) / largo_max
        filas = [ARRIBA + 90 + (abajo - ARRIBA - 140) * (i + 0.5) / n for i in range(n)]
        grueso = min(70, (abajo - ARRIBA - 140) / n * 0.45)
        ax.plot([x0, x0], [ARRIBA + 40, abajo - 20], color=GRIS, linewidth=mapa.pt(3), zorder=2)   # origen común
        for o, y in zip(objetos, filas):
            largo = abs(o["medida"]) * escala
            diminuto = largo < MINIMO
            largo = max(largo, MINIMO)
            color = mapa.AMARILLO if o["destacado"] else (CESPED if o["forma"] == "campo" else "#E6EAF2")
            patches = []
            for pieza in FORMAS_H.get(o["forma"], FORMAS_H["barra"]):
                puntos = [(px, y - py * grueso) for px, py in pieza]      # px de 0 a 1: se multiplica al crecer
                patches.append((ax.add_patch(Polygon([(x0, yy) for _, yy in puntos], closed=True, facecolor=color,
                                                     edgecolor="none", zorder=4, animated=True)), puntos))
            piezas.append((patches, largo))
            texto = f"{o['nombre']} · {o['texto']}" + ("  (a escala, casi invisible)" if diminuto else "")
            etiquetas.append([mapa.texto(ax, x0, y - grueso / 2 - 30, texto, 36,
                                         color=mapa.AMARILLO if o["destacado"] else mapa.TEXTO, negrita=True,
                                         ha="left", va="center", zorder=7, animated=True)])

    cartel = None
    if final:
        caja = ax.add_patch(FancyBboxPatch((140, ABAJO - 95), 800, 90, boxstyle="round,pad=0,rounding_size=22",
                                           facecolor=mapa.AMARILLO, edgecolor="none", zorder=8, animated=True))
        # La letra se ajusta para que el texto quepa en el cartel (unos 0,58 px por px de letra)
        letras = ax.text(540, ABAJO - 50, final, fontsize=mapa.pt(min(52, 760 / (0.58 * max(1, len(final))))), color=mapa.MAR, family=mapa.FUENTE,
                         weight="bold", ha="center", va="center", zorder=9, animated=True)
        cartel = [caja, letras]

    fig.canvas.draw()
    fondo = fig.canvas.copy_from_bbox(fig.bbox)
    animados = round(segundos * FPS)

    def fotograma(n_fot):
        s = min(n_fot, animados) / FPS
        fig.canvas.restore_region(fondo)
        visibles = []
        for i, ((patches, medida), textos) in enumerate(zip(piezas, etiquetas)):
            inicio = i * por_objeto
            g = suave((s - inicio) / CRECER)
            if g <= 0:
                continue
            for patch, puntos in patches:
                if vertical:
                    patch.set_xy([(x, suelo - py * medida * g) for x, py in puntos])
                else:
                    patch.set_xy([(x0 + px * medida * g, yy) for px, yy in puntos])
                visibles.append(patch)
            alfa = suave((s - inicio - CRECER * 0.75) / 0.4)
            for t in textos:
                if alfa > 0:
                    t.set_alpha(alfa)
                    visibles.append(t)
        if cartel and s >= n * por_objeto:
            alfa = suave((s - n * por_objeto) / 0.4)
            for t in cartel:
                t.set_alpha(alfa)
                visibles.append(t)
        for artista in sorted(visibles, key=lambda a: a.get_zorder()):
            ax.draw_artist(artista)

    total = round((segundos + COLCHON) * FPS)
    mapa.grabar(fig, total, salida, fotograma)
    fuentes = sorted({f for o in objetos for f in o["fuentes"]})
    return {"fotogramas": total, "fuentes": fuentes, "fuente": "Esquema propio (scripts/animar.py)",
            "url": fuentes[0] if fuentes else "", "licencia": "Obra propia (sin restricciones)"}
