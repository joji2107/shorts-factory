"""Pasos de vídeo: fondo a partir de la lista de cortes, y render final.

El render normaliza el volumen en dos pasadas: primero mezcla el audio y lo mide,
y después aplica la corrección exacta al montarlo con el vídeo.
"""
import json
import re
import shutil
from pathlib import Path

from .clips import es_foto, filtro_foto, ruta_clip
from .musica import inicio_musica, leer_energia, respiros_flojos
from .utilidades import ejecutar, duracion

FORMATO = "aformat=sample_rates=48000:channel_layouts=stereo"

ENCUADRES = {
    "relleno": (
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1"
    ),
    "desenfocado": (
        "split[a][b];"
        "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:2[fondo];"
        "[b]scale=1080:-2[frente];"
        "[fondo][frente]overlay=(W-w)/2:(H-h)/2,fps=30,setsar=1"
    ),
}


def generar_fondo(edl, biblioteca, carpeta, salida, c):
    """Crea un corte por cada línea de la lista y los une en un solo vídeo."""
    carpeta.mkdir(exist_ok=True)
    lineas = [l.split() for l in edl.read_text(encoding="utf-8").splitlines() if l.strip()]

    lista = []
    for n, campos in enumerate(lineas, start=1):
        clip, inicio = campos[0], campos[1]
        largo = float(campos[2]) if len(campos) > 2 else c["segundos_corte"]
        fotogramas = round(largo * 30)
        corte = carpeta / f"corte_{n:02}.mp4"
        ruta = ruta_clip(biblioteca, clip)
        if es_foto(ruta):
            # Una foto: el tramo de su vídeo virtual (Ken Burns) que empieza en 'inicio'
            entrada = ["-loop", "1", "-framerate", "30", "-i", ruta]
            filtro = filtro_foto(ruta, float(inicio), c["imagen"])
        else:
            entrada = ["-ss", inicio, "-i", ruta]
            filtro = ENCUADRES[c["encuadre"]]
        ejecutar([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            *entrada, "-frames:v", fotogramas,
            "-vf", filtro,
            "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            corte,
        ])
        lista.append(f"file '{corte.name}'")
        print(f"   {corte.name}: {clip} desde el segundo {inicio}")

    archivo_lista = carpeta / "lista.txt"
    archivo_lista.write_text("\n".join(lista) + "\n", encoding="utf-8")
    ejecutar([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", archivo_lista, "-c", "copy", salida,
    ])
    # Los cortes sueltos ya están dentro de fondo.mp4: no hace falta guardarlos
    shutil.rmtree(carpeta)


def subida_en_respiros(subida_db, rampa, tramos):
    """Filtro que sube la música subida_db en cada respiro (inicio, fin): empieza a subir
    al callarse la voz y acaba de bajar justo cuando vuelve, con rampas de 'rampa' s."""
    factor = 10 ** (subida_db / 20) - 1
    envolventes = "+".join(f"min(clip((t-{a:.3f})/{rampa},0,1),clip(({b:.3f}-t)/{rampa},0,1))"
                           for a, b in tramos)
    return f"volume=eval=frame:volume='1+{factor:.4f}*({envolventes})'"


