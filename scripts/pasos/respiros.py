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
Las marcas [sonido clip desde largo] (fase 11, 015) también son silencios en la voz, del
largo del clip, pero su entrada lleva además "sonido": {"clip", "desde", "largo"}: los cortes
ponen ahí ese clip y el render su audio, con la música apagada. Pueden ir antes de la
primera palabra (el vídeo empieza con el clip) o después de la última (acaba con él).
Los subtítulos, los cortes, los efectos anclados a palabras y el render leen estos
archivos, así que todo se desplaza solo.
"""
import json

from .marcas import en_la_transcripcion, respiros_del_guion, sonidos_del_guion
from .subtitulos import palabras_del_guion
from .utilidades import ejecutar

FRECUENCIA = 48000      # la de voz.wav (mono, 48 kHz)
SONIDO_TRAS_FINAL = 0.4  # un [sonido] al final entra este tiempo después de la última palabra
ANTES_DE_LA_VOZ = 0.3    # con un [sonido] al principio, la voz empieza este tiempo después de él


def puntos_de_insercion(palabras, guion_md, segundos_por_defecto):
    """[(segundo en voz.wav, segundos de silencio, contexto, sonido)]: el centro del hueco
    entre la palabra anterior a cada [respiro] o [sonido] y la siguiente. sonido es None en
    un respiro y {"clip", "desde", "largo"} en un [sonido], que también puede ir al principio
    (se inserta en el segundo 0) o al final (SONIDO_TRAS_FINAL después de la última palabra)."""
    marcas = [(posicion, segundos, contexto, None)
              for posicion, segundos, contexto in respiros_del_guion(guion_md, segundos_por_defecto)]
    marcas += [(posicion, largo, contexto, {"clip": clip, "desde": desde, "largo": largo})
               for posicion, clip, desde, largo, contexto in sonidos_del_guion(guion_md)]
    if not marcas:
        return []
    indices = en_la_transcripcion([m[0] for m in marcas], palabras, palabras_del_guion(guion_md))
    puntos = []
    for (_, segundos, contexto, sonido), i in zip(marcas, indices):
        marca = f"[sonido {sonido['clip']}]" if sonido else "[respiro]"
        if i is None:
            raise RuntimeError(f"El {marca} antes de «{contexto}» no se encuentra en la transcripción")
        if sonido and i == 0:
            # Al principio: lo que hay en la grabación antes (el silencio de antes de hablar,
            # 1,2 s en 015) se quita, para que la voz entre justo después del clip
            punto = max(0.0, palabras[0]["inicio"] - ANTES_DE_LA_VOZ)
            sonido = {**sonido, "al_principio": True}
        elif sonido and i >= len(palabras):
            punto = palabras[-1]["fin"] + SONIDO_TRAS_FINAL
        elif i == 0 or i >= len(palabras):
            raise RuntimeError(f"El [respiro] antes de «{contexto}» está al principio o al final del "
                               "guion: ahí no hace falta (al final ya está la cola)")
        else:
            punto = (palabras[i - 1]["fin"] + palabras[i]["inicio"]) / 2
        puntos.append((punto, segundos, contexto, sonido))
    return sorted(puntos, key=lambda x: x[0])


def recorte_inicial(puntos):
    """Segundos de voz que se quitan del principio: los de antes de un [sonido] inicial."""
    return puntos[0][0] if puntos and puntos[0][3] and puntos[0][3].get("al_principio") else 0.0


def desplazar_palabras(palabras, puntos):
    """Cada palabra se retrasa la suma de los silencios insertados antes de ella (menos lo
    que se quita del principio con un [sonido] inicial)."""
    resultado, recorte = [], recorte_inicial(puntos)
    for p in palabras:
        retraso = sum(segundos for punto, segundos, *_ in puntos if punto <= p["inicio"]) - recorte
        resultado.append({**p, "inicio": round(p["inicio"] + retraso, 3), "fin": round(p["fin"] + retraso, 3)})
    return resultado


def grafo_insercion(puntos):
    """Filtro de FFmpeg que corta la voz en cada punto (por muestras, para que la duración
    sea exacta) y pone en medio el silencio."""
    partes, etiquetas, desde = [], [], 0
    recorte = recorte_inicial(puntos)
    for n, (punto, segundos, *_) in enumerate(puntos):
        hasta = round(punto * FRECUENCIA)
        partes.append(f"anullsrc=r={FRECUENCIA}:cl=mono,atrim=end_sample={round(segundos * FRECUENCIA)}[s{n}]")
        if n == 0 and recorte:
            etiquetas.append(f"[s{n}]")          # lo de antes del [sonido] inicial no entra
        else:
            partes.append(f"[0:a]atrim=start_sample={desde}:end_sample={hasta},asetpts=PTS-STARTPTS[v{n}]")
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
    lista, retraso = [], -recorte_inicial(puntos)
    for punto, segundos, contexto, sonido in puntos:
        inicio = punto + retraso                 # en el tiempo del vídeo final
        entrada = {"inicio": round(inicio, 3), "fin": round(inicio + segundos, 3),
                   "segundos": segundos, "antes_de": contexto}
        if sonido:
            entrada["sonido"] = sonido
        lista.append(entrada)
        retraso += segundos
        que = f"sonido de {sonido['clip']}" if sonido else "respiro"
        print(f"   {que} de {segundos:g} s en {inicio:.2f} s, antes de «{contexto}»")
    lista_salida.write_text(json.dumps(lista, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
