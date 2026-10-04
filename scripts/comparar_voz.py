"""Prueba controlada del sonido de la voz: varias tomas, cada una procesada con la cadena
actual y con variantes que cambian una sola cosa, todas al mismo volumen para
compararlas de forma justa. No cambia config/por_defecto.json: solo lee su cadena.

Uso:
  python comparar_voz.py                      # data/pruebas/voz/toma_*.wav
  python comparar_voz.py --calibrar           # elegir el umbral del de-esser
  python comparar_voz.py --umbral-deesser 20 data/archivo/007-cambio_hora.wav

Cada toma tiene que empezar con unos segundos de silencio (4 en la prueba): de ahí se
mide el ruido de fondo. Resultado en data/pruebas/voz/: versiones/*.wav, medidas.json y
comparar.html (con escucha a ciegas).

Medidas (todas con la ponderación K de la norma EBU R128, la de los LUFS):
- ruido: mediana del volumen momentáneo (ventanas de 0,4 s) del silencio inicial;
- voz: volumen integrado desde que empieza la voz;
- voz/ruido: voz - ruido, en dB (cuanto más, mejor);
- pico: pico real (true peak) de la voz, en dBTP.
"""
import argparse
import json
import re
import statistics
from pathlib import Path

from crear_short import RAIZ
from pasos.utilidades import ejecutar
from pasos.voz import detectar_voz

CARPETA = RAIZ / "data" / "pruebas" / "voz"
VERSIONES = CARPETA / "versiones"
OBJETIVO = -16.0         # LUFS de todas las versiones, para compararlas igual de fuertes
TECHO = -1.0             # dBTP: si al igualar una versión pasa de aquí, se limita
UMBRAL_SILENCIO = "-40dB"  # para encontrar dónde acaba el silencio inicial (el del vigilante)
SILENCIO_ANTES = 1.0     # segundos de silencio que se dejan antes de la voz al escuchar
RUIDO_DESDE = 0.5        # el ruido de la sala se mide desde aquí (el clic de empezar a grabar queda fuera)
# Umbral del de-esser, elegido con --calibrar (grabación de 007, 2026-10-04). En FFmpeg 6.1 funciona
# al revés de lo que dice su nombre: 0 no hace nada y cuanto más alto, más baja (con 5 ya quita
# 16 dB). Con 0,5 la zona de las eses baja 4 dB en los silbidos y 1,5 dB en el resto de la voz.
# El filtro deesser de FFmpeg se probó y apenas hacía nada (0,5 dB).
UMBRAL_DEESSER = 0.5
ZONA_ESES = (5000, 9000)  # Hz donde están los silbidos de las "s"
VENTANA = 0.05           # segundos de cada ventana al medir las pausas


def cadena_actual():
    config = json.loads((RAIZ / "config" / "por_defecto.json").read_text(encoding="utf-8"))
    return config["voz"]["cadena"]


def deesser(umbral):
    """Ecualizador dinámico: baja la zona de 6,5 kHz solo cuando una "s" la dispara."""
    return (f"adynamicequalizer=dfrequency=6500:dqfactor=1.5:tfrequency=6500:tqfactor=1.5:"
            f"ratio=3:attack=1:release=50:threshold={umbral}")


