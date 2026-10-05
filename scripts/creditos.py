"""Créditos y medida de los textos de publicación de un short (shorts/<nombre>/publicacion.md).

1. Mira qué archivos usa el short: los clips de su lista de cortes (cortes.txt de la
   receta o, si no tiene, cortes_auto.txt de data/shorts/; si aún no existe, los clips de
   la receta), la música y los efectos que suenan. Busca su autor en biblioteca/indice.csv.
2. Escribe los créditos en publicacion.md:
   - una línea "Créditos:" sola se sustituye, junto con las líneas que la siguen hasta
     la primera vacía, por la versión larga (autor, fuente y url de cada archivo);
   - una línea que empieza por "Créditos: " (con texto detrás) se sustituye por la
     versión corta, de una sola línea (para X).
   Se puede repetir: vuelve a escribir los mismos créditos.
3. Mide cada bloque ```text con el límite de su plataforma (LIMITES). Un bloque que
   sirve para varias plataformas va en una sección como "## YouTube, Instagram y TikTok"
   y se mide con el límite de cada una. Si alguno se pasa, termina con código 1.

Uso: python scripts/creditos.py 002-caballo
"""
import argparse
import re
import sys
from pathlib import Path

from crear_short import RAIZ, cargar_config
from material import IMAGENES, VIDEOS, leer_indice

# Límites comprobados el 2026-10-03. Clave: (sección ##, apartado ###) de publicacion.md.
# "visible": caracteres que se ven antes de "más"; "url": lo que cuenta cada enlace en X.
LIMITES = {
    ("YouTube", "Título"): {"maximo": 100, "recomendado": 60},
    ("YouTube", "Descripción"): {"maximo": 5000},
    ("YouTube", "Comentario fijado"): {"maximo": 10000},
    ("Instagram", "Descripción"): {"maximo": 2200, "hashtags": 5, "visible": 125},
    ("Instagram", "Comentario fijado"): {"maximo": 2200},
    ("TikTok", "Descripción"): {"maximo": 4000, "visible": 80},
    ("TikTok", "Comentario fijado"): {"maximo": 150},
    ("X", "Post"): {"maximo": 280, "url": 23},
    ("X", "Respuesta"): {"maximo": 280, "url": 23},
}
# Cada línea del bloque de "## Títulos" es una opción de título de YouTube.
LIMITE_TITULOS = LIMITES[("YouTube", "Título")]


def sin_repetir(elementos):
    return list(dict.fromkeys(elementos))


def archivos_usados(nombre):
    """(clips, música, efectos) del short, como nombres de archivo del índice.
    clips está vacío si el short todavía no tiene clips elegidos."""
    config = cargar_config(nombre)
    clips = []
    for lista in (RAIZ / "shorts" / nombre / "cortes.txt",
                  RAIZ / "data" / "shorts" / nombre / "cortes_auto.txt"):
        if lista.is_file():
            clips = sin_repetir(linea.split()[0] for linea in
                                lista.read_text(encoding="utf-8").splitlines() if linea.split())
            break
    else:
        clips = config.get("video", {}).get("clips") or []

    musica = config["musica"]["archivo"]
    efectos = config["efectos"]
    # Con "lista" no se usan los automáticos (igual que en crear_short.py)
    if efectos.get("lista"):
        sonidos = [efecto["archivo"] for efecto in efectos["lista"]]
    elif efectos.get("automaticos"):
        sonidos = efectos.get("archivos", [])
    else:
        sonidos = []
    # Una foto se llama <clip>.jpg en el índice; todo lo demás, <clip>.mp4
    return ([f"{clip}.jpg" if (IMAGENES / f"{clip}.jpg").is_file() and not (VIDEOS / f"{clip}.mp4").is_file()
             else f"{clip}.mp4" for clip in sorted(clips)],
            [Path(musica).name] if musica else [],
            sin_repetir(Path(sonido).name for sonido in sonidos))


def fichas(archivos, indice):
    """La línea del índice de cada archivo."""
    faltan = [archivo for archivo in archivos if archivo not in indice]
    if faltan:
        raise RuntimeError(f"No están en biblioteca/indice.csv: {', '.join(faltan)}")
    return [indice[archivo] for archivo in archivos]


def autores_por_fuente(filas):
    """'A y B (Pixabay); C (Pexels)': cada autor una vez, agrupados por fuente. Si la
    licencia obliga a citarla (CC BY), va con la fuente: 'D (Wikimedia Commons, CC BY 4.0)'."""
    fuentes = {}
    for fila in filas:
        grupo = fila["fuente"]
        if fila.get("licencia", "").startswith("CC BY"):
            grupo += f", {fila['licencia']}"
        fuentes.setdefault(grupo, [])
        if fila["autor"] not in fuentes[grupo]:
            fuentes[grupo].append(fila["autor"])

    def enumerar(nombres):
        return nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " y " + nombres[-1]

    return "; ".join(f"{enumerar(autores)} ({fuente})" for fuente, autores in fuentes.items())


