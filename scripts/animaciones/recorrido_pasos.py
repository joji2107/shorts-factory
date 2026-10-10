"""Animación de un proceso paso a paso (021, el voto por correo): una barra con los pasos
numerados que se van marcando, una tarjeta por paso (icono dibujado, nombre, qué pasa y un
recuadro amarillo con el control que se aplica), un resumen con todos los controles juntos (la
recompensa) y, si la ficha los trae, casos reales con su fuente.

Cada paso dura "segundos_paso" (5 s): en el guion, cada tramo se ancla con [plano <nombre> N 4]
a la frase que lo explica (N = 0, 5, 10...), así sale cuando se dice aunque se lea más rápido o
más lento; el segundo que sobra de cada tramo es la tarjeta quieta, por si el plano se alarga.

Ficha:
  "titulo", "subtitulo", "nota" (una línea, p. ej. dónde mirar los plazos), "fuente",
  "pasos": [{"titulo", "texto", "control", "icono": dni|censo|sobre|enviar|candado|urna}],
  "resumen": {"titulo", "items": [...], "segundos": 8},
  "casos": {"titulo", "segundos": 7, "fuente", "lista": [{"titulo", "lineas": [...], "destacado": true}]}

Los segmentos van seguidos: pasos (6 x 5 s), resumen y casos. Todo queda entre la cabecera y
la zona de los subtítulos (por encima de 1250 px).
"""
import subprocess
import textwrap

from matplotlib.patches import Arc, Circle, FancyBboxPatch, Polygon, Rectangle

from . import mapa

FPS = 30
COLCHON = 0.5
ENTRADA = 0.5          # segundos que tarda en aparecer cada cosa
BARRA_Y = 450          # la barra de pasos
ICONO = (540, 655)     # centro del icono de cada paso
GRIS = "#C9D1E3"