def variantes(cadena, umbral):
    """Las versiones a comparar: nombre -> (descripción, filtros). Cada variante cambia una
    sola cosa de la cadena actual. Si la cadena cambia y ya no tiene el filtro que hay que
    tocar, falla en vez de comparar algo que no es."""
    filtros = cadena.split(",")

    def posicion(prefijo):
        encontrados = [i for i, f in enumerate(filtros) if f.startswith(prefijo)]
        if len(encontrados) != 1:
            raise SystemExit(f"La cadena actual no tiene un solo filtro '{prefijo}': revisa las variantes")
        return encontrados[0]

    menos_ruido = list(filtros)
    i = posicion("afftdn=")
    menos_ruido[i] = re.sub(r"nr=[\d.]+", "nr=7", menos_ruido[i])
    con_deesser = list(filtros)
    con_deesser.insert(posicion("treble=") + 1, deesser(umbral))
    cuerpo = list(filtros)
    cuerpo[posicion("bass=")] = "bass=g=4:f=150"
    sin_loudnorm = [f for f in filtros if not f.startswith("loudnorm=")]
    versiones = {
        "sin_procesar": ("Sin procesar (solo a mono)", ""),
        "actual": ("Cadena actual", cadena),
        "menos_ruido": ("(a) Menos reducción de ruido: afftdn nr=7 en vez de 14", ",".join(menos_ruido)),
        "deesser": (f"(b) De-esser a 6,5 kHz después de los agudos (umbral {umbral})", ",".join(con_deesser)),
        "cuerpo": ("(c) Más cuerpo: bass g=4 a 150 Hz en vez de g=2 a 120 Hz", ",".join(cuerpo)),
        # El loudnorm dinámico arranca con demasiada ganancia y sube el ruido de antes de la
        # voz unos 40 dB; sin él, el volumen lo pone una ganancia fija (aquí, igualar())
        "sin_loudnorm": ("(d) Sin el loudnorm dinámico del final (volumen con una ganancia fija)",
                         ",".join(sin_loudnorm)),
    }
    if len(sin_loudnorm) == len(filtros):      # la cadena ya no lo tiene (desde la parte 10)
        del versiones["sin_loudnorm"]
    return versiones


def procesar(original, filtros, salida, desde):
    """Como voz.py: recorta el silencio inicial y pasa a mono antes de la cadena. Deja
    SILENCIO_ANTES segundos de silencio delante de la voz (desde), que se escuchan y donde
    se mide el ruido que queda tras el procesado."""
    ejecutar(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{desde:.3f}", "-i", original,
              "-af", "aformat=channel_layouts=mono" + ("," + filtros if filtros else ""),
              "-ac", "1", "-ar", "48000", "-c:a", "pcm_s24le", salida])


def numero(texto):
    return float("-inf") if "inf" in texto else float(texto)


def ruido(archivo, desde, hasta):
    """Volumen del ruido de fondo entre dos instantes de silencio: la mediana del volumen
    momentáneo (ventanas de 0,4 s). None si el tramo es demasiado corto."""
    if hasta - desde < 0.6:
        return None
    texto = ejecutar(["ffmpeg", "-hide_banner", "-nostats", "-i", archivo, "-af",
                      f"aformat=channel_layouts=mono,atrim={desde:.3f}:{hasta:.3f},ebur128=framelog=info",
                      "-f", "null", "-"]).stderr
    momentaneo = [numero(m) for m in re.findall(r"\bM:\s*(-?inf|-?[\d.]+)", texto)][3:]  # 0,4 s llenos
    return round(statistics.median(momentaneo), 1) if momentaneo else None


def medir(archivo, inicio, ruido_desde):
    """Ruido del silencio inicial, volumen de la voz (desde inicio), relación entre los dos y pico."""
    texto = ejecutar(["ffmpeg", "-hide_banner", "-nostats", "-i", archivo, "-af",
                      f"aformat=channel_layouts=mono,atrim=start={inicio:.3f},ebur128=peak=true",
                      "-f", "null", "-"]).stderr
    resumen = texto[texto.rfind("Summary:"):]
    medidas = {"ruido": ruido(archivo, ruido_desde, inicio - 0.2),
               "voz": numero(re.search(r"I:\s*(-?inf|-?[\d.]+) LUFS", resumen).group(1)),
               "pico": numero(re.search(r"True peak:\s*Peak:\s*(-?inf|-?[\d.]+)", resumen, re.S).group(1))}
    medidas["voz_ruido"] = round(medidas["voz"] - medidas["ruido"], 1) if medidas["ruido"] is not None else None
    return medidas