def textos_de_creditos(nombre):
    """(líneas de la versión larga, línea de la versión corta), o None si aún no hay clips."""
    clips, musica, efectos = archivos_usados(nombre)
    if not clips:
        return None
    indice = {fila["archivo"]: fila for fila in leer_indice()}
    clips, musica, efectos = (fichas(grupo, indice) for grupo in (clips, musica, efectos))

    def linea_clip(fila):
        # Con atribución (Commons, NASA...) va el texto exacto que pide su licencia
        tipo = "Foto" if fila["tipo"].strip() == "imagen" else "Vídeo"
        if fila.get("atribucion", "").strip():
            return f"{tipo}: {fila['atribucion'].strip()}"
        return f"{tipo}: {fila['autor']} en {fila['fuente']}, {fila['url']}"

    largo = ["Créditos:"]
    largo += [linea_clip(fila) for fila in clips]
    largo += [f"Música: {fila['autor']} en {fila['fuente']}, {fila['url']}" for fila in musica]
    if efectos:
        largo.append(f"Efectos de sonido: {autores_por_fuente(efectos)}")

    videos = [fila for fila in clips if fila["tipo"].strip() != "imagen"]
    fotos = [fila for fila in clips if fila["tipo"].strip() == "imagen"]
    partes = []
    if videos:
        partes.append(f"vídeos de {autores_por_fuente(videos)}")
    if fotos:
        partes.append(f"fotos de {autores_por_fuente(fotos)}")
    if musica:
        partes.append(f"música de {autores_por_fuente(musica)}")
    if efectos:
        partes.append(f"efectos de {', '.join(sin_repetir(fila['fuente'] for fila in efectos))}")
    corto = "Créditos: " + "; ".join(partes) + "."
    return largo, corto


def poner_creditos(lineas, largo, corto):
    """Sustituye los créditos de publicacion.md. Devuelve (líneas nuevas, cuántos cambió)."""
    resultado, saltando, cambios = [], False, 0
    for linea in lineas:
        if saltando:
            if linea.strip() and not linea.startswith("```"):
                continue        # línea de los créditos anteriores
            saltando = False
        if linea.rstrip() == "Créditos:":
            resultado.extend(largo)
            saltando, cambios = True, cambios + 1
        elif linea.startswith("Créditos: "):
            resultado.append(corto)
            cambios += 1
        else:
            resultado.append(linea)
    return resultado, cambios


def bloques(lineas):
    """Los bloques ```text con su sección (##) y apartado (###)."""
    seccion = apartado = None
    dentro, actual = False, []
    for linea in lineas:
        if dentro:
            if linea.startswith("```"):
                yield seccion, apartado, "\n".join(actual)
                dentro, actual = False, []
            else:
                actual.append(linea)
        elif linea.startswith("```text"):
            dentro = True
        elif linea.startswith("### "):
            apartado = linea[4:].strip()
        elif linea.startswith("## "):
            seccion, apartado = linea[3:].strip(), None


def medir(texto, limite):
    """Devuelve (caracteres, avisos, se_pasa)."""
    largo = len(texto)
    if "url" in limite:         # en X cada enlace cuenta lo mismo, sea como sea de largo
        urls = re.findall(r"https?://\S+", texto)
        largo += sum(limite["url"] - len(url) for url in urls)
    avisos = []
    if "recomendado" in limite and largo > limite["recomendado"]:
        avisos.append(f"más de los {limite['recomendado']} recomendados")
    if "hashtags" in limite:
        cuantos = len(re.findall(r"#\w+", texto))
        if cuantos > limite["hashtags"]:
            avisos.append(f"{cuantos} hashtags, solo cuentan {limite['hashtags']}")
    if "visible" in limite:
        primera = len(texto.splitlines()[0]) if texto else 0
        if primera > limite["visible"]:
            avisos.append(f"la primera línea tiene {primera}; se ven unos {limite['visible']}")
    return largo, avisos, largo > limite["maximo"]


def informe(lineas):
    """Imprime la medida de cada bloque. Devuelve True si alguno se pasa del máximo."""
    alguno_se_pasa = False
    for seccion, apartado, texto in bloques(lineas):
        if seccion == "Títulos":
            medidas = [(f"Título: {titulo}", titulo, LIMITE_TITULOS) for titulo in texto.splitlines() if titulo.strip()]
        else:
            plataformas = re.split(r",\s*|\s+y\s+", seccion or "")
            medidas = [(f"{plataforma} / {apartado}", texto, LIMITES[(plataforma, apartado)])
                       for plataforma in plataformas if (plataforma, apartado) in LIMITES]
        for nombre, contenido, limite in medidas:
            largo, avisos, se_pasa = medir(contenido, limite)
            alguno_se_pasa |= se_pasa
            marca = "SE PASA" if se_pasa else "bien"
            extra = f" ({'; '.join(avisos)})" if avisos else ""
            print(f"  {marca:7} {largo:5} de {limite['maximo']:5}  {nombre}{extra}")
    return alguno_se_pasa


def main():
    parser = argparse.ArgumentParser(description="Créditos y medida de los textos de publicación")
    parser.add_argument("short", help="Carpeta del short, por ejemplo 002-caballo")
    args = parser.parse_args()

    ruta = RAIZ / "shorts" / args.short / "publicacion.md"
    if not ruta.is_file():
        sys.exit(f"No existe {ruta.relative_to(RAIZ)}")
    lineas = ruta.read_text(encoding="utf-8").splitlines()

    creditos = textos_de_creditos(args.short)
    if creditos is None:
        print("Todavía no hay clips elegidos: los créditos se quedan pendientes.")
    else:
        lineas, cambios = poner_creditos(lineas, *creditos)
        if cambios:
            ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
            print(f"Créditos escritos en {cambios} sitios de {ruta.relative_to(RAIZ)}:")
            print("\n".join("  " + linea for linea in creditos[0]))
        else:
            print("No hay ninguna línea 'Créditos:' donde escribirlos.")

    print("\nMedidas:")
    if informe(lineas):
        sys.exit("\nAlgún texto se pasa del límite de su plataforma.")


if __name__ == "__main__":
    main()
