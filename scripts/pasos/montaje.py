"""Pasos de vídeo: fondo a partir de la lista de cortes, y render final.

El render normaliza el volumen en dos pasadas: primero mezcla el audio y lo mide,
y después aplica la corrección exacta al montarlo con el vídeo.
"""
import json

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
        ejecutar([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", inicio, "-i", biblioteca / f"{clip}.mp4", "-frames:v", fotogramas,
            "-vf", ENCUADRES[c["encuadre"]],
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


def construir_grafo_audio(total, musica, efectos):
    """Grafo de la mezcla de audio, sin normalizar. Entradas: 0 voz, 1 música (si hay),
    y después los efectos. 'efectos' es una lista de (retraso_ms, volumen)."""
    if musica:
        partes = [
            f"[0:a]{FORMATO},asplit=2[voz][voz_sc]",
            f"[1:a]{FORMATO},volume={musica['volumen']},"
            f"afade=t=in:d={musica['fundido_entrada']},"
            f"afade=t=out:st={total - musica['fundido_salida']:.3f}:d={musica['fundido_salida']}[musica]",
            f"[musica][voz_sc]sidechaincompress=threshold={musica['umbral_ducking']}:"
            f"ratio={musica['ratio_ducking']}:attack={musica['ataque_ducking']}:"
            f"release={musica['relajacion_ducking']}[musica_duck]",
        ]
        entradas, siguiente = ["[voz]", "[musica_duck]"], 2
    else:
        partes = [f"[0:a]{FORMATO}[voz]"]
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


def medir_volumen(archivo, objetivo):
    """Primera pasada de loudnorm: mide el audio sin modificarlo."""
    resultado = ejecutar([
        "ffmpeg", "-hide_banner", "-nostats", "-i", archivo, "-vn",
        "-af", f"loudnorm={objetivo}:print_format=json", "-f", "null", "-",
    ])
    return leer_json_final(resultado.stderr)


def render(fondo, voz, ass, grafo_txt, salida, raiz, config, lista_efectos):
    """Mezcla voz, música y efectos, normaliza en dos pasadas y graba los subtítulos."""
    total = duracion(voz) + config["final"]["cola"]
    if duracion(fondo) < total:
        print("   AVISO: el fondo dura menos que la voz. Faltan cortes en la lista.")

    musica = config["musica"] if config["musica"]["archivo"] else None
    entradas = ["-i", voz]
    if musica:
        entradas += ["-ss", musica["inicio"], "-t", f"{total:.3f}", "-i", raiz / musica["archivo"]]

    efectos = []
    for efecto in lista_efectos:
        archivo = raiz / efecto["archivo"]
        # Empieza la mitad de su duración antes del momento, para quedar centrado
        retraso = max(0, round((efecto["momento"] - duracion(archivo) / 2) * 1000))
        efectos.append((retraso, config["efectos"]["volumen"]))
        entradas += ["-i", archivo]

    # 1) Mezcla de audio, todavía sin normalizar
    mezcla_wav = salida.parent / "mezcla.wav"
    grafo_txt.write_text(construir_grafo_audio(total, musica, efectos), encoding="utf-8")
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
    ejecutar([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", fondo, "-i", mezcla_wav,
        "-filter_complex", f"[0:v]ass={ass}[video];[1:a]{audio}[audio]",
        "-map", "[video]", "-map", "[audio]", "-t", f"{total:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", config["final"]["crf"],
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        salida,
    ])

    # 4) Comprobación: medir el archivo terminado
    f = medir_volumen(salida, objetivo)
    print(f"   volumen: mezcla {m['input_i']} LUFS, ganancia {ganancia:+.2f} dB "
          f"-> final {f['input_i']} LUFS, pico {f['input_tp']} dBTP")
    print(f"   duración final: {total:.1f} s, {len(efectos)} efectos")
