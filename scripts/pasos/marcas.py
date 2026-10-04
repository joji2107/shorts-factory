"""Marcas de montaje del guion (fábrica 2.0): van entre corchetes, antes de la palabra
en la que actúan, y no se leen en voz alta.

  [respiro 3]                 3 s de silencio en ese hueco (sin número: respiros.segundos)
  [plano volcan_03 12.5 6]    el clip volcan_03, desde su segundo 12,5, durante 6 s

Para saber en qué momento de la grabación cae cada marca, se cuenta cuántas palabras
dichas hay antes de ella en el guion y se busca esa posición en la transcripción con la
misma alineación que usan los subtítulos (alinear). Así una palabra repetida no confunde
nada y las marcas siguen en su sitio aunque se vuelva a grabar.
"""
import re

from .subtitulos import alinear, palabras_de_texto, seccion_guion, solo_lo_que_se_dice

MARCA = re.compile(r"\[(respiro|plano)\b([^\]]*)\]", re.I)


def leer_marcas(ruta):
    """Las marcas del guion, en orden: {"tipo", "argumentos", "posicion", "contexto"}.
    'posicion' es cuántas palabras dichas hay antes de la marca (la palabra del guion que
    va justo después). 'contexto' son esas palabras siguientes, para los mensajes."""
    if not ruta.exists():
        return []
    texto = seccion_guion(ruta)
    marcas = []
    for encontrada in MARCA.finditer(texto):
        posicion = len(palabras_de_texto(solo_lo_que_se_dice(texto[:encontrada.start()])))
        siguientes = palabras_de_texto(solo_lo_que_se_dice(texto[encontrada.end():]))[:3]
        marcas.append({
            "tipo": encontrada.group(1).lower(),
            "argumentos": encontrada.group(2).split(),
            "posicion": posicion,
            "contexto": " ".join(p[2] for p in siguientes) or "(final)",
        })
    return marcas


def respiros_del_guion(ruta, segundos_por_defecto):
    """[(posicion, segundos, contexto)] de las marcas [respiro N]."""
    resultado = []
    for m in leer_marcas(ruta):
        if m["tipo"] != "respiro":
            continue
        try:
            segundos = float(m["argumentos"][0].replace(",", ".")) if m["argumentos"] else segundos_por_defecto
        except ValueError:
            raise RuntimeError(f"[respiro {' '.join(m['argumentos'])}] antes de «{m['contexto']}»: "
                               "tiene que ser [respiro] o [respiro N], con N en segundos") from None
        resultado.append((m["posicion"], segundos, m["contexto"]))
    return resultado


def planos_del_guion(ruta):
    """[(posicion, clip, desde, largo, contexto)] de las marcas [plano clip desde largo]."""
    resultado = []
    for m in leer_marcas(ruta):
        if m["tipo"] != "plano":
            continue
        try:
            clip, desde, largo = m["argumentos"]
            resultado.append((m["posicion"], clip, float(desde.replace(",", ".")),
                              float(largo.replace(",", ".")), m["contexto"]))
        except ValueError:
            raise RuntimeError(f"[plano {' '.join(m['argumentos'])}] antes de «{m['contexto']}»: "
                               "tiene que ser [plano clip desde largo], por ejemplo [plano volcan_03 12.5 6]") from None
    return resultado


def en_la_transcripcion(posiciones, palabras, guion):
    """Para cada posición del guion, el índice de palabras.json de la palabra dicha que va
    justo después de la marca (len(palabras) si la marca está al final).
    Si esa palabra se transcribió distinta (Whisper oyó mal), se usa la siguiente a la
    anterior si esa coincide; si no, la siguiente palabra igual en los dos textos, y si no
    hay ninguna, la anterior igual + 1. Devuelve None para las que no se pueden situar."""
    transcritas, tramos = alinear(palabras, guion)
    # Para cada palabra del guion que coincide con la transcripción: su índice en palabras.json
    iguales = {}
    for operacion, a1, a2, b1, b2 in tramos:
        if operacion == "equal" or (operacion == "replace" and a2 - a1 == b2 - b1):
            for k in range(a2 - a1):
                iguales[a1 + k] = transcritas[b1 + k][0]

    resultado = []
    for posicion in posiciones:
        if posicion >= len(guion):
            resultado.append(len(palabras))
            continue
        if posicion in iguales:
            resultado.append(iguales[posicion])
            continue
        if posicion - 1 in iguales:                  # la de antes sí coincide: la siguiente a ella
            resultado.append(iguales[posicion - 1] + 1)
            continue
        despues = [iguales[p] for p in range(posicion, len(guion)) if p in iguales]
        antes = [iguales[p] for p in range(posicion - 1, -1, -1) if p in iguales]
        if despues:
            resultado.append(despues[0])
        elif antes:
            resultado.append(antes[0] + 1)
        else:
            resultado.append(None)
    return resultado
