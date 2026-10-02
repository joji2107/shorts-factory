"""Paso 2: transcribir la voz con faster-whisper (palabra a palabra)."""
import json


def formato_srt(segundos):
    ms_totales = int(round(segundos * 1000))
    horas, resto = divmod(ms_totales, 3_600_000)
    minutos, resto = divmod(resto, 60_000)
    segs, ms = divmod(resto, 1000)
    return f"{horas:02}:{minutos:02}:{segs:02},{ms:03}"


def transcribir(audio, srt_salida, json_salida, config):
    # Se importa aquí dentro para que el modelo solo se cargue si el paso se ejecuta
    from faster_whisper import WhisperModel

    modelo = WhisperModel(config["modelo"], device="cpu", compute_type="int8", cpu_threads=2)
    segmentos, info = modelo.transcribe(
        str(audio), language=config["idioma"], word_timestamps=True, vad_filter=True
    )

    srt, palabras = [], []
    for numero, seg in enumerate(segmentos, start=1):
        srt.append(
            f"{numero}\n{formato_srt(seg.start)} --> {formato_srt(seg.end)}\n{seg.text.strip()}\n"
        )
        for p in seg.words:
            palabras.append(
                {"palabra": p.word.strip(), "inicio": round(p.start, 3), "fin": round(p.end, 3)}
            )

    srt_salida.write_text("\n".join(srt), encoding="utf-8")
    json_salida.write_text(json.dumps(palabras, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   {info.duration:.1f} s de audio, {len(srt)} segmentos, {len(palabras)} palabras")
