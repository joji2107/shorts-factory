"""Progreso del short que está haciendo el vigilante, para verlo en una ventana.

Escribe data/estado/progreso.json (lo lee ventana_progreso.sh, en el Mac, para abrir la
página al empezar, avisar si falla y abrir el vídeo al terminar) y data/estado/progreso.html
(la página: barra de progreso, pasos, tiempo y, si falla, qué ha pasado y qué hacer).
Mientras trabaja, la página se recarga sola cada segundo.

La barra avanza por pasos, cada uno con su peso según lo que suele tardar (la transcripción
y el render son los largos): no hay forma de saber cuánto le falta a FFmpeg o a Whisper
dentro de un paso, así que el paso en marcha se ve a rayas.
"""
import html
import json
import os
import re
import statistics
import time

from crear_short import PASOS, RAIZ

CARPETA = RAIZ / "data" / "estado"
JSON = CARPETA / "progreso.json"
PAGINA = CARPETA / "progreso.html"
REGISTRO = RAIZ / "data" / "registro.log"

# Peso de cada paso en la barra (proporcional a lo que suele tardar)
PESOS = {"preparar": 2, "voz": 5, "transcripcion": 35, "respiros": 2, "subtitulos": 3, "fondo": 25, "render": 28}
TEXTOS = {"preparar": "Preparar la receta", "voz": "Limpiar la voz", "transcripcion": "Transcribir la voz (Whisper)",
          "respiros": "Meter los respiros", "subtitulos": "Subtítulos", "fondo": "Montar las imágenes",
          "render": "Mezclar el audio y grabar el vídeo"}

_estado = {}


def suele_tardar():
    """Mediana de los minutos de los últimos 5 shorts del registro ("OK ... en 2.4 min")."""
    if not REGISTRO.exists():
        return None
    minutos = [float(m) for m in re.findall(r"  OK\s+\S+ en ([\d.]+) min", REGISTRO.read_text(encoding="utf-8"))]
    return round(statistics.median(minutos[-5:]), 1) if minutos else None


def _guardar():
    """Escribe el JSON y la página de golpe (a un temporal y renombrando): así la página o el
    script del Mac nunca leen un archivo a medio escribir."""
    CARPETA.mkdir(parents=True, exist_ok=True)
    hechos = sum(PESOS[p["nombre"]] for p in _estado["pasos"] if p["estado"] == "hecho")
    total = sum(PESOS[p["nombre"]] for p in _estado["pasos"] if p["estado"] != "saltado")
    _estado["porcentaje"] = 100 if _estado["estado"] == "listo" else round(100 * hechos / total)
    for ruta, texto in ((JSON, json.dumps(_estado, ensure_ascii=False, indent=2)), (PAGINA, _pagina())):
        temporal = ruta.with_name(ruta.name + ".tmp")
        temporal.write_text(texto, encoding="utf-8")
        os.replace(temporal, ruta)


def empezar(nombre):
    """Un short nuevo: todos los pasos pendientes y el primero (preparar) en marcha."""
    _estado.clear()
    _estado.update({"short": nombre, "estado": "procesando", "inicio": round(time.time()), "fin": None,
                    "mensaje": "", "video": "", "log": "", "suele_tardar_min": suele_tardar(),
                    "pasos": [{"nombre": p, "texto": TEXTOS[p], "estado": "pendiente"} for p in ["preparar"] + PASOS]})
    _estado["pasos"][0]["estado"] = "ahora"
    _guardar()


def paso(nombre, saltado=False):
    """Empieza un paso: los anteriores quedan hechos. saltado: el paso no hace falta (respiros
    desactivados) y no cuenta en la barra."""
    if not _estado:
        return
    llegado = False
    for p in _estado["pasos"]:
        if p["nombre"] == nombre:
            p["estado"] = "saltado" if saltado else "ahora"
            llegado = True
        elif not llegado and p["estado"] in ("ahora", "pendiente"):
            p["estado"] = "hecho"
    _guardar()


def terminar(video):
    """El short está hecho: todo en verde y la ruta del vídeo (para abrirlo desde el Mac)."""
    if not _estado:
        return
    for p in _estado["pasos"]:
        if p["estado"] != "saltado":
            p["estado"] = "hecho"
    _estado.update({"estado": "listo", "fin": round(time.time()), "video": str(video.relative_to(RAIZ))})
    _guardar()


def fallar(mensaje, log):
    """Ha fallado: el paso en marcha queda en rojo, con el mensaje y qué hacer."""
    if not _estado:
        return
    for p in _estado["pasos"]:
        if p["estado"] == "ahora":
            p["estado"] = "error"
    _estado.update({"estado": "error", "fin": round(time.time()), "mensaje": str(mensaje),
                    "log": str(log.relative_to(RAIZ))})
    _guardar()


