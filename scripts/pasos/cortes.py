"""Genera la lista de cortes (EDL) automáticamente, cortando en las pausas de la voz.

Versión 2:
- En cada tramo elige la MEJOR pausa (la más larga, con prioridad a los finales
  de frase), en vez de la primera que encuentra.
- Si no hay pausas, corta entre dos palabras, nunca a mitad de una.
- Ningún corte supera la duración máxima, tampoco el último.
- Reparte los clips sin repetir el mismo plano mientras quede material sin usar.

Versión 3:
- Elige automáticamente dónde poner los efectos de sonido: en los cortes que
  coinciden con las pausas más marcadas del guion (cambios de bloque).

Versión 4:
- El reparto (repartir) no imprime nada, para poder simularlo desde el servidor MCP.
- Cada clip empieza en un punto al azar (desplazar), no siempre en el segundo 0.

Versión 5:
- Con video.buscar_destellos, cada corte se mueve para que un destello (un rayo) caiga
  al principio del plano: en las tormentas grabadas de verdad casi todo el tiempo está
  oscuro y, con un punto al azar, muchos cortes salían sin rayo.
- Los cortes llegan hasta la cola después de la última palabra (o tras_ultima_palabra
  en un bucle), como el render: no al final de la grabación.

Versión 6 (fábrica 2.0, con video.ritmo.activo):
- Los planos protagonistas del guion ([plano clip desde largo]) van primero, en su sitio:
  empiezan justo antes de su palabra (o con el respiro que los precede), desde el segundo
  del clip que eligió la skill, y pueden durar más que corte_max (hasta plano_max).
- Un respiro sin protagonista es un tramo de un solo plano: nada de cortes rápidos en silencio.
- El resto es relleno: cortes rápidos (relleno_min-relleno_max) con los demás clips. El
  contraste entre los cortes rápidos y los planos largos es lo que da ritmo.
"""
import json
import random
import re
import statistics

from .clips import duracion_clip, es_foto, ruta_clip
from .marcas import en_la_transcripcion, planos_del_guion
from .subtitulos import palabras_del_guion
from .utilidades import duracion, ejecutar

FPS = 30
MARGEN = 0.5        # segundos que se saltan entre dos usos de un clip, para no repetir plano
ANTICIPO = 0.1     # segundos que un plano protagonista empieza antes de su palabra
PLANO_MIN = 2.0     # segundos que tiene que conservar un plano protagonista acortado para no pisar otro
FIN_FRASE = (".", "?", "!")
PAUSA_SUAVE = (",", ";", ":")


def a_fotograma(t):
    """Redondea un tiempo al fotograma más cercano, para que los cortes no acumulen desfase."""
    return round(t * FPS) / FPS


def huecos(palabras, c):
    """Devuelve dos listas de momentos posibles de corte:
    - pausas: (momento, puntuación) en los huecos reales entre palabras.
    - fronteras: el punto entre cada par de palabras, para cortes forzados.
    """
    pausas, fronteras = [], []
    for actual, siguiente in zip(palabras, palabras[1:]):
        momento = (actual["fin"] + siguiente["inicio"]) / 2
        fronteras.append(momento)
        hueco = siguiente["inicio"] - actual["fin"]
        if hueco < c["pausa_corte"]:
            continue
        puntuacion = hueco
        if actual["palabra"].endswith(FIN_FRASE):
            puntuacion += 1.0      # final de frase: el mejor sitio para cortar
        elif actual["palabra"].endswith(PAUSA_SUAVE):
            puntuacion += 0.3      # coma o similar: buen sitio, pero menos
        pausas.append((momento, puntuacion))
    return pausas, fronteras


def puntos_de_corte(palabras, total, c, desde=0.0):
    """Elige los momentos de corte tramo a tramo, de 'desde' a 'total'."""
    pausas, fronteras = huecos(palabras, c)
    puntos = [desde]
    while total - puntos[-1] > c["corte_max"]:
        ultimo = puntos[-1]
        desde = ultimo + c["corte_min"]
        # El corte no puede dejar después un trozo final más corto que el mínimo
        hasta = min(ultimo + c["corte_max"], total - c["corte_min"])

        en_ventana = [(m, p) for m, p in pausas if desde <= m <= hasta]
        if en_ventana:
            siguiente = max(en_ventana, key=lambda x: x[1])[0]
        else:
            # Sin pausas: la frontera entre palabras más tardía dentro del tramo
            posibles = [m for m in fronteras if desde <= m <= hasta]
            siguiente = max(posibles) if posibles else hasta
        puntos.append(siguiente)
    puntos.append(total)
    return [a_fotograma(p) for p in puntos]


