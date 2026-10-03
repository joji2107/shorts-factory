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
"""
import json
import random

from .utilidades import duracion

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


def crear_edl(json_palabras, voz, salida, biblioteca, config):
    c = config["video"]
    if not c["clips"]:
        raise RuntimeError("No hay cortes.txt en la receta ni lista de 'clips' en la configuración")
    palabras = json.loads(json_palabras.read_text(encoding="utf-8"))
    total = duracion(voz) + config["final"]["cola"]
    puntos = puntos_de_corte(palabras, total, c)
    edl = asignar_clips(puntos, c["clips"], biblioteca)
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