def suave(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def caja(ax, x, y, ancho, alto, color, borde="none", alfa=1.0, z=5):
    return ax.add_patch(FancyBboxPatch((x - ancho / 2, y - alto / 2), ancho, alto,
                                       boxstyle="round,pad=0,rounding_size=22", facecolor=color,
                                       edgecolor=borde, linewidth=mapa.pt(4), alpha=alfa, zorder=z))


def icono(ax, nombre):
    """Las piezas de un icono sencillo, dibujado con formas (sin fuentes de iconos)."""
    cx, cy = ICONO
    linea = {"facecolor": "none", "edgecolor": "white", "linewidth": mapa.pt(8), "zorder": 6}
    amarillo = {"facecolor": mapa.AMARILLO, "edgecolor": "none", "zorder": 6}
    p = []
    if nombre == "dni":                     # carné: tarjeta, cara y líneas
        p.append(caja(ax, cx, cy, 300, 190, "none", "white", z=6))
        p.append(ax.add_patch(Circle((cx - 80, cy - 10), 42, **amarillo)))
        p += [ax.add_patch(Rectangle((cx - 10, cy - 50 + 32 * i), 120 - 30 * i, 14, facecolor="white",
                                     zorder=6)) for i in range(3)]
    elif nombre == "censo":                 # lista con una línea marcada
        p.append(caja(ax, cx, cy, 220, 270, "none", "white", z=6))
        for i in range(4):
            y = cy - 90 + 55 * i
            p.append(ax.add_patch(Rectangle((cx - 40, y - 7), 110, 14, facecolor="white", zorder=6)))
            p.append(ax.add_patch(Circle((cx - 70, y), 13, **(amarillo if i == 1 else
                                                               {"facecolor": "white", "zorder": 6}))))
    elif nombre in ("sobre", "enviar"):     # sobre (con flecha si se envía)
        dx = -40 if nombre == "enviar" else 0
        p.append(ax.add_patch(Rectangle((cx - 150 + dx, cy - 95), 300, 190, **linea)))
        p.append(ax.add_patch(Polygon([(cx - 150 + dx, cy - 95), (cx + dx, cy + 10), (cx + 150 + dx, cy - 95)],
                                      closed=False, **linea)))
        if nombre == "enviar":
            p.append(ax.add_patch(Polygon([(cx + 135, cy - 45), (cx + 215, cy), (cx + 135, cy + 45)],
                                          closed=True, **amarillo)))
            p.append(ax.add_patch(Rectangle((cx + 95, cy - 14), 50, 28, **amarillo)))
    elif nombre == "candado":               # custodia: candado
        p.append(caja(ax, cx, cy + 40, 230, 170, "none", "white", z=6))
        p.append(ax.add_patch(Arc((cx, cy - 45), 150, 170, theta1=180, theta2=360, color="white",
                                  linewidth=mapa.pt(10), zorder=6)))
        p.append(ax.add_patch(Circle((cx, cy + 30), 22, **amarillo)))
        p.append(ax.add_patch(Rectangle((cx - 8, cy + 30), 16, 50, **amarillo)))
    elif nombre == "urna":                  # urna con un sobre entrando por la ranura
        p.append(ax.add_patch(Polygon([(cx - 150, cy - 40), (cx + 150, cy - 40), (cx + 125, cy + 130),
                                       (cx - 125, cy + 130)], closed=True, **linea)))
        p.append(ax.add_patch(Rectangle((cx - 70, cy - 50), 140, 16, facecolor="white", zorder=6)))
        p.append(ax.add_patch(Rectangle((cx - 55, cy - 150), 110, 95, facecolor=mapa.AMARILLO,
                                        edgecolor=mapa.MAR, linewidth=mapa.pt(4), zorder=5)))
    return p


def crear(ficha, salida, cache):
    pasos = ficha["pasos"]
    por_paso = float(ficha.get("segundos_paso", 5))
    resumen = ficha.get("resumen")
    casos = ficha.get("casos")
    tramos = [("paso", i, i * por_paso, por_paso) for i in range(len(pasos))]
    t = len(pasos) * por_paso
    if resumen:
        tramos.append(("resumen", 0, t, float(resumen.get("segundos", 8))))
        t += tramos[-1][3]
    if casos:
        tramos.append(("casos", 0, t, float(casos.get("segundos", 7))))
        t += tramos[-1][3]
    segundos = t

    fig, ax = mapa.lienzo((0, mapa.ANCHO, mapa.ALTO, 0))
    # Cabecera fija
    for y, cadena, px, color, negrita in [
        (140, ficha.get("titulo", "").upper(), 66, mapa.TEXTO, True),
        (215, ficha.get("subtitulo", "").upper(), 36, mapa.AMARILLO, True),
        (268, ficha.get("nota", ""), 32, mapa.TEXTO, False),
        (318, ficha.get("fuente", ""), 26, GRIS, False),
    ]:
        mapa.texto(ax, mapa.ANCHO / 2, y, cadena, px, color=color, negrita=negrita, ha="center", va="center", zorder=8)

    # Barra de pasos: círculos numerados unidos por una línea
    xs = [140 + i * (800 / max(1, len(pasos) - 1)) for i in range(len(pasos))]
    ax.plot([xs[0], xs[-1]], [BARRA_Y, BARRA_Y], color=GRIS, linewidth=mapa.pt(4), alpha=0.5, zorder=2)
    circulos, numeros, marcas = [], [], []
    for i, x in enumerate(xs):
        circulos.append(ax.add_patch(Circle((x, BARRA_Y), 34, facecolor=mapa.MAR, edgecolor=GRIS,
                                            linewidth=mapa.pt(4), zorder=3)))
        numeros.append(mapa.texto(ax, x, BARRA_Y + 2, str(i + 1), 34, negrita=True, ha="center", va="center", zorder=4))
        marcas.append(ax.text(x, BARRA_Y + 2, "✔", fontsize=mapa.pt(38), color=mapa.MAR, family=mapa.FUENTE,
                              ha="center", va="center", zorder=4, weight="bold"))

    # Tarjetas de los pasos
    tarjetas = []
    for i, paso in enumerate(pasos):
        piezas = icono(ax, paso.get("icono", "sobre"))
        piezas.append(mapa.texto(ax, 540, 880, f"{i + 1} · {paso['titulo'].upper()}", 56, negrita=True,
                                 ha="center", va="center", zorder=7))
        piezas.append(mapa.texto(ax, 540, 970, textwrap.fill(paso["texto"], 34), 36, ha="center", va="center",
                                 zorder=7, linespacing=1.25))
        piezas.append(caja(ax, 540, 1140, 940, 150, mapa.AMARILLO, z=6))
        piezas.append(ax.text(540, 1140, textwrap.fill("CONTROL: " + paso["control"], 36),
                              fontsize=mapa.pt(38), color=mapa.MAR, family=mapa.FUENTE, weight="bold",
                              ha="center", va="center", zorder=7, linespacing=1.2))
        tarjetas.append(piezas)

    # Resumen: todos los controles juntos
    lista_resumen = []
    if resumen:
        titulo_r = mapa.texto(ax, 540, 560, resumen["titulo"].upper(), 76, color=mapa.AMARILLO, negrita=True,
                              ha="center", va="center", zorder=7)
        for k, item in enumerate(resumen["items"]):
            y = 680 + k * 92
            lista_resumen.append([
                ax.text(150, y, "✔", fontsize=mapa.pt(50), color=mapa.AMARILLO, family=mapa.FUENTE,
                        weight="bold", ha="center", va="center", zorder=7),
                mapa.texto(ax, 210, y, item, 42, negrita=True, ha="left", va="center", zorder=7),
            ])
    # Casos reales
    piezas_casos = []
    if casos:
        piezas_casos.append(mapa.texto(ax, 540, 545, casos["titulo"].upper(), 60, color=mapa.AMARILLO,
                                       negrita=True, ha="center", va="center", zorder=7))
        y = 640
        for caso in casos["lista"]:
            alto = 80 + 52 * len(caso["lineas"])
            grupo = [caja(ax, 540, y + alto / 2, 960, alto, "#22335A" if caso.get("destacado") else "none",
                          mapa.AMARILLO if caso.get("destacado") else GRIS, z=5),
                     mapa.texto(ax, 90, y + 45, caso["titulo"].upper(), 40, color=mapa.AMARILLO, negrita=True,
                                ha="left", va="center", zorder=7)]
            for k, lin in enumerate(caso["lineas"]):
                grupo.append(mapa.texto(ax, 90, y + 100 + 52 * k, lin, 34, ha="left", va="center", zorder=7))
            piezas_casos.append(grupo)
            y += alto + 30
        piezas_casos.append(mapa.texto(ax, 540, min(y + 10, 1225), casos.get("fuente", ""), 26, color=GRIS,
                                       ha="center", va="center", zorder=7))

    def mostrar(piezas, alfa):
        for p in piezas:
            if isinstance(p, list):
                mostrar(p, alfa)
                continue
            p.set_visible(alfa > 0)
            p.set_alpha(alfa)

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
        s = min(segundos, n / FPS) if n < animados else segundos - 1e-6
        tipo, indice, inicio, largo = next(tr for tr in tramos if tr[2] <= s < tr[2] + tr[3])
        dentro = s - inicio
        aparecer = suave(dentro / ENTRADA)

        # Barra: hechos en amarillo con ✔; el actual con borde amarillo; en el resumen y los casos, todos hechos
        actual = indice if tipo == "paso" else len(pasos)
        for i in range(len(pasos)):
            hecho = i < actual
            circulos[i].set_facecolor(mapa.AMARILLO if hecho else mapa.MAR)
            circulos[i].set_edgecolor(mapa.AMARILLO if i <= actual else GRIS)
            numeros[i].set_visible(not hecho)
            marcas[i].set_visible(hecho)
        for i, piezas in enumerate(tarjetas):
            mostrar(piezas, aparecer if (tipo == "paso" and i == indice) else 0)
        if resumen:
            mostrar([titulo_r], aparecer if tipo == "resumen" else 0)
            for k, fila in enumerate(lista_resumen):
                mostrar(fila, suave((dentro - 0.4 - 0.45 * k) / 0.35) if tipo == "resumen" else 0)
        if casos:
            for k, grupo in enumerate(piezas_casos):
                mostrar(grupo if isinstance(grupo, list) else [grupo],
                        suave((dentro - 0.5 * k) / ENTRADA) if tipo == "casos" else 0)

        fig.canvas.draw()
        ffmpeg.stdin.write(bytes(fig.canvas.buffer_rgba()))
    ffmpeg.stdin.close()
    if ffmpeg.wait() != 0:
        raise RuntimeError("FFmpeg no ha podido crear el vídeo de la animación")
    fuentes = ficha.get("fuentes", [])
    return {"fotogramas": total, "tramos": [(tp, round(ini, 2), lg) for tp, _, ini, lg in tramos],
            "fuentes": fuentes, "fuente": "Esquema propio (scripts/animar.py)",
            "url": fuentes[0] if fuentes else "", "licencia": "Obra propia (sin restricciones)"}