def repartir(largos, clips, duraciones):
    """Reparte los clips por turnos, sin repetir plano mientras quede material.
    No imprime nada: devuelve la lista de cortes y los avisos, para que también
    se pueda usar desde el servidor MCP (que no admite print) para simular un short."""
    posicion = {clip: 0.0 for clip in clips}
    edl, avisos = [], []
    anterior = None
    turno = 0
    for largo in largos:
        disponibles = [cl for cl in clips if cl != anterior] or clips

        # Por turnos, el primer clip distinto del anterior al que le quede material sin usar
        elegido = None
        for k in range(len(clips)):
            clip = clips[(turno + k) % len(clips)]
            if clip in disponibles and posicion[clip] + largo <= duraciones[clip]:
                elegido = clip
                turno = (turno + k + 1) % len(clips)
                break

        if elegido is None:
            # Todos agotados: se reutiliza desde el principio el clip más largo
            elegido = max(disponibles, key=lambda cl: duraciones[cl])
            posicion[elegido] = 0.0
            avisos.append(f"material agotado, se repite {elegido} desde el principio")
        if duraciones[elegido] < largo:
            avisos.append(f"{elegido} dura menos que el corte ({largo:.1f} s)")

        edl.append((elegido, posicion[elegido], largo))
        posicion[elegido] += largo + MARGEN
        anterior = elegido
    return edl, avisos


def saltando(edl, duraciones, saltar, azar=random):
    """Reparte y desplaza sobre la parte útil de cada clip (sin sus primeros saltar[clip]
    segundos: la cartela de la NASA, por ejemplo) y después suma ese desfase a los cortes.
    Sin nada que saltar, el resultado es el de siempre. edl: los largos de los cortes."""
    utiles = {clip: max(0.0, d - saltar.get(clip, 0)) for clip, d in duraciones.items()}
    cortes, avisos = repartir(edl, list(duraciones), utiles)
    cortes = desplazar(cortes, utiles, azar)
    return [(clip, inicio + saltar.get(clip, 0), largo) for clip, inicio, largo in cortes], avisos


def asignar_clips(puntos, clips, biblioteca, segundos_imagen, saltar=None):
    """Mide los clips, los reparte entre los cortes y avisa si falta material."""
    duraciones = {clip: duracion_clip(biblioteca, clip, segundos_imagen) for clip in clips}
    largos = [b - a for a, b in zip(puntos, puntos[1:])]
    edl, avisos = saltando(largos, duraciones, saltar or {})
    for aviso in avisos:
        print(f"   AVISO: {aviso}")
    return edl


def desplazar(edl, duraciones, azar=random):
    """Mueve todos los cortes de cada clip el mismo desfase al azar, dentro de lo
    que sobra al final del clip. El reparto no cambia (ni el material que hace
    falta), pero el clip ya no empieza siempre en el segundo 0: si sale en
    varios shorts, el primer plano no se repite."""
    final = {}
    for clip, inicio, largo in edl:
        final[clip] = max(final.get(clip, 0.0), inicio + largo)
    # Hacia abajo, a fotogramas enteros: así el último corte nunca se pasa del final del clip
    desfase = {clip: int(azar.uniform(0, max(0.0, duraciones[clip] - fin)) * FPS) / FPS
               for clip, fin in final.items()}
    return [(clip, inicio + desfase[clip], largo) for clip, inicio, largo in edl]


