"""Cambia la versión de la fábrica que usan los shorts nuevos, sin cambiar los antiguos.

Uso: python promover_version.py 2.0 [--simular]

1. Escribe "version_fabrica" (la versión por defecto de ahora, con la que se hicieron)
   en todas las recetas de shorts/ que no la tengan: las grabadas, las reservadas y
   las 9xx. Las que ya la tienen no se tocan. Una receta sin config.json (una reservada
   con solo el guion) recibe uno con solo la versión.
2. Cambia "version_fabrica" de config/por_defecto.json a la versión nueva.
3. Comprueba que los JSON tocados siguen siendo válidos y lista lo que ha cambiado.

Desde entonces los shorts nuevos nacen con la versión nueva y los antiguos siguen fijados
a la suya, porque los valores de cada versión están congelados en config/versiones/.
Repetirlo no cambia nada. Con --simular solo dice lo que haría.
"""
import argparse
import json
import re
import sys

from crear_short import RAIZ

POR_DEFECTO = RAIZ / "config" / "por_defecto.json"
VERSION = re.compile(r'"version_fabrica":\s*"([^"]*)"')


def con_version(texto, version):
    """Añade la versión justo después de la llave de apertura, como una línea más: así
    no se reescribe el resto del archivo y el cambio en Git es de una sola línea."""
    if not texto.strip():
        return json.dumps({"version_fabrica": version}, indent=2) + "\n"
    inicio = texto.index("{") + 1
    return texto[:inicio] + f'\n  "version_fabrica": "{version}",' + texto[inicio:]


def cambios_necesarios(nueva):
    """Lista de (ruta, texto nuevo, descripción) sin escribir nada."""
    texto_defecto = POR_DEFECTO.read_text(encoding="utf-8")
    actual = json.loads(texto_defecto)["version_fabrica"]
    cambios = []
    for receta in sorted(p for p in (RAIZ / "shorts").iterdir() if re.match(r"\d{3}-", p.name) and p.is_dir()):
        ruta = receta / "config.json"
        texto = ruta.read_text(encoding="utf-8") if ruta.exists() else ""
        if texto.strip() and "version_fabrica" in json.loads(texto):
            continue
        que = "nueva receta con" if not texto.strip() else "se fija a la"
        cambios.append((ruta, con_version(texto, actual), f"{receta.name}: {que} versión {actual}"))
    if actual != nueva:
        cambios.append((POR_DEFECTO, VERSION.sub(f'"version_fabrica": "{nueva}"', texto_defecto, count=1),
                        f"por_defecto.json: versión {actual} -> {nueva}"))
    return cambios


def main():
    parser = argparse.ArgumentParser(description="Cambia la versión de la fábrica de los shorts nuevos")
    parser.add_argument("version", help="Versión nueva, por ejemplo 2.0")
    parser.add_argument("--simular", action="store_true", help="Solo dice lo que cambiaría")
    args = parser.parse_args()

    if not (RAIZ / "config" / "versiones" / f"{args.version}.json").exists():
        print(f"ERROR: la versión '{args.version}' no está en config/versiones/", file=sys.stderr)
        sys.exit(1)

    cambios = cambios_necesarios(args.version)
    if not cambios:
        print(f"Nada que cambiar: la versión por defecto ya es {args.version} y todas las recetas tienen la suya.")
        return
    for ruta, texto, descripcion in cambios:
        json.loads(texto)          # nunca se escribe un JSON roto
        if not args.simular:
            ruta.write_text(texto, encoding="utf-8")
        print(("(simulado) " if args.simular else "") + descripcion)
    print(f"{len(cambios)} archivos {'cambiarían' if args.simular else 'cambiados'}.")


if __name__ == "__main__":
    main()
