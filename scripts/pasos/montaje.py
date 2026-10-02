"""Pasos de vídeo: fondo a partir de la lista de cortes, y render final."""
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


def construir_grafo(ass, total, musica, efectos, loudnorm):
    """Escribe el grafo de la mezcla. 'efectos' es una lista de (retraso_ms, volumen)."""
    partes = [f"[0:v]ass={ass}[video]"]

    if musica:
        partes.append(f"[1:a]{FORMATO},asplit=2[voz][voz_sc]")
        partes.append(
            f"[2:a]{FORMATO},volume={musica['volumen']},"
            f"afade=t=in:d={musica['fundido_entrada']},"
            f"afade=t=out:st={total - musica['fundido_salida']:.3f}:d={musica['fundido_salida']}[musica]"
        )
        partes.append(
            f"[musica][voz_sc]sidechaincompress=threshold={musica['umbral_ducking']}:"
            f"ratio={musica['ratio_ducking']}:attack={musica['ataque_ducking']}:"
            f"release={musica['relajacion_ducking']}[musica_duck]"
        )
        entradas, siguiente = ["[voz]", "[musica_duck]"], 3
    else:
        partes.append(f"[1:a]{FORMATO}[voz]")
        entradas, siguiente = ["[voz]"], 2

    for n, (retraso, volumen) in enumerate(efectos):
        partes.append(
            f"[{siguiente + n}:a]{FORMATO},volume={volumen},adelay={retraso}:all=1[s{n}]"
        )
        entradas.append(f"[s{n}]")

    partes.append(
        f"{''.join(entradas)}amix=inputs={len(entradas)}:duration=longest:normalize=0,"
        f"loudnorm={loudnorm}[audio]"
    )
    return ";\n".join(partes)


def render(fondo, voz, ass, grafo_txt, salida, raiz, config, lista_efectos):
    """Mezcla vídeo, voz, música y efectos, y graba los subtítulos."""
    total = duracion(voz) + config["final"]["cola"]
    if duracion(fondo) < total:
        print("   AVISO: el fondo dura menos que la voz. Faltan cortes en la lista.")

    musica = config["musica"] if config["musica"]["archivo"] else None
    entradas = ["-i", fondo, "-i", voz]
    if musica:
        entradas += ["-ss", musica["inicio"], "-t", f"{total:.3f}", "-i", raiz / musica["archivo"]]

    efectos = []
    for efecto in lista_efectos:
        archivo = raiz / efecto["archivo"]
        # Empieza la mitad de su duración antes del momento, para quedar centrado
        retraso = max(0, round((efecto["momento"] - duracion(archivo) / 2) * 1000))
        efectos.append((retraso, config["efectos"]["volumen"]))
        entradas += ["-i", archivo]

    grafo = construir_grafo(ass, total, musica, efectos, config["final"]["loudnorm"])
    grafo_txt.write_text(grafo, encoding="utf-8")

    ejecutar([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *entradas,
        "-filter_complex_script", grafo_txt,
        "-map", "[video]", "-map", "[audio]", "-t", f"{total:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", config["final"]["crf"],
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        salida,
    ])
    print(f"   duración final: {total:.1f} s, {len(efectos)} efectos")
