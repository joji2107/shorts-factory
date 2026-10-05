"""Revisa los textos de publicación de un short (shorts/<nombre>/publicacion.md) antes de publicar.

1. Licencias: mira qué archivos usa el short (los clips de su lista de cortes: cortes.txt de
   la receta o, si no tiene, cortes_auto.txt de data/shorts/; si aún no existe, los clips de
   la receta; la música y los efectos que suenan) y busca su licencia en biblioteca/indice.csv.
   Desde la fase 11 los créditos no se escriben en la publicación (la licencia y el autor de
   cada archivo se quedan solo en el índice, en local), así que el short solo puede usar
   material que no obliga a citar al autor: Pixabay, Pexels, dominio público, CC0 y la NASA
   (pide reconocerla, pero no lo exige). Si usa algo CC BY, lo dice y termina con código 1.
2. Mide cada bloque ```text con el límite de su plataforma (LIMITES). Un bloque que sirve
   para varias plataformas va en una sección como "## YouTube, Instagram y TikTok" y se mide
   con el límite de cada una. Si alguno se pasa, termina con código 1.

Uso: python scripts/revisar_publicacion.py 012-protestas_francia
"""
import argparse
import re
import sys
import unicodedata
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
    """La línea del índice de cada archivo. Los nombres se comparan normalizados (NFC): macOS
    escribe la "ñ" de los nombres de archivo como "n" + tilde aparte, y el guion la escribe
    como una sola letra (014: "lluvia_cataluña-003" no se encontraba en el índice)."""
    nfc = lambda texto: unicodedata.normalize("NFC", texto)
    indice = {nfc(nombre): fila for nombre, fila in indice.items()}
    faltan = [archivo for archivo in archivos if nfc(archivo) not in indice]
    if faltan:
        raise RuntimeError(f"No están en biblioteca/indice.csv: {', '.join(faltan)}")
    return [indice[nfc(archivo)] for archivo in archivos]


def licencias_con_problema(nombre):
    """Las filas del índice de los archivos del short que no se pueden publicar sin más: las
    que obligan a citar al autor allí donde se publica (CC BY) y las de licencia desconocida
    ("falta" o vacía: los clips de TikTok de 010 y 014, que antes pasaban como buenas).
    Devuelve (cc_by, desconocidas), o None si el short aún no tiene clips."""
    clips, musica, efectos = archivos_usados(nombre)
    if not clips:
        return None
    indice = {fila["archivo"]: fila for fila in leer_indice()}
    filas = fichas(clips + musica + efectos, indice)
    licencia = lambda fila: fila["licencia"].strip().lower()
    return ([fila for fila in filas if licencia(fila).startswith("cc by")],
            [fila for fila in filas if licencia(fila) in ("", "falta")])


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
    parser = argparse.ArgumentParser(description="Licencias y medida de los textos de publicación")
    parser.add_argument("short", help="Carpeta del short, por ejemplo 002-caballo")
    args = parser.parse_args()

    ruta = RAIZ / "shorts" / args.short / "publicacion.md"
    if not ruta.is_file():
        sys.exit(f"No existe {ruta.relative_to(RAIZ)}")
    lineas = ruta.read_text(encoding="utf-8").splitlines()

    revision = licencias_con_problema(args.short)
    problema = False
    if revision is None:
        print("Todavía no hay clips elegidos: las licencias se revisan después del render.")
    else:
        atribucion, desconocidas = revision
        if atribucion:
            print(f"ATENCIÓN: {len(atribucion)} archivos exigen citar al autor (CC BY) y la publicación no lleva créditos:")
            for fila in atribucion:
                print(f"  {fila['archivo']}: {fila['licencia']}, de {fila['autor']}")
            print("Cámbialos por material sin esa obligación o añade su crédito a mano en la publicación.")
        if desconocidas:
            print(f"ATENCIÓN: {len(desconocidas)} archivos no tienen licencia conocida (no se sabe si se pueden usar):")
            for fila in desconocidas:
                print(f"  {fila['archivo']}: {fila['fuente']}, de {fila['autor'] or 'autor desconocido'}")
            print("Publicarlos es decisión tuya: no hay permiso conocido del autor.")
        problema = bool(atribucion or desconocidas)
        if not problema:
            print("Licencias: todo el material se puede publicar sin créditos.")

    print("\nMedidas:")
    if informe(lineas):
        sys.exit("\nAlgún texto se pasa del límite de su plataforma.")
    if problema:
        sys.exit("\nHay material que exige créditos o sin licencia conocida.")


if __name__ == "__main__":
    main()