def igualar(entrada, salida):
    """Lleva la versión a OBJETIVO LUFS con una ganancia exacta (dos pasadas, como el
    render). Si el pico pasara de TECHO, limita, y devuelve cuántos dB recorta."""
    texto = ejecutar(["ffmpeg", "-hide_banner", "-nostats", "-i", entrada, "-af", "ebur128=peak=true",
                      "-f", "null", "-"]).stderr
    resumen = texto[texto.rfind("Summary:"):]
    integrado = numero(re.search(r"I:\s*(-?[\d.]+) LUFS", resumen).group(1))
    pico = numero(re.search(r"True peak:\s*Peak:\s*(-?inf|-?[\d.]+)", resumen, re.S).group(1))
    ganancia = OBJETIVO - integrado
    filtros = f"volume={ganancia:.2f}dB"
    limitada = round(max(0.0, pico + ganancia - TECHO), 1)     # dB de pico que recorta el limitador
    if limitada:
        filtros += f",alimiter=limit={10 ** (TECHO / 20):.4f}:attack=5:release=50:level=disabled"
    ejecutar(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", entrada, "-af", filtros,
              "-ar", "48000", "-c:a", "pcm_s16le", salida])
    return round(ganancia, 1), limitada


def niveles(archivo, filtros="", desde=0.0):
    """Volumen (dBFS, RMS) en ventanas de 50 ms: {número de ventana: nivel}. 'desde' es el
    segundo de la toma original en que empieza este archivo, para alinear las ventanas."""
    texto = ejecutar(["ffmpeg", "-hide_banner", "-nostats", "-i", archivo, "-af",
                      "aformat=channel_layouts=mono,aresample=48000," + (filtros + "," if filtros else "")
                      + "asetnsamples=n=2400:p=0,astats=metadata=1:reset=1,"
                      "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
                      "-f", "null", "-"]).stdout
    pares = re.findall(r"pts_time:([\d.]+)\s+lavfi.astats.Overall.RMS_level=(-?inf|-?[\d.]+)", texto)
    return {round((float(tiempo) + desde) / VENTANA): numero(nivel) for tiempo, nivel in pares}


def tramos_de_la_toma(toma, inicio):
    """Qué ventanas de la toma original son voz y cuáles pausa entre frases, según su nivel
    respecto al ruido de la sala. Se decide con la toma original para que todas las
    versiones se midan en los mismos instantes."""
    original = niveles(toma)
    sala = [n for v, n in original.items() if RUIDO_DESDE <= v * VENTANA <= min(inicio - 0.2, 3.5)]
    if len(sala) < 10:
        return None
    sala = statistics.median(sala)
    voz = {v for v, n in original.items() if v * VENTANA >= inicio and n > sala + 30}
    pausas = {v for v, n in original.items() if v * VENTANA >= inicio + 0.5 and n < sala + 6}
    return (voz, pausas) if len(voz) >= 20 and len(pausas) >= 6 else None


def voz_ruido_en_pausas(archivo, desde, tramos):
    """Voz/ruido donde se oye de verdad, en las pausas entre frases: mediana de las ventanas
    de voz menos mediana de las de pausa (dB)."""
    if not tramos:
        return None
    voz, pausas = tramos
    medido = niveles(archivo, desde=desde)
    en_voz = [medido[v] for v in voz if v in medido and medido[v] != float("-inf")]
    en_pausa = [medido[v] for v in pausas if v in medido and medido[v] != float("-inf")]
    if not en_voz or not en_pausa:
        return None
    return round(statistics.median(en_voz) - statistics.median(en_pausa), 1)


def niveles_eses(archivo):
    """Volumen (dB) de la zona de las eses en ventanas de 50 ms."""
    texto = ejecutar(["ffmpeg", "-hide_banner", "-nostats", "-i", archivo, "-af",
                      f"highpass=f={ZONA_ESES[0]},lowpass=f={ZONA_ESES[1]},asetnsamples=n=2400:p=0,"
                      "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
                      "-f", "null", "-"]).stdout
    return [numero(v) for v in re.findall(r"RMS_level=(-?inf|-?[\d.]+)", texto)]