def construir_grafo_audio(total, musica, efectos, subida=None):
    """Grafo de la mezcla de audio, sin normalizar. Entradas: 0 voz, 1 música (si hay),
    y después los efectos. 'efectos' es una lista de (retraso_ms, volumen).
    subida (fábrica 2.0): (dB, rampa, [(inicio, fin)]) para subir la música en los respiros.
    Sin subida, el grafo es exactamente el de siempre."""
    # La voz se alarga con silencio hasta el final: sidechaincompress termina cuando
    # termina su entrada más corta, y sin esto la música se cortaba al acabar la voz
    # (la cola y el fundido de salida se quedaban mudos).
    voz = f"[0:a]{FORMATO},apad=whole_dur={total:.3f}"
    if musica:
        partes = [
            f"{voz},asplit=2[voz][voz_sc]",
            f"[1:a]{FORMATO},volume={musica['volumen']},"
            f"afade=t=in:d={musica['fundido_entrada']},"
            f"afade=t=out:st={total - musica['fundido_salida']:.3f}:d={musica['fundido_salida']}[musica]",
            f"[musica][voz_sc]sidechaincompress=threshold={musica['umbral_ducking']}:"
            f"ratio={musica['ratio_ducking']}:attack={musica['ataque_ducking']}:"
            f"release={musica['relajacion_ducking']}[musica_duck]",
        ]
        if subida and subida[2]:
            # En los respiros la voz calla, el ducking se suelta solo y además la música sube
            partes[-1] = partes[-1].replace("[musica_duck]", "[musica_sin_subida]")
            partes.append(f"[musica_sin_subida]{subida_en_respiros(*subida)}[musica_duck]")
        entradas, siguiente = ["[voz]", "[musica_duck]"], 2
    else:
        partes = [f"{voz}[voz]"]
        entradas, siguiente = ["[voz]"], 1

    for n, (retraso, volumen) in enumerate(efectos):
        partes.append(
            f"[{siguiente + n}:a]{FORMATO},volume={volumen},adelay={retraso}:all=1[s{n}]"
        )
        entradas.append(f"[s{n}]")

    partes.append(
        f"{''.join(entradas)}amix=inputs={len(entradas)}:duration=longest:normalize=0[mezcla]"
    )
    return ";\n".join(partes)


def leer_json_final(texto):
    """loudnorm escribe su informe JSON al final de la salida de FFmpeg: lo extrae."""
    return json.loads(texto[texto.rfind("{"): texto.rfind("}") + 1])


def pico(archivo):
    """El pico de un archivo de audio, en dB (volumedetect)."""
    resultado = ejecutar([
        "ffmpeg", "-hide_banner", "-nostats", "-i", archivo, "-af", "volumedetect", "-f", "null", "-",
    ])
    return float(re.search(r"max_volume: (-?[\d.]+) dB", resultado.stderr).group(1))


def medir_volumen(archivo, objetivo):
    """Primera pasada de loudnorm: mide el audio sin modificarlo."""
    resultado = ejecutar([
        "ffmpeg", "-hide_banner", "-nostats", "-i", archivo, "-vn",
        "-af", f"loudnorm={objetivo}:print_format=json", "-f", "null", "-",
    ])
    return leer_json_final(resultado.stderr)


def inicio_automatico(musica, respiros, total, raiz):
    """musica.inicio "auto" (fábrica 2.0): el segundo de la canción desde el que empezar
    para que su momento fuerte (biblioteca/musica.json) suene en la revelación, que es el
    último respiro. Si no se puede (sin respiros, canción sin analizar o plana), desde 0."""
    nombre = Path(musica["archivo"]).name
    energia = leer_energia(raiz).get(nombre)
    if not respiros:
        print("   AVISO: música 'auto' sin respiros: no hay revelación con la que sincronizarla, empieza en 0")
        return 0.0
    if not energia:
        print(f"   AVISO: {nombre} no está en biblioteca/musica.json (analizar_musica.py): empieza en 0")
        return 0.0
    if energia["plana"]:
        print(f"   AVISO: {nombre} es plana (sin momento fuerte): empieza en 0")
        return 0.0
    revelacion = respiros[-1]["inicio"]
    inicio, aviso = inicio_musica(energia["momento_fuerte"], revelacion, total, energia["duracion"])
    if aviso:
        print(f"   AVISO: {aviso}")
    print(f"   música desde el segundo {inicio:g}: su momento fuerte ({energia['momento_fuerte']} s, "
          f"+{energia['subida_db']:g} dB) en la revelación ({revelacion:.2f} s)")
    return inicio


