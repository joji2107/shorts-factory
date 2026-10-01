"""Transcribe un audio con faster-whisper.

Genera, junto al audio, un .srt (subtítulos por frases)
y un .json (cada palabra con su tiempo de inicio y fin).
"""
import json
import sys
import time
import resource
from pathlib import Path

from faster_whisper import WhisperModel


def formato_srt(segundos):
    """Convierte segundos (65.5) al formato de SRT (00:01:05,500)."""
    ms_totales = int(round(segundos * 1000))
    horas, resto = divmod(ms_totales, 3_600_000)
    minutos, resto = divmod(resto, 60_000)
    segs, ms = divmod(resto, 1000)
    return f"{horas:02}:{minutos:02}:{segs:02},{ms:03}"


def main():
    if len(sys.argv) < 2:
        print("Uso: python transcribir.py <audio> [modelo] [idioma]")
        sys.exit(1)

    audio = Path(sys.argv[1])
    modelo = sys.argv[2] if len(sys.argv) > 2 else "small"
    idioma = sys.argv[3] if len(sys.argv) > 3 else "es"

    inicio = time.perf_counter()
    print(f"Cargando modelo '{modelo}'...")
    whisper = WhisperModel(modelo, device="cpu", compute_type="int8", cpu_threads=2)

    print(f"Transcribiendo {audio.name}...")
    segmentos, info = whisper.transcribe(
        str(audio),
        language=idioma,
        word_timestamps=True,
        vad_filter=True,
    )

    srt = []
    palabras = []
    # 'segmentos' se va generando mientras se transcribe; el trabajo ocurre en este bucle
    for numero, seg in enumerate(segmentos, start=1):
        srt.append(
            f"{numero}\n{formato_srt(seg.start)} --> {formato_srt(seg.end)}\n{seg.text.strip()}\n"
        )
        for p in seg.words:
            palabras.append(
                {"palabra": p.word.strip(), "inicio": round(p.start, 3), "fin": round(p.end, 3)}
            )

    audio.with_suffix(".srt").write_text("\n".join(srt), encoding="utf-8")
    audio.with_suffix(".json").write_text(
        json.dumps(palabras, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    total = time.perf_counter() - inicio
    print(f"Idioma: {info.language} (confianza {info.language_probability:.2f})")
    print(f"Audio: {info.duration:.1f} s | Segmentos: {len(srt)} | Palabras: {len(palabras)}")
    print(f"Tiempo total: {total:.1f} s")
    pico_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(f"RAM pico del proceso: {pico_mb: .0f} MB")


if __name__ == "__main__":
    main()