def destellos(video):
    """Segundos en que el clip se ilumina de golpe (un rayo): fotogramas con un brillo
    medio (YAVG de signalstats, a 10 por segundo) de al menos 1,5 veces el típico del
    clip y 15 puntos más. Los que van seguidos (menos de 1 s) cuentan como uno."""
    resultado = ejecutar([
        "ffmpeg", "-hide_banner", "-i", video, "-an",
        "-vf", "scale=160:-2,fps=10,signalstats,metadata=print:key=lavfi.signalstats.YAVG",
        "-f", "null", "-",
    ])
    tiempos = [float(t) for t in re.findall(r"pts_time:([\d.]+)", resultado.stderr)]
    brillos = [float(y) for y in re.findall(r"YAVG=([\d.]+)", resultado.stderr)]
    if not brillos:
        return []
    tipico = statistics.median(brillos)
    encontrados, ultimo = [], -9.0
    for t, brillo in zip(tiempos, brillos):
        if brillo > max(tipico * 1.5, tipico + 15) and t - ultimo > 1:
            encontrados.append(t)
            ultimo = t
    return encontrados


def a_destellos(edl, biblioteca, duraciones, antes=0.4):
    """Mueve cada corte para que empiece 'antes' segundos antes de un destello de su
    clip. Cada destello se usa una vez y dos tramos de un mismo clip no se pisan (con
    MARGEN). Si un clip no tiene destellos libres, el corte se queda donde estaba (o en
    el primer hueco libre, si ahí pisaría a otro). Las fotos no tienen destellos."""
    pendientes = {}
    for clip in {clip for clip, _, _ in edl}:
        ruta = ruta_clip(biblioteca, clip)
        pendientes[clip] = [] if es_foto(ruta) else destellos(ruta)
    usados, resultado, con_rayo = {}, [], 0

    def libre(clip, inicio, largo):
        return (0 <= inicio and inicio + largo <= duraciones[clip] and
                all(inicio >= fin + MARGEN or inicio + largo + MARGEN <= ini for ini, fin in usados.get(clip, [])))

    for clip, inicio, largo in edl:
        elegido = None
        for t in pendientes[clip]:
            candidato = a_fotograma(max(0.0, t - antes))
            if libre(clip, candidato, largo):
                elegido = candidato
                pendientes[clip].remove(t)
                con_rayo += 1
                break
        if elegido is None:
            huecos_libres = (a_fotograma(x / 2) for x in range(int((duraciones[clip] - largo) * 2) + 1))
            elegido = inicio if libre(clip, inicio, largo) else next(
                (x for x in huecos_libres if libre(clip, x, largo)), inicio)
        usados.setdefault(clip, []).append((elegido, elegido + largo))
        resultado.append((clip, elegido, largo))
    print(f"   {con_rayo} de {len(edl)} cortes empiezan en un destello")
    return resultado


def tramos_fijos(palabras, guion, respiros, total, c, duracion_de):
    """Los tramos que no se cortan: planos protagonistas y respiros sin protagonista.
    Devuelve [(inicio, fin, clip o None, desde, descripción)] ordenados; clip None es un
    respiro, que se rellena con un solo plano de relleno. Lanza RuntimeError con la marca
    culpable si un plano se sale del clip, es demasiado largo o se pisa con otro tramo."""
    planos = planos_del_guion(guion) if guion is not None else []
    fijos = []
    if planos:
        indices = en_la_transcripcion([p[0] for p in planos], palabras, palabras_del_guion(guion))
        for (_, clip, desde, largo, contexto), i in zip(planos, indices):
            marca = f"[plano {clip} {desde:g} {largo:g}] antes de «{contexto}»"
            if i is None or i >= len(palabras):
                raise RuntimeError(f"{marca}: no se encuentra en la transcripción (o está al final)")
            if largo > c["ritmo"]["plano_max"]:
                raise RuntimeError(f"{marca}: dura más que video.ritmo.plano_max ({c['ritmo']['plano_max']:g} s)")
            if desde + largo > duracion_de(clip):
                raise RuntimeError(f"{marca}: se sale del clip, que dura {duracion_de(clip):.1f} s")
            inicio = max(0.0, palabras[i]["inicio"] - ANTICIPO)
            for r in respiros:
                # Si la palabra viene justo después de un respiro, el plano empieza con el respiro
                if (i == 0 or r["inicio"] >= palabras[i - 1]["fin"] - 0.01) and r["fin"] <= palabras[i]["inicio"] + 0.01:
                    inicio = r["inicio"]
            fijos.append((a_fotograma(inicio), a_fotograma(min(inicio + largo, total)), clip, desde, marca))
    for r in respiros:
        cubierto = any(ini <= r["inicio"] + 0.05 and fin >= r["fin"] - 0.05 for ini, fin, *_ in fijos)
        if not cubierto:
            fijos.append((a_fotograma(r["inicio"]), a_fotograma(r["fin"]), None, 0.0,
                          f"[respiro] antes de «{r['antes_de']}»"))
    fijos.sort()
    # Si un plano se pisa con el siguiente (se leyó más rápido de lo previsto), se acorta hasta
    # donde empieza el otro, mientras le queden PLANO_MIN segundos. Si no, error: hay que mover
    # las marcas. En 012, la foto de 2006 se comía el principio de la siguiente por 0,7 s.
    ajustados = []
    for tramo in fijos:
        if ajustados and tramo[0] < ajustados[-1][1] - 0.001:
            anterior = ajustados[-1]
            if anterior[2] is None or tramo[0] - anterior[0] < PLANO_MIN:
                raise RuntimeError(f"Se pisan {anterior[4]} y {tramo[4]}: acorta el primero o aleja las marcas")
            print(f"   AVISO: {anterior[4]} se acorta a {tramo[0] - anterior[0]:.1f} s para no pisar {tramo[4]}")
            ajustados[-1] = (anterior[0], tramo[0], *anterior[2:])
        ajustados.append(tramo)
    return ajustados


