"""Hoja para leer un guion en voz alta: shorts/<nombre>/para_leer.html.

Se genera a partir de guion.md, así que siempre coincide con él: cada frase en su
línea, la **negrita** (énfasis) en color y las (pausa) en gris, para no leerlas.
Arriba van el nombre de la grabación, la duración y las notas de lectura: las líneas
"> ..." de la cabecera de guion.md (por ejemplo, cómo leer el final de un bucle).

Uso: python scripts/para_leer.py 003-rayo
"""
import argparse
import html
import re
import sys

from crear_short import RAIZ

# Las de la estructura clásica y las de la fábrica 2.0 (promesa y recompensa)
PARTES = ("Gancho", "Dato", "Giro", "Remate", "Promesa", "Escalones", "Revelación", "Cierre")

ESTILO = """\
  :root { --texto: #1d1d1f; --suave: #8a8a8e; --fondo: #fbfaf7; --marca: #b4533a; }
  @media (prefers-color-scheme: dark) {
    :root { --texto: #f2f2f2; --suave: #9a9aa0; --fondo: #161618; --marca: #f08a6c; }
  }
  body { background: var(--fondo); color: var(--texto); margin: 0;
         font-family: -apple-system, "Helvetica Neue", Arial, sans-serif; }
  main { max-width: 760px; margin: 0 auto; padding: 32px 20px 80px; }
  .aviso { color: var(--suave); font-size: 15px; line-height: 1.5;
           border-bottom: 1px solid color-mix(in srgb, var(--suave) 35%, transparent);
           padding-bottom: 18px; margin-bottom: 28px; }
  .aviso code { font-size: 14px; }
  .nota { color: var(--texto); }
  h2 { color: var(--suave); font-size: 13px; letter-spacing: .12em; text-transform: uppercase;
       font-weight: 600; margin: 34px 0 6px; }
  p { font-size: 30px; line-height: 1.55; margin: 0 0 14px; }
  strong { color: var(--marca); }
  .pausa { color: var(--suave); font-size: 20px; font-style: italic; white-space: nowrap; }
"""


def marcar(texto):
    """Texto del guion a HTML: **negrita** en <strong> y (pausa) en gris. De las marcas de
    montaje (fábrica 2.0), [plano ...] no sale y [respiro] sale en gris: el silencio lo
    pone el sistema, así que no hay que pararse."""
    texto = re.sub(r"\s*\[plano\b[^\]]*\]", "", texto, flags=re.I)
    texto = re.sub(r"\[respiro\b[^\]]*\]", "\x00", texto, flags=re.I)
    texto = html.escape(texto, quote=False)
    texto = texto.replace("\x00", '<span class="pausa">(respiro: sigue leyendo normal, el silencio lo pone el sistema)</span>')
    texto = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", texto)
    texto = re.sub(r"`(.+?)`", r"<code>\1</code>", texto)
    return texto.replace("(pausa)", '<span class="pausa">(pausa)</span>')


def frases(parrafo):
    """Una frase por línea. Una (pausa) va con la frase anterior, como en un guion, y unos
    puntos suspensivos seguidos de minúscula ("soñar... hasta") no cortan la frase."""
    trozos = re.split(r"(?<=[.?!])\s+(?![a-záéíóúüñ]|\(pausa\))|(?<=\(pausa\))\s+", parrafo.strip())
    return "<br>\n  ".join(marcar(trozo) for trozo in trozos)


def leer_guion(ruta):
    """(cabecera, [(parte, [párrafos])]) de guion.md."""
    cabecera, separador, resto = ruta.read_text(encoding="utf-8").partition("\n## Guion")
    if not separador:
        sys.exit(f"{ruta.relative_to(RAIZ)} no tiene la sección '## Guion'")
    cuerpo = resto.split("\n## ")[0]
    nombres = "|".join(PARTES)
    partes = re.findall(rf"^\*\*({nombres}):\*\*\s*(.*?)(?=^\*\*(?:{nombres}):\*\*|\Z)", cuerpo, re.M | re.S)
    return cabecera, [(parte, [linea for linea in texto.splitlines() if linea.strip()])
                      for parte, texto in partes]


def generar(nombre):
    receta = RAIZ / "shorts" / nombre
    cabecera, partes = leer_guion(receta / "guion.md")

    palabras = re.search(r"\*\*Palabras:\*\*\s*(\d+)", cabecera)
    segundos = re.search(r"\*\*Duración (?:estimada|real):\*\*\s*([\d.,]+)", cabecera)
    resumen = []
    if palabras:
        resumen.append(f"{palabras.group(1)} palabras")
    if segundos:
        resumen.append(f"unos {round(float(segundos.group(1).replace(',', '.')))} segundos")
    notas = " ".join(linea.lstrip("> ").strip() for linea in cabecera.splitlines() if linea.startswith(">"))
    # Un texto que no es un short (una prueba de voz) dice en "**Grabación:**" dónde se guarda
    grabacion = re.search(r"\*\*Grabación:\*\*\s*(.+)", cabecera)
    if grabacion:
        donde = [f"{marcar(grabacion.group(1).strip())}<br>"]
    else:
        donde = [f"Guarda la grabación como <code>{nombre}.wav</code> en <code>data/bandeja/</code>",
                 "(con el vigilante en marcha).<br>",
                 # Prueba de voz (fase 9, parte 10): con el micro cerca, la voz gana 3-4 dB sobre el ruido
                 "<strong>Micro a 10-15 cm</strong> de la boca.<br>"]

    aviso = [f"<strong>{nombre}</strong>{': ' + ', '.join(resumen) if resumen else ''}.<br>",
             *donde,
             '<strong>Negrita</strong> = énfasis · <span class="pausa">(pausa)</span> = respira, no se lee.',
             "Lee a tu ritmo: la duración la marca tu voz."]
    if notas:
        aviso.append(f'<br><span class="nota">{marcar(notas)}</span>')

    cuerpo = []         # un bloque por parte: el título y sus párrafos
    for parte, parrafos in partes:
        cuerpo.append("\n".join([f"  <h2>{parte}</h2>"] + [f"  <p>{frases(parrafo)}</p>" for parrafo in parrafos]))

    pagina = (
        '<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>Para leer: {nombre}</title>\n<style>\n{ESTILO}</style>\n</head>\n<body>\n<main>\n"
        '  <div class="aviso">\n    ' + "\n    ".join(aviso) + "\n  </div>\n\n"
        + "\n\n".join(cuerpo) + "\n</main>\n</body>\n</html>\n"
    )
    salida = receta / "para_leer.html"
    salida.write_text(pagina, encoding="utf-8")
    return salida, len(partes)


def main():
    parser = argparse.ArgumentParser(description="Hoja para leer un guion en voz alta")
    parser.add_argument("short", help="Carpeta del short, por ejemplo 003-rayo")
    args = parser.parse_args()
    salida, cuantas = generar(args.short)
    print(f"Escrita {salida.relative_to(RAIZ)} ({cuantas} partes del guion)")


if __name__ == "__main__":
    main()
