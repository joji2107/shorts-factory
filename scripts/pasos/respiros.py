"""Paso respiros (fábrica 2.0): mete silencios en la voz donde el guion dice [respiro N].

El locutor lee seguido, con una pausa normal, y aquí se inserta el silencio exacto: así
dura lo que dice el guion (se cambia sin volver a grabar), es silencio digital (sin el
ruido de fondo de la sala, que la cadena de voz subiría) y Whisper no ve silencios
largos, en los que tiende a inventarse texto.

Escribe:
- voz_respiros.wav: la voz con los silencios.
- palabras_respiros.json: los tiempos de la transcripción desplazados. palabras.json no
  cambia (la velocidad de lectura se mide con la grabación real).
- respiros.json: [{"inicio", "fin", "segundos", "antes_de"}] en el tiempo del vídeo final,
  para que el render suba la música en ellos y los cortes no corten dentro.
Los subtítulos, los cortes, los efectos anclados a palabras y el render leen estos
archivos, así que todo se desplaza solo.
"""
import json

from .marcas import en_la_transcripcion, respiros_del_guion
from .subtitulos import palabras_del_guion
from .utilidades import ejecutar

FRECUENCIA = 48000      # la de voz.wav (mono, 48 kHz)


def puntos_de_insercion(palabras, guion_md, segundos_por_defecto):
    """[(segundo en voz.wav, segundos de silencio, contexto)]: el centro del hueco entre la
    palabra anterior a cada [respiro] y la siguiente."""
    marcas = respiros_del_guion(guion_md, segundos_por_defecto)
    if not marcas:
        return []
    indices = en_la_transcripcion([m[0] for m in marcas], palabras, palabras_del_guion(guion_md))
    puntos = []
    for (_, segundos, contexto), i in zip(marcas, indices):
        if i is None:
            raise RuntimeError(f"El [respiro] antes de «{contexto}» no se encuentra en la transcripción")
        if i == 0 or i >= len(palabras):
            raise RuntimeError(f"El [respiro] antes de «{contexto}» está al principio o al final del "
                               "guion: ahí no hace falta (al final ya está la cola)")
        punto = (palabras[i - 1]["fin"] + palabras[i]["inicio"]) / 2
        puntos.append((punto, segundos, contexto))
    return sorted(puntos)


def desplazar_palabras(palabras, puntos):
    """Cada palabra se retrasa la suma de los silencios insertados antes de ella."""
    resultado = []
    for p in palabras:
        retraso = sum(segundos for punto, segundos, _ in puntos if punto <= p["inicio"])
        resultado.append({**p, "inicio": round(p["inicio"] + retraso, 3), "fin": round(p["fin"] + retraso, 3)})
    return resultado


def grafo_insercion(puntos):
    """Filtro de FFmpeg que corta la voz en cada punto (por muestras, para que la duración
    sea exacta) y pone en medio el silencio."""
    partes, etiquetas, desde = [], [], 0
    for n, (punto, segundos, _) in enumerate(puntos):
        hasta = round(punto * FRECUENCIA)
        partes.append(f"[0:a]atrim=start_sample={desde}:end_sample={hasta},asetpts=PTS-STARTPTS[v{n}]")
        partes.append(f"anullsrc=r={FRECUENCIA}:cl=mono,atrim=end_sample={round(segundos * FRECUENCIA)}[s{n}]")
        etiquetas += [f"[v{n}]", f"[s{n}]"]
        desde = hasta
    partes.append(f"[0:a]atrim=start_sample={desde},asetpts=PTS-STARTPTS[v{len(puntos)}]")
    etiquetas.append(f"[v{len(puntos)}]")
    partes.append(f"{''.join(etiquetas)}concat=n={len(etiquetas)}:v=0:a=1[voz]")
    return ";".join(partes)


def crear_respiros(voz, json_palabras, guion_md, voz_salida, json_salida, lista_salida, c):
    palabras = json.loads(json_palabras.read_text(encoding="utf-8"))
    puntos = puntos_de_insercion(palabras, guion_md, c["segundos"])
    if puntos:
        ejecutar([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", voz,
            "-filter_complex", grafo_insercion(puntos), "-map", "[voz]",
            "-ar", str(FRECUENCIA), "-ac", "1", "-c:a", "pcm_s24le", voz_salida,
        ])
    else:
        print("   AVISO: respiros activados, pero el guion no tiene ningún [respiro]")
        ejecutar(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", voz, "-c", "copy", voz_salida])

    json_salida.write_text(json.dumps(desplazar_palabras(palabras, puntos), ensure_ascii=False, indent=1),
                           encoding="utf-8")
    lista, retraso = [], 0.0
    for punto, segundos, contexto in puntos:
        inicio = punto + retraso                 # en el tiempo del vídeo final
        lista.append({"inicio": round(inicio, 3), "fin": round(inicio + segundos, 3),
                      "segundos": segundos, "antes_de": contexto})
        retraso += segundos
        print(f"   respiro de {segundos:g} s en {inicio:.2f} s, antes de «{contexto}»")
    lista_salida.write_text(json.dumps(lista, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