def crear_flecha(salida, alto):
    """PNG de una flecha roja con borde blanco, con la punta abajo (en el centro del borde
    inferior), de 'alto' píxeles. Se dibuja con geq (sin fuentes: con el carácter ⬇ y
    drawtext salía un rombo con «?»): un mango hasta el 56 % de la altura y una punta.
    El borde blanco es la forma entera; la parte roja va metida 'm' píxeles por dentro."""
    ancho, m = round(alto * 0.7), max(2, alto // 16)
    medio, cuello = ancho / 2, alto * 0.56
    borde = (f"(lt(abs(X-{medio:.1f}),{ancho * 0.16 + m:.1f})*lt(Y,{cuello + m:.1f})"
             f"+gte(Y,{cuello - m:.1f})*lt(abs(X-{medio:.1f}),({alto}-Y)*{medio / (alto - cuello):.4f}))")
    roja = (f"(lt(abs(X-{medio:.1f}),{ancho * 0.16:.1f})*gt(Y,{m})*lt(Y,{cuello:.1f})"
            f"+gte(Y,{cuello:.1f})*lt(abs(X-{medio:.1f}),({alto - 2 * m}-Y)*{(medio - m) / (alto - 2 * m - cuello):.4f}))")
    ejecutar(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
              "-i", f"color=c=black@0:s={ancho}x{alto},format=rgba", "-frames:v", "1", "-vf",
              f"geq=r='if(gt({roja},0),230,255)':g='if(gt({roja},0),25,255)':b='if(gt({roja},0),25,255)'"
              f":a='255*gt({borde},0)'", salida])
    return ancho, alto