def efecto_deesser(actual, con_deesser):
    """Cuánto baja la zona de las eses en las ventanas con silbido (el 15 % más fuerte en la
    versión actual) y en el resto de la voz. Las dos versiones ya están igualadas y
    alineadas: misma toma, mismo recorte."""
    a, d = niveles_eses(actual), niveles_eses(con_deesser)
    pares = [(x, y) for x, y in zip(a, d) if x > -60 and y != float("-inf")]
    if len(pares) < 20:
        return None
    corte = sorted(x for x, _ in pares)[int(len(pares) * 0.85)]
    eses = [x - y for x, y in pares if x >= corte]
    resto = [x - y for x, y in pares if x < corte]
    return {"eses": round(statistics.median(eses), 1), "resto": round(statistics.median(resto), 1)}


def inicio_voz(toma, manual=None):
    """Dónde empieza la voz: el final del silencio inicial (a -40 dB, como el vigilante),
    o el segundo que se indique con --inicio si la detección falla por el ruido."""
    return manual if manual is not None else detectar_voz(toma, UMBRAL_SILENCIO, 0)[0]


def calibrar(toma, cadena, umbrales, manual=None):
    print(f"Calibrando el de-esser con {toma.name}: dB que baja la zona de {ZONA_ESES[0]}-{ZONA_ESES[1]} Hz")
    desde = max(0.0, inicio_voz(toma, manual) - SILENCIO_ANTES)
    VERSIONES.mkdir(parents=True, exist_ok=True)
    tmp, base = VERSIONES / "_calibrar.wav", VERSIONES / "_calibrar_actual.wav"
    procesar(toma, cadena, tmp, desde)
    igualar(tmp, base)
    for umbral in umbrales:
        procesar(toma, variantes(cadena, umbral)["deesser"][1], tmp, desde)
        salida = VERSIONES / f"_calibrar_{umbral}.wav"
        igualar(tmp, salida)
        efecto = efecto_deesser(base, salida)
        print(f"  umbral {umbral:>5g}: eses {efecto['eses']:+.1f} dB · resto {efecto['resto']:+.1f} dB")
        salida.unlink()
    tmp.unlink()
    base.unlink()