def segmentos_con_ritmo(palabras, total, fijos, c, duracion_de):
    """Toda la duración en tramos: los fijos y, entre ellos, cortes de relleno rápidos.
    Devuelve [(inicio, fin, clip o None, desde)]; clip None se reparte con el relleno.
    Un hueco más corto que relleno_min no se convierte en un fogonazo: alarga el tramo
    anterior (si es un plano, solo si al clip le queda material)."""
    ritmo = c["ritmo"]
    relleno = {**c, "corte_min": ritmo["relleno_min"], "corte_max": ritmo["relleno_max"]}
    segmentos, t = [], 0.0
    for inicio, fin, clip, desde, _ in fijos + [(total, total, None, 0.0, "")]:
        if inicio - t > 0.001:
            anterior = segmentos[-1] if segmentos else None
            cabe = anterior and (anterior[2] is None or
                                 anterior[3] + (inicio - anterior[0]) <= duracion_de(anterior[2]))
            if inicio - t < ritmo["relleno_min"] and cabe:
                segmentos[-1] = (anterior[0], inicio, anterior[2], anterior[3])
            elif inicio - t < ritmo["relleno_min"] and not segmentos and clip and desde >= inicio - t:
                # Un plano casi al principio del vídeo: empieza en el 0 (un poco antes en su
                # clip) en vez de dejar delante un fogonazo de relleno de un fotograma
                desde -= inicio - t
                inicio = t
            else:
                puntos = puntos_de_corte(palabras, inicio, relleno, desde=t)
                segmentos += [(a, b, None, 0.0) for a, b in zip(puntos, puntos[1:])]
        if fin > inicio:
            segmentos.append((inicio, fin, clip, desde))
        t = max(t, fin)
    return segmentos


def edl_con_ritmo(palabras, total, guion, respiros, biblioteca, c):
    """Lista de cortes de la fábrica 2.0: protagonistas fijos + relleno rápido."""
    duraciones = {}

    def duracion_de(clip):
        if clip not in duraciones:
            duraciones[clip] = duracion_clip(biblioteca, clip, c["imagen"]["segundos"])
        return duraciones[clip]

    fijos = tramos_fijos(palabras, guion, respiros, total, c, duracion_de)
    segmentos = segmentos_con_ritmo(palabras, total, fijos, c, duracion_de)
    protagonistas = {clip for _, _, clip, _, _ in fijos if clip}
    relleno = [clip for clip in c["clips"] if clip not in protagonistas] or c["clips"]
    for clip in relleno:
        duracion_de(clip)
    largos = [fin - inicio for inicio, fin, clip, _ in segmentos if clip is None]
    edl_relleno, avisos = saltando(largos, {clip: duraciones[clip] for clip in relleno}, c.get("saltar", {}))
    for aviso in avisos:
        print(f"   AVISO: {aviso}")
    if c.get("buscar_destellos"):
        edl_relleno = a_destellos(edl_relleno, biblioteca, duraciones)

    edl, siguiente = [], iter(edl_relleno)
    for inicio, fin, clip, desde in segmentos:
        edl.append(next(siguiente) if clip is None else (clip, desde, fin - inicio))
    for inicio, fin, clip, desde, descripcion in fijos:
        print(f"   {inicio:6.2f}-{fin:6.2f} s: " + (f"{clip} desde {desde:g} s, por {descripcion}"
                                                     if clip else f"un solo plano, {descripcion}"))
    if largos:
        print(f"   {len(largos)} cortes de relleno, de {min(largos):.1f} a {max(largos):.1f} s")
    return edl


