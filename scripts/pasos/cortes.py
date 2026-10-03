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
- Con final.tras_ultima_palabra (bucle), los cortes llegan hasta ahí y no más.
"""
import json
import random
import re
import statistics

from .utilidades import duracion, ejecutar

FPS = 30
MARGEN = 0.5        # segundos que se saltan entre dos usos de un clip, para no repetir plano
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


def puntos_de_corte(palabras, total, c):
    """Elige los momentos de corte tramo a tramo."""
    pausas, fronteras = huecos(palabras, c)
    puntos = [0.0]
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


def asignar_clips(puntos, clips, biblioteca):
    """Mide los clips, los reparte entre los cortes y avisa si falta material."""
    duraciones = {clip: duracion(biblioteca / f"{clip}.mp4") for clip in clips}
    largos = [b - a for a, b in zip(puntos, puntos[1:])]
    edl, avisos = repartir(largos, clips, duraciones)
    for aviso in avisos:
        print(f"   AVISO: {aviso}")
    return desplazar(edl, duraciones)


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
    el primer hueco libre, si ahí pisaría a otro)."""
    pendientes = {clip: destellos(biblioteca / f"{clip}.mp4") for clip in {clip for clip, _, _ in edl}}
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


def crear_edl(json_palabras, voz, salida, biblioteca, config):
    c = config["video"]
    if not c["clips"]:
        raise RuntimeError("No hay cortes.txt en la receta ni lista de 'clips' en la configuración")
    palabras = json.loads(json_palabras.read_text(encoding="utf-8"))
    tras = config["final"].get("tras_ultima_palabra")
    if tras is not None and palabras:
        total = palabras[-1]["fin"] + tras          # bucle: el vídeo acaba ahí (como en render)
    else:
        total = duracion(voz) + config["final"]["cola"]
    puntos = puntos_de_corte(palabras, total, c)
    edl = asignar_clips(puntos, c["clips"], biblioteca)
    if c.get("buscar_destellos"):
        duraciones = {clip: duracion(biblioteca / f"{clip}.mp4") for clip in c["clips"]}
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