def comparar(tomas, cadena, umbral, manual=None):
    VERSIONES.mkdir(parents=True, exist_ok=True)
    resultado = []
    for toma in tomas:
        nombre = toma.stem
        inicio = inicio_voz(toma, manual)
        desde = max(0.0, inicio - SILENCIO_ANTES)
        # La toma tal cual: el ruido de la sala, en el silencio inicial (hasta 3,5 s)
        sala = medir(toma, inicio, RUIDO_DESDE) | {"ruido": ruido(toma, RUIDO_DESDE, min(inicio - 0.2, 3.5))}
        if sala["ruido"] is not None:
            sala["voz_ruido"] = round(sala["voz"] - sala["ruido"], 1)
        print(f"== {nombre}: la voz empieza en {inicio:.2f} s · ruido de la sala {sala['ruido']} LUFS · "
              f"voz {sala['voz']} LUFS · voz/ruido {sala['voz_ruido']} dB · pico {sala['pico']} dBTP")
        if inicio < 3.5:
            print("   AVISO: menos de 3,5 s de silencio al principio: el ruido se mide con menos tiempo"
                  if sala["ruido"] is not None else
                  "   AVISO: sin silencio al principio: no se puede medir el ruido (prueba --inicio)")
        tramos = tramos_de_la_toma(toma, inicio)
        if not tramos:
            print("   AVISO: no se distinguen bien las pausas: no se mide la voz/ruido de las versiones")
        versiones = []
        for clave, (descripcion, filtros) in variantes(cadena, umbral).items():
            completa = VERSIONES / f"_{nombre}_{clave}.wav"
            procesar(toma, filtros, completa, desde)
            medidas = medir(completa, inicio - desde, 0.0)
            # El ruido del segundo de silencio inicial no sirve tras la cadena: el loudnorm
            # dinámico arranca con muchísima ganancia y lo sube hasta 40 dB. Se mide en las pausas.
            medidas["ruido_arranque"] = medidas.pop("ruido")
            medidas.pop("voz_ruido")
            medidas["voz_ruido_pausas"] = voz_ruido_en_pausas(completa, desde, tramos)
            archivo = VERSIONES / f"{nombre}_{clave}.wav"
            ganancia, limitada = igualar(completa, archivo)
            completa.unlink()
            versiones.append({"clave": clave, "descripcion": descripcion,
                              "archivo": f"versiones/{archivo.name}", **medidas,
                              "ganancia": ganancia, "limitada": limitada})
            print(f"   {clave:<13} voz {medidas['voz']} LUFS · voz/ruido en las pausas "
                  f"{medidas['voz_ruido_pausas']} dB · pico {medidas['pico']} dBTP · ruido en el arranque "
                  f"{medidas['ruido_arranque']} LUFS" + (f" · el limitador recorta {limitada} dB" if limitada else ""))
        efecto = efecto_deesser(VERSIONES / f"{nombre}_actual.wav", VERSIONES / f"{nombre}_deesser.wav")
        if efecto:
            print(f"   de-esser: la zona de las eses baja {efecto['eses']} dB en los silbidos "
                  f"y {efecto['resto']} dB en el resto")
        resultado.append({"toma": nombre, "inicio_voz": round(inicio, 2), "sala": sala,
                          "versiones": versiones, "deesser": efecto})
    return resultado