def crear_edl(json_palabras, voz, salida, biblioteca, config, guion=None, respiros=()):
    """guion (guion.md) y respiros (los de respiros.json) solo se usan con video.ritmo.activo."""
    c = config["video"]
    if not c["clips"]:
        raise RuntimeError("No hay cortes.txt en la receta ni lista de 'clips' en la configuración")
    palabras = json.loads(json_palabras.read_text(encoding="utf-8"))
    tras = config["final"].get("tras_ultima_palabra")
    if palabras:                                    # el vídeo acaba ahí (como en render)
        total = palabras[-1]["fin"] + (tras if tras is not None else config["final"]["cola"])
    else:
        total = duracion(voz) + config["final"]["cola"]
    if c["ritmo"]["activo"]:
        edl = edl_con_ritmo(palabras, total, guion, list(respiros), biblioteca, c)
    else:
        puntos = puntos_de_corte(palabras, total, c)
        edl = asignar_clips(puntos, c["clips"], biblioteca, c["imagen"]["segundos"], c.get("saltar", {}))
        if c.get("buscar_destellos"):
            duraciones = {clip: duracion_clip(biblioteca, clip, c["imagen"]["segundos"]) for clip in c["clips"]}
            edl = a_destellos(edl, biblioteca, duraciones)
    salida.write_text(
        "".join(f"{clip} {inicio:.3f} {largo:.4f}\n" for clip, inicio, largo in edl),
        encoding="utf-8",
    )
    largos = [largo for _, _, largo in edl]
    print(f"   {len(edl)} cortes automáticos, de {min(largos):.1f} a {max(largos):.1f} s")


def puntos_desde_edl(edl, segundos_corte):
    """Devuelve los momentos de corte de una lista (manual o automática)."""
    t, puntos = 0.0, []
    for linea in edl.read_text(encoding="utf-8").splitlines():
        campos = linea.split()
        if not campos:
            continue
        largo = float(campos[2]) if len(campos) > 2 else segundos_corte
        t += round(largo * FPS) / FPS
        puntos.append(t)
    return puntos[:-1]   # el último es el final del vídeo, no un corte


def elegir_efectos(edl, json_palabras, config):
    """Elige en qué cortes suenan los efectos: los que caen en las pausas más
    marcadas (finales de frase largos), separados entre sí y lejos del inicio y el final."""
    e = config["efectos"]
    palabras = json.loads(json_palabras.read_text(encoding="utf-8"))
    pausas, _ = huecos(palabras, config["video"])
    cortes = puntos_desde_edl(edl, config["video"]["segundos_corte"])
    total = palabras[-1]["fin"]

    # Puntuación de cada corte: la de la pausa en la que cae (0 si no cae en ninguna)
    candidatos = []
    for corte in cortes:
        if corte < e["inicio_min"] or corte > total - 3.0:   # ni al principio ni en los 3 s finales
            continue
        cercanas = [p for m, p in pausas if abs(m - corte) <= 0.1]
        if cercanas and max(cercanas) >= 1.0:   # solo finales de frase
            candidatos.append((corte, max(cercanas)))

    elegidos = []
    for corte, _ in sorted(candidatos, key=lambda x: x[1], reverse=True):
        if all(abs(corte - otro) >= e["separacion_min"] for otro in elegidos):
            elegidos.append(corte)
        if len(elegidos) == e["automaticos"]:
            break
    elegidos.sort()

    lista = []
    for n, momento in enumerate(elegidos):
        archivo = e["archivos"][n % len(e["archivos"])]
        siguientes = " ".join(p["palabra"] for p in palabras if p["inicio"] > momento)[:40]
        print(f"   efecto en {momento:.2f} s, antes de: «{siguientes}...»")
        lista.append({"archivo": archivo, "momento": momento})
    return lista
