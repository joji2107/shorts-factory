"""Compara cómo funcionan los shorts por técnica de interacción, tema y duración.

Uso: python analizar_metricas.py [--momento 7d|48h] [--plataforma youtube]

- Cada plataforma va por separado: sus cifras no se pueden comparar entre sí.
- Medianas y no medias: un solo vídeo viral cambiaría la media de todo su grupo.
- Likes, comentarios, compartidos y seguidores van por cada 1000 visualizaciones; si
  no, ganaría siempre el grupo del vídeo que más se vio.
- % visto = duración media vista / duración del vídeo (pasa de 100 si se vuelve a ver).
- Avisa cuando hay pocos datos: con un puñado de shorts, las diferencias pueden ser azar.
"""
import argparse
import statistics

import metricas

MIN_GRUPO = 3        # shorts por grupo para tomarlo en serio
MIN_PLATAFORMA = 10  # shorts medidos en una plataforma para sacar conclusiones
TASAS = ["likes", "comentarios", "compartidos", "seguidores"]


def numero(texto):
    return float(texto) if texto not in ("", None) else None


def tramo(segundos):
    if segundos is None:
        return "sin duración"
    if segundos < 40:
        return "menos de 40 s"
    return "40-45 s" if segundos <= 45 else "más de 45 s"


def preparar(fila):
    """Añade a una medida los valores calculados que se comparan."""
    vis = numero(fila["visualizaciones"])
    dur = numero(fila["duracion_s"])
    media = numero(fila["duracion_media_s"])
    datos = {
        "visualizaciones": vis,
        "se_quedaron_pct": numero(fila["se_quedaron_pct"]),
        "visto_pct": media / dur * 100 if media is not None and dur else None,
        "tecnica": fila["tecnica"] or "sin técnica",
        "tema": fila["tema"],
        "duracion": tramo(dur),
    }
    for campo in TASAS:
        valor = numero(fila[campo])
        datos[campo] = valor / vis * 1000 if valor is not None and vis else None
    return datos


def mediana(filas, campo):
    valores = [f[campo] for f in filas if f[campo] is not None]
    return statistics.median(valores) if valores else None


def celda(valor, decimales=1):
    """Número con punto de miles y coma decimal (1.234,5); '—' si no hay dato."""
    if valor is None:
        return "—"
    return f"{valor:,.{decimales}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def tabla(filas, agrupar, plataforma):
    columnas = [("vis.", "visualizaciones", 0)]
    if plataforma == "youtube":
        columnas.append(("% se quedó", "se_quedaron_pct", 1))
    columnas += [("% visto", "visto_pct", 1)] + [(f"{c[:6]}/1000", c, 1) for c in TASAS]

    grupos = {}
    for f in filas:
        grupos.setdefault(f[agrupar], []).append(f)
    ancho = max(len(g) for g in grupos) + 6
    print(f"  {'':{ancho}}" + "".join(f"{nombre:>13}" for nombre, _, _ in columnas))
    for grupo, miembros in sorted(grupos.items(), key=lambda g: -(mediana(g[1], "visualizaciones") or 0)):
        marca = " *" if len(miembros) < MIN_GRUPO else ""
        etiqueta = f"{grupo} ({len(miembros)}){marca}"
        print(f"  {etiqueta:{ancho}}" + "".join(f"{celda(mediana(miembros, campo), dec):>13}"
                                               for _, campo, dec in columnas))
    return grupos


def main():
    parser = argparse.ArgumentParser(description="Compara los shorts por técnica, tema y duración")
    parser.add_argument("--momento", choices=list(metricas.MOMENTOS),
                        help="Por defecto 7d si hay medidas de 7 días; si no, 48h")
    parser.add_argument("--plataforma", choices=metricas.PLATAFORMAS)
    parser.add_argument("--carpeta", default=str(metricas.CARPETA))
    args = parser.parse_args()

    todas = metricas.leer_metricas(metricas.RAIZ / args.carpeta)
    momento = args.momento or ("7d" if any(m["momento"] == "7d" for m in todas) else "48h")
    elegidas = [m for m in todas if m["momento"] == momento
                and (not args.plataforma or m["plataforma"] == args.plataforma)]
    print(f"Medidas a las {momento}: {len(elegidas)}")
    if not elegidas:
        print("No hay medidas que comparar todavía.")
        return

    print("Medianas de cada grupo; entre paréntesis, cuántos shorts tiene. "
          f"* = menos de {MIN_GRUPO} shorts: no sirve para sacar conclusiones.")
    for plataforma in metricas.PLATAFORMAS:
        filas = [preparar(m) for m in elegidas if m["plataforma"] == plataforma]
        if not filas:
            continue
        print(f"\n=== {plataforma} ({len(filas)} shorts)")
        if len(filas) < MIN_PLATAFORMA:
            print(f"AVISO: solo {len(filas)} shorts medidos (menos de {MIN_PLATAFORMA}). "
                  "Las diferencias pueden ser casualidad: tómalo como pistas, no como conclusiones.")
        grupos_por = {}
        for titulo, campo in (("Por técnica", "tecnica"), ("Por tema", "tema"), ("Por duración", "duracion")):
            print(f"\n {titulo}")
            grupos_por[campo] = tabla(filas, campo, plataforma)
        if all(len(m) == 1 for m in grupos_por["tema"].values()):
            print("\nAVISO: cada tema tiene un solo short. Comparar temas es comparar shorts sueltos, "
                  "y el tema va mezclado con la técnica, la música y el día de publicación.")
        sin_dato = [c for c in ("visualizaciones", "visto_pct") if all(f[c] is None for f in filas)]
        if sin_dato:
            print(f"AVISO: no hay ningún dato de {', '.join(sin_dato)} en {plataforma}.")


if __name__ == "__main__":
    main()