def consejo(mensaje, nombre):
    """Qué hacer después de un error, en palabras sencillas."""
    reintentar = (f"Para volver a intentarlo, mueve data/errores/{nombre}.wav (o la grabación nueva) "
                  "a data/bandeja/.")
    if "en silencio" in mensaje:
        return "Graba otra vez revisando la entrada de micro en GarageBand. " + reintentar
    if "Se pisan" in mensaje or "se sale del clip" in mensaje or "plano_max" in mensaje:
        return "Hay que mover o acortar una marca [plano] en guion.md (pídeme que lo mire). " + reintentar
    if "No hay vídeos ni fotos" in mensaje:
        return "Falta material del tema en la biblioteca, o el nombre de la grabación no coincide con la receta. " + reintentar
    return "Pídeme que mire el error (ver_error) y lo arreglamos. " + reintentar


def _pagina():
    e = _estado
    trabajando = e["estado"] == "procesando"
    iconos = {"hecho": "✓", "ahora": "●", "pendiente": "○", "saltado": "–", "error": "✕"}
    pasos = "\n".join(f'<li class="{p["estado"]}"><span class="icono">{iconos[p["estado"]]}</span>'
                      f'{html.escape(p["texto"])}</li>' for p in e["pasos"])
    titulos = {"procesando": "Creando el short…", "listo": "¡Short listo!", "error": "Ha fallado"}
    suele = f"Suele tardar unos {e['suele_tardar_min']:g} min." if e.get("suele_tardar_min") else ""
    extra = ""
    if e["estado"] == "error":
        extra = (f'<div class="aviso"><strong>Qué ha pasado:</strong> {html.escape(e["mensaje"])}'
                 f'<p><strong>Qué hacer:</strong> {html.escape(consejo(e["mensaje"], e["short"]))}</p>'
                 f'<p class="detalle">Detalles técnicos: {html.escape(e["log"])}</p></div>')
    elif e["estado"] == "listo":
        video = "../" + e["video"].split("data/", 1)[-1]
        extra = (f'<div class="listo">Está en <code>{html.escape(e["video"])}</code> y se abre solo. '
                 'Revísalo y, si está bien, muévelo a data/listos/.</div>'
                 f'<video src="{html.escape(video)}" controls></video>')
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
{'<meta http-equiv="refresh" content="1">' if trabajando else ''}
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(e['short'])} · progreso</title>
<style>
:root {{ --fondo:#f6f7fb; --tarjeta:#fff; --texto:#14213D; --suave:#6b7280; --barra:#FFC93C; --bien:#16a34a; --mal:#dc2626; --borde:#e5e7eb; }}
@media (prefers-color-scheme: dark) {{ :root {{ --fondo:#0f1626; --tarjeta:#18223a; --texto:#f3f4f6; --suave:#9ca3af; --borde:#2b3756; }} }}
body {{ margin:0; font-family:-apple-system,system-ui,sans-serif; background:var(--fondo); color:var(--texto); }}
main {{ max-width:560px; margin:40px auto; padding:28px; background:var(--tarjeta); border-radius:16px; border:1px solid var(--borde); }}
h1 {{ margin:0 0 4px; font-size:24px; }} .short {{ color:var(--suave); margin:0 0 20px; }}
.barra {{ height:22px; border-radius:11px; background:var(--borde); overflow:hidden; }}
.relleno {{ height:100%; width:{e['porcentaje']}%; background:var(--barra); transition:width .5s; }}
.procesando .relleno {{ background-image:repeating-linear-gradient(45deg,rgba(255,255,255,.35) 0 10px,transparent 10px 20px); }}
.listo-pagina .relleno {{ background:var(--bien); }} .error-pagina .relleno {{ background:var(--mal); }}
.datos {{ display:flex; justify-content:space-between; color:var(--suave); margin:8px 0 18px; font-size:14px; }}
ul {{ list-style:none; padding:0; margin:0; }} li {{ padding:6px 0; color:var(--suave); }}
li.hecho {{ color:var(--bien); }} li.ahora {{ color:var(--texto); font-weight:600; }} li.error {{ color:var(--mal); font-weight:600; }}
.icono {{ display:inline-block; width:24px; }}
.aviso {{ margin-top:18px; padding:14px; border-radius:10px; background:rgba(220,38,38,.1); border:1px solid var(--mal); }}
.detalle {{ color:var(--suave); font-size:13px; }}
.listo {{ margin-top:18px; padding:14px; border-radius:10px; background:rgba(22,163,74,.12); border:1px solid var(--bien); }}
video {{ width:100%; margin-top:14px; border-radius:10px; max-height:60vh; background:#000; }}
</style></head>
<body class="{e['estado']}-pagina {e['estado']}"><main>
<h1>{titulos[e['estado']]}</h1><p class="short">{html.escape(e['short'])}</p>
<div class="barra"><div class="relleno"></div></div>
<div class="datos"><span>{e['porcentaje']} %</span><span id="tiempo"></span><span>{suele}</span></div>
<ul>{pasos}</ul>{extra}
</main>
<script>
const inicio = {e['inicio']}, fin = {e['fin'] or 'null'};
const s = Math.max(0, Math.round((fin || Date.now() / 1000) - inicio));
document.getElementById("tiempo").textContent = Math.floor(s / 60) + " min " + String(s % 60).padStart(2, "0") + " s";
</script></body></html>
"""
