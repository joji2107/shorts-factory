"""Paso 1: procesar la voz con la cadena de filtros de la configuración."""
import re

from .utilidades import ejecutar, duracion


def detectar_voz(original, umbral="-45dB", margen=0.3):
    """Devuelve (inicio, fin) de la parte con voz, saltando el silencio del principio
    y del final de la grabación. Se usa cuando la configuración dice "inicio": "auto"."""
    texto = ejecutar([
        "ffmpeg", "-hide_banner", "-nostats", "-i", original,
        "-af", f"silencedetect=noise={umbral}:d=0.5", "-f", "null", "-",
    ]).stderr
    total = duracion(original)
    comienzos = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", texto)]
    finales = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", texto)]

    inicio, fin = 0.0, total
    # Si la grabación empieza en silencio, la voz empieza donde acaba ese silencio
    if comienzos and comienzos[0] <= 0.1 and finales:
        inicio = max(0.0, finales[0] - margen)
    # Si termina en silencio, se corta medio segundo después de la última palabra
    if comienzos and comienzos[-1] > inicio and (len(finales) < len(comienzos) or finales[-1] >= total - 0.1):
        fin = min(total, comienzos[-1] + 0.5)
    return inicio, fin


def tramos_con_sonido(archivo, umbral):
    """Devuelve la lista de (inicio, fin) con sonido, usando silencios cortos (0,1 s)."""
    texto = ejecutar([
        "ffmpeg", "-hide_banner", "-nostats", "-i", archivo,
        "-af", f"silencedetect=noise={umbral}:d=0.1", "-f", "null", "-",
    ]).stderr
    total = duracion(archivo)
    comienzos = [max(0.0, float(x)) for x in re.findall(r"silence_start: (-?[\d.]+)", texto)]
    finales = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", texto)]
    if len(finales) < len(comienzos):
        finales.append(total)  # el último silencio llega hasta el final

    tramos, desde = [], 0.0
    for comienzo, final in zip(comienzos, finales):
        if comienzo > desde:
            tramos.append((desde, comienzo))
        desde = final
    if desde < total:
        tramos.append((desde, total))
    return tramos


def quitar_ruidos(salida, config):
    """Recorta los ruidos sueltos del principio y del final (un chasquido, un roce al
    parar la grabación): sonidos de menos de `duracion_max` separados de la voz por un
    hueco de al menos `hueco_min`. silencedetect con d=0.5 no los ve, porque no hay
    medio segundo de silencio entre el ruido y la primera palabra."""
    tramos = tramos_con_sonido(salida, config["umbral"])
    corto = lambda t: t[1] - t[0] <= config["duracion_max"]
    # Un sonido corto es ruido si lo separa un hueco de la voz o si va pegado a otro
    # sonido corto (dos chasquidos seguidos)
    ruido_inicio = ruido_fin = None
    while len(tramos) > 1 and corto(tramos[0]) and (
            tramos[1][0] - tramos[0][1] >= config["hueco_min"] or corto(tramos[1])):
        ruido_inicio = tramos.pop(0)
    while len(tramos) > 1 and corto(tramos[-1]) and (
            tramos[-1][0] - tramos[-2][1] >= config["hueco_min"] or corto(tramos[-2])):
        ruido_fin = tramos.pop()
    if not ruido_inicio and not ruido_fin:
        return

    inicio, fin = 0.0, duracion(salida)
    if ruido_inicio:
        inicio = max(ruido_inicio[1] + 0.02, tramos[0][0] - config["margen"])
        print(f"   ruido al principio hasta {ruido_inicio[1]:.2f} s: la voz empieza en {inicio:.2f} s")
    if ruido_fin:
        fin = min(ruido_fin[0] - 0.02, tramos[-1][1] + config["margen"] * 2)
        print(f"   ruido al final en {ruido_fin[0]:.2f} s: la voz acaba en {fin:.2f} s")

    temporal = salida.with_name("voz_sin_ruidos.wav")
    ejecutar([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{inicio:.3f}", "-t", f"{fin - inicio:.3f}", "-i", salida,
        "-c:a", "pcm_s24le", temporal,
    ])
    temporal.replace(salida)


def procesar_voz(original, salida, config):
    if config["inicio"] == "auto":
        inicio, fin = detectar_voz(original, config.get("umbral_silencio", "-45dB"),
                                   config.get("margen_inicio", 0.3))
        print(f"   voz detectada entre {inicio:.2f} y {fin:.2f} s")
        recorte = ["-ss", f"{inicio:.3f}", "-t", f"{fin - inicio:.3f}"]
    else:
        recorte = ["-ss", config["inicio"]]

    ejecutar([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        *recorte, "-i", original,
        # Primero a mono: así la normalización final de la cadena mide la señal
        # tal como se va a guardar (si se pasa a mono al final, pierde 3 dB)
        "-af", "aformat=channel_layouts=mono," + config["cadena"],
        "-ac", "1", "-ar", "48000", "-c:a", "pcm_s24le",
        salida,
    ])
    # Sobre la voz ya procesada: el ruido de fondo queda muy por debajo de la voz
    if config.get("quitar_ruidos"):
        quitar_ruidos(salida, config["quitar_ruidos"])