def render(fondo, voz, ass, grafo_txt, salida, raiz, config, lista_efectos, fin_ultima_palabra=None,
           respiros=(), flechas=()):
    """Mezcla voz, música y efectos, normaliza en dos pasadas y graba los subtítulos.
    fin_ultima_palabra: segundo en que acaba la última palabra (de la transcripción).
    respiros: los de respiros.json (fábrica 2.0): la música sube en ellos."""
    tras = config["final"].get("tras_ultima_palabra")
    if fin_ultima_palabra is not None:
        # El vídeo acaba la cola después de la última palabra, no al final de la grabación:
        # lo que se grabe después (silencio, ruido al parar) se queda fuera. En un bucle,
        # tras_ultima_palabra (0,5 s) para que enlace con la primera frase.
        total = fin_ultima_palabra + (tras if tras is not None else config["final"]["cola"])
    else:
        total = duracion(voz) + config["final"]["cola"]
    if duracion(fondo) < total - 0.05:   # margen de un fotograma y poco más
        print("   AVISO: el fondo dura menos que la voz. Faltan cortes en la lista.")

    musica = dict(config["musica"]) if config["musica"]["archivo"] else None
    if musica and fin_ultima_palabra is not None:
        # El fundido de salida de la música no empieza antes de la última palabra
        musica["fundido_salida"] = round(min(musica["fundido_salida"], total - fin_ultima_palabra), 3)
    if musica and musica["inicio"] == "auto":
        musica["inicio"] = inicio_automatico(musica, list(respiros), total, raiz)
    energia = leer_energia(raiz).get(Path(musica["archivo"]).name) if musica else None
    if energia and respiros:
        for aviso in respiros_flojos(energia, float(musica["inicio"]), respiros):
            print(f"   AVISO: {aviso}")
    entradas = ["-i", voz]
    if musica:
        entradas += ["-ss", musica["inicio"], "-t", f"{total:.3f}", "-i", raiz / musica["archivo"]]

    efectos = []
    e = config["efectos"]
    for efecto in lista_efectos:
        archivo = raiz / efecto["archivo"]
        # Empieza la mitad de su duración antes del momento, para quedar centrado
        retraso = max(0, round((efecto["momento"] - duracion(archivo) / 2) * 1000))
        # Cada efecto viene con un nivel distinto (de -0,1 a -21 dB de pico): primero se
        # lleva su pico a efectos.pico y después se aplica efectos.volumen, igual para todos
        medido = pico(archivo)
        volumen = e["volumen"] * 10 ** ((e["pico"] - medido) / 20)
        print(f"   efecto {archivo.name}: pico {medido:.1f} dB, ajuste {e['pico'] - medido:+.1f} dB")
        efectos.append((retraso, f"{volumen:.4f}"))
        entradas += ["-i", archivo]

    # 1) Mezcla de audio, todavía sin normalizar
    mezcla_wav = salida.parent / "mezcla.wav"
    r = config["respiros"]
    subida = (r["subida_musica_db"], r["rampa"], [(x["inicio"], x["fin"]) for x in respiros]) if respiros else None
    if musica and subida:
        print(f"   la música sube {r['subida_musica_db']:g} dB en {len(respiros)} respiros")
    grafo_txt.write_text(construir_grafo_audio(total, musica, efectos, subida), encoding="utf-8")
    ejecutar([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *entradas,
        "-filter_complex_script", grafo_txt, "-map", "[mezcla]", "-t", f"{total:.3f}",
        "-ar", "48000", "-c:a", "pcm_s24le", mezcla_wav,
    ])

    # 2) Primera pasada: medir la mezcla
    objetivo = config["final"]["loudnorm"]
    valores = dict(parte.split("=") for parte in objetivo.split(":"))   # {"I": "-14", "TP": "-2", ...}
    m = medir_volumen(mezcla_wav, objetivo)

    # 3) Segunda pasada: la ganancia exacta que falta hasta el objetivo, y un limitador
    #    con el techo 1 dB por debajo del pico permitido (margen para la codificación AAC)
    ganancia = float(valores["I"]) - float(m["input_i"])
    techo = 10 ** ((float(valores["TP"]) - 1.0) / 20)   # de dB a valor lineal
    audio = f"volume={ganancia:.2f}dB,alimiter=limit={techo:.4f}:level=disabled"
    # Flechas ([flecha x y] del guion): (inicio, fin, x, y) en la pantalla, con la punta en
    # (x, y) y un rebote suave. Van antes de los subtítulos, para no taparlos. Sin flechas,
    # el comando es el de siempre.
    video, entrada_flecha = f"[0:v]ass={ass}[video]", []
    if flechas:
        png = Path(grafo_txt).with_name("flecha.png")
        ancho, alto = crear_flecha(png, config["flechas"]["alto"])
        entrada_flecha = ["-loop", "1", "-i", png]
        cadena, anterior = [], "[0:v]"
        for n, (inicio, fin, x, y) in enumerate(flechas):
            rebote = f"{alto * 0.15:.0f}*abs(sin(2*PI*1.5*(t-{inicio:.3f})))"
            cadena.append(f"{anterior}[2:v]overlay=x={x - ancho / 2:.0f}:y='{y - alto:.0f}-{rebote}'"
                          f":enable='between(t,{inicio:.3f},{fin:.3f})':shortest=1[f{n}]")
            anterior = f"[f{n}]"
        video = ";".join(cadena) + f";{anterior}ass={ass}[video]"
    ejecutar([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", fondo, "-i", mezcla_wav, *entrada_flecha,
        "-filter_complex", f"{video};[1:a]{audio}[audio]",
        "-map", "[video]", "-map", "[audio]", "-t", f"{total:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", config["final"]["crf"],
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        salida,
    ])

    # 4) Comprobación: medir el archivo terminado
    f = medir_volumen(salida, objetivo)
    print(f"   volumen: mezcla {m['input_i']} LUFS, ganancia {ganancia:+.2f} dB "
          f"-> final {f['input_i']} LUFS, pico {f['input_tp']} dBTP")
    fundido = f", fundido de la música {musica['fundido_salida']:g} s" if musica else ""
    print(f"   duración final: {total:.1f} s, {len(efectos)} efectos{fundido}")