PAGINA = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Prueba de voz</title>
<style>
:root { --fondo: #fbfaf7; --texto: #1d1d1f; --suave: #6b6b70; --borde: #e3e1dc; --marca: #14213D; --resalte: #FFC93C; }
@media (prefers-color-scheme: dark) { :root { --fondo: #15171c; --texto: #ececef; --suave: #9a9aa2; --borde: #2c2f37; --marca: #FFC93C; } }
body { background: var(--fondo); color: var(--texto); font: 16px/1.5 -apple-system, system-ui, sans-serif; margin: 0; }
main { max-width: 980px; margin: 0 auto; padding: 24px 16px 64px; }
h1 { font-size: 26px; margin: 0 0 4px; } h2 { font-size: 19px; margin: 36px 0 8px; }
p.nota { color: var(--suave); margin: 0 0 16px; }
.botones { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 16px 0; }
button, select { font: inherit; padding: 6px 12px; border-radius: 8px; border: 1px solid var(--borde); background: transparent; color: var(--texto); cursor: pointer; }
button.principal { background: var(--marca); color: var(--fondo); border-color: var(--marca); }
.tabla { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid var(--borde); vertical-align: middle; }
th { color: var(--suave); font-weight: 600; } td.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
audio { width: 240px; height: 36px; }
.muestra { display: grid; grid-template-columns: 110px 1fr; gap: 6px 12px; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--borde); }
.muestra textarea { grid-column: 2; font: inherit; font-size: 14px; padding: 6px; border-radius: 8px; border: 1px solid var(--borde); background: transparent; color: var(--texto); min-height: 34px; }
.revelado { color: var(--marca); font-weight: 600; }
.oculto { display: none; }
@media (max-width: 600px) { audio { width: 100%; } .muestra { grid-template-columns: 1fr; } .muestra textarea { grid-column: 1; } }
</style>
</head>
<body>
<main>
<h1>Prueba de voz</h1>
<p class="nota">Todas las versiones están igualadas a OBJETIVO LUFS, para compararlas igual de fuertes.</p>
<div class="botones">
  <select id="grupo"></select>
  <button class="principal" id="empezar">Escuchar a ciegas</button>
  <button id="revelar" class="oculto">Revelar</button>
  <button id="volver" class="oculto">Volver a la tabla</button>
</div>
<div id="ciegas" class="oculto"></div>
<div id="normal"></div>
</main>
<script>
const DATOS = __DATOS__;
const OBJ = __OBJETIVO__;
const $ = (s) => document.querySelector(s);
const fmt = (v, d = 1) => v === null || v === undefined ? "—" : (v === -Infinity ? "−∞" : v.toFixed(d).replace(".", ","));
const guardar = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
const leer = (k) => { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } };

function tablaNormal() {
  $("#normal").innerHTML = DATOS.map((t) => `
    <h2>${t.toma}</h2>
    <p class="nota">Toma sin procesar: ruido de la sala <b>${fmt(t.sala.ruido)} LUFS</b>, voz <b>${fmt(t.sala.voz)} LUFS</b>, voz/ruido <b>${fmt(t.sala.voz_ruido)} dB</b>, pico <b>${fmt(t.sala.pico)} dBTP</b> (la voz empieza en ${fmt(t.inicio_voz, 2)} s). En la tabla, <b>voz/ruido en las pausas</b> compara las ventanas de voz con las pausas entre frases (las mismas en todas las versiones; cuanto más, mejor). <b>Ruido en el arranque</b>: el segundo antes de la voz, que la cadena actual sube mucho porque su loudnorm empieza con demasiada ganancia.${t.deesser ? ` De-esser: la zona de las eses baja ${fmt(t.deesser.eses)} dB en los silbidos y ${fmt(t.deesser.resto)} dB en el resto.` : ""}</p>
    <div class="tabla"><table>
      <tr><th>Versión</th><th>Escuchar</th><th>Voz/ruido en las pausas (dB)</th><th>Voz (LUFS)</th><th>Pico (dBTP)</th><th>Ruido en el arranque (LUFS)</th></tr>
      ${t.versiones.map((v) => `<tr><td>${v.descripcion}${v.limitada ? ` · <i>limitador: −${fmt(v.limitada)} dB</i>` : ""}</td>
        <td><audio controls preload="none" src="${v.archivo}"></audio></td>
        <td class="n">${fmt(v.voz_ruido_pausas)}</td><td class="n">${fmt(v.voz)}</td>
        <td class="n">${fmt(v.pico)}</td><td class="n">${fmt(v.ruido_arranque)}</td></tr>`).join("")}
    </table></div>`).join("");
}

function opciones() {
  const grupos = [["todas", "Todas las versiones"], ...DATOS.map((t) => [t.toma, `Solo ${t.toma}`]),
                  ...DATOS[0].versiones.map((v) => ["v:" + v.clave, `Las tomas con: ${v.clave}`])];
  $("#grupo").innerHTML = grupos.map(([k, n]) => `<option value="${k}">${n}</option>`).join("");
}

function elegidas(grupo) {
  const todas = DATOS.flatMap((t) => t.versiones.map((v) => ({ ...v, toma: t.toma })));
  if (grupo === "todas") return todas;
  if (grupo.startsWith("v:")) return todas.filter((v) => v.clave === grupo.slice(2));
  return todas.filter((v) => v.toma === grupo);
}

function barajar(lista) {
  const l = [...lista];
  for (let i = l.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [l[i], l[j]] = [l[j], l[i]]; }
  return l;
}

let sesion = null;
function empezar() {
  const grupo = $("#grupo").value;
  const anterior = leer("voz:" + grupo);
  const lista = elegidas(grupo);
  sesion = anterior && anterior.orden.length === lista.length ? anterior
         : { grupo, orden: barajar(lista).map((v) => v.archivo), notas: {}, textos: {} };
  guardar("voz:" + grupo, sesion);
  pintarCiegas(false);
}

function pintarCiegas(revelado) {
  const porArchivo = Object.fromEntries(elegidas(sesion.grupo).map((v) => [v.archivo, v]));
  let orden = sesion.orden;
  if (revelado) orden = [...orden].sort((a, b) => (sesion.notas[b] || 0) - (sesion.notas[a] || 0));
  $("#ciegas").innerHTML = `<p class="nota">${revelado ? "Ordenadas por tu nota." : "Puntúa cada muestra del 1 al 5. El orden es aleatorio y se guarda en este navegador."}</p>` +
    orden.map((a) => {
      const n = sesion.orden.indexOf(a) + 1, v = porArchivo[a];
      return `<div class="muestra"><b>Muestra ${n}</b>
        <div><audio controls preload="none" src="${a}"></audio>
        <select data-a="${a}"><option value="">Nota</option>${[1, 2, 3, 4, 5].map((k) => `<option ${sesion.notas[a] == k ? "selected" : ""}>${k}</option>`).join("")}</select>
        ${revelado ? `<span class="revelado">${v.toma} · ${v.descripcion}</span>` : ""}</div>
        <textarea data-t="${a}" placeholder="Nota (opcional)">${sesion.textos[a] || ""}</textarea></div>`;
    }).join("");
  $("#ciegas").querySelectorAll("select").forEach((s) => s.onchange = () => { sesion.notas[s.dataset.a] = Number(s.value) || 0; guardar("voz:" + sesion.grupo, sesion); });
  $("#ciegas").querySelectorAll("textarea").forEach((t) => t.oninput = () => { sesion.textos[t.dataset.t] = t.value; guardar("voz:" + sesion.grupo, sesion); });
  for (const [id, ver] of [["#ciegas", true], ["#normal", false], ["#revelar", !revelado], ["#volver", true], ["#empezar", false]])
    $(id).classList.toggle("oculto", !ver);
}

$("#empezar").onclick = empezar;
$("#revelar").onclick = () => pintarCiegas(true);
$("#volver").onclick = () => { for (const [id, ver] of [["#ciegas", false], ["#normal", true], ["#revelar", false], ["#volver", false], ["#empezar", true]]) $(id).classList.toggle("oculto", !ver); };
document.addEventListener("play", (e) => document.querySelectorAll("audio").forEach((a) => { if (a !== e.target) a.pause(); }), true);
opciones();
tablaNormal();
</script>
</body>
</html>
"""


def pagina(resultado):
    datos = json.dumps(resultado, ensure_ascii=False).replace("-Infinity", "null").replace("</", "<\\/")
    texto = (PAGINA.replace("__DATOS__", datos).replace("__OBJETIVO__", f"{OBJETIVO:g}")
             .replace("OBJETIVO LUFS", f"{OBJETIVO:g} LUFS"))
    (CARPETA / "comparar.html").write_text(texto, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Compara tomas de voz y cadenas de procesado")
    parser.add_argument("tomas", nargs="*", help="Tomas a comparar (por defecto, data/pruebas/voz/toma_*.wav)")
    parser.add_argument("--umbral-deesser", type=float, default=UMBRAL_DEESSER)
    parser.add_argument("--inicio", type=float, help="Segundo en que empieza la voz, si no se detecta solo")
    parser.add_argument("--calibrar", action="store_true", help="Prueba varios umbrales del de-esser")
    parser.add_argument("--umbrales", default="0,1,2,5,10", help="Umbrales que prueba --calibrar")
    args = parser.parse_args()

    tomas = [Path(t) if Path(t).is_absolute() else RAIZ / t for t in args.tomas] \
        or sorted(CARPETA.glob("toma_*.wav"))
    if not tomas:
        raise SystemExit("No hay tomas en data/pruebas/voz/ (toma_actual.wav, toma_manta.wav, toma_cerca.wav)")
    cadena = cadena_actual()
    if args.calibrar:
        calibrar(tomas[0], cadena, [float(u) for u in args.umbrales.split(",")], args.inicio)
        return
    resultado = comparar(tomas, cadena, args.umbral_deesser, args.inicio)
    (CARPETA / "medidas.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    pagina(resultado)
    print(f"\nPágina: {(CARPETA / 'comparar.html').relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
