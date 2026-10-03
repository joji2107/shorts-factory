# Fase 9: Estrategia de contenido y canales

> Estado: en curso.

## Objetivo
Publicar los shorts en los canales nuevos (YouTube, Instagram, TikTok y X) con
textos cuidados y honestos: títulos que despierten curiosidad sin engañar,
descripciones con las fuentes de los datos y los créditos de los clips y la música,
y una pregunta que invite a comentar.

| Parte | Qué se hizo | Commit |
|---|---|---|
| 1 | Textos de publicación en la skill `guion-short` y `scripts/creditos.py` | |

---

## Parte 1: textos de publicación

### Qué hace
La skill `guion-short` tiene un paso nuevo (5, Publicación) que escribe
`shorts/NNN-tema/publicacion.md`:

- **Títulos**: 3 opciones de unos 60 caracteres, con el tema al principio y una
  brecha de curiosidad que el vídeo resuelve de verdad. Con *reto inicial*, el título
  no da la respuesta. La skill marca su favorita.
- **Descripción**: el gancho en la primera línea, 2 o 3 frases que amplían el dato,
  una pregunta que conecta con la técnica de interacción del guion, las fuentes y
  los créditos, y entre 3 y 5 hashtags en español.
- **Comentario fijado**: otra pregunta fácil de contestar, de 150 caracteres como
  mucho para que sirva también en TikTok.
- **Versiones por plataforma** solo cuando hacen falta: un texto que cabe en varias
  va una sola vez en una sección como `## YouTube, Instagram y TikTok`. X va aparte
  (280 caracteres): las fuentes y los créditos van en una respuesta al propio post.

Si a la skill se le pasa un short que ya existe (`/guion-short 001-pulpo`), salta
directamente a este paso.

### Límites de cada plataforma
Comprobados el 2026-10-03. Cambian a menudo; si una plataforma los cambia, se
actualizan en `LIMITES` (`scripts/creditos.py`) y en la tabla de la skill.

| Plataforma | Límites |
|---|---|
| YouTube | título 100 · descripción 5000 · comentario 10 000; los 3 primeros hashtags salen encima del título |
| Instagram | descripción 2200 (se ven unos 125 antes de "más") · como máximo 5 hashtags desde diciembre de 2025 |
| TikTok | descripción 4000 (se ven unos 80) · comentario 150 |
| X | 280 por post en cuentas gratuitas · cada url cuenta 23, sea como sea de larga |

### `scripts/creditos.py`
Los clips no se conocen al escribir el guion: los elige el vigilante con la
duración real de la grabación. Por eso los créditos se escriben después del render,
con un script en vez de copiarlos a mano del índice:

```bash
docker run --rm -t -v "$PWD:/proyecto" shorts-whisper python /proyecto/scripts/creditos.py 002-caballo
```

1. Mira qué clips usa el short de verdad: su `cortes.txt` o, si no tiene,
   `data/shorts/<nombre>/cortes_auto.txt` (si aún no existe, los clips de la receta).
   Además, la música y los efectos que suenan (con `efectos.lista`, solo esos).
2. Busca el autor, la fuente y la url de cada archivo en `biblioteca/indice.csv` (con
   `leer_indice()` de `material.py`).
3. Sustituye en `publicacion.md` la línea `Créditos:` (y las que la siguen hasta la
   primera vacía) por la versión larga, y la línea `Créditos: ...` de X por la corta.
   Se puede repetir sin cambiar nada (comprobado con `md5`).
4. Mide cada bloque ```text con el límite de cada plataforma de su sección y avisa si
   la primera línea es más larga de lo que se ve o si hay más hashtags de los que
   cuentan. Si algo se pasa, termina con código 1.

Los caracteres se cuentan con el script y no a ojo: es fácil equivocarse contando a
mano, y en X las urls no cuentan lo que miden.

### Los shorts 001-pulpo y 002-caballo
- **001-pulpo** no tenía fuentes (se grabó antes de la skill). Se buscaron y se
  añadieron a su `guion.md`: Smithsonian Magazine, BBC Science Focus, el estudio de
  Wells y otros (Journal of Experimental Biology, 1987) sobre el corazón que se para
  al nadar a chorro, y Scientific American para la sangre azul. Su remate promete
  "Mañana te cuento algo todavía más raro": para cumplirlo, 002-caballo se publica al
  día siguiente (anotado en su `publicacion.md`).
- **002-caballo** usa las fuentes de su guion. Su técnica es *reto inicial*, así que
  ningún título dice la respuesta (soñar).

Medidas de los dos: descripciones de 1680 y 1495 caracteres (caben en las tres
plataformas), comentarios de 68 y 61, y en X posts de 200 y 184 y respuestas de 241 y
249.

## Problemas y soluciones

| Síntoma | Causa | Solución | Prevención |
|---------|-------|----------|------------|
| No se pueden poner los créditos al escribir el guion | Los clips los elige el vigilante después de grabar | Créditos pendientes en `publicacion.md` y `creditos.py` después del render | |
| 001-pulpo no tenía fuentes | Se grabó antes de la skill, que exige verificar los datos | Buscarlas después y anotar que confirman lo que ya se dijo | Todos los guiones nuevos pasan por la skill |
| Algunas páginas de fuentes no se dejan abrir (Smithsonian, la revista del estudio) | Bloquean las descargas automáticas (error 403) | Comprobar el contenido por el extracto del buscador y anotarlo en la fuente | |
| La url de un estudio podía cambiar | Las revistas cambian de web | Usar su DOI (`https://doi.org/...`), que siempre lleva al artículo | |
| Muchas webs decían que Instagram admite 30 hashtags | Páginas de contadores sin actualizar | Buscar el anuncio oficial (5 desde diciembre de 2025) | Fecha de comprobación junto a cada límite |
| [Añade aquí otros problemas] | | | |

## Herramientas aprendidas

| Herramienta | Para qué |
|-------------|----------|
| `doi.org` | Enlace permanente a un artículo científico |
| `curl -sI` | Ver solo la respuesta de una web (código y redirección) sin descargarla |
| `re.split`, `re.findall` | Separar las plataformas de una sección y contar urls y hashtags |
| `dict.fromkeys` | Quitar repetidos de una lista sin cambiar el orden |

## Mis conclusiones
- [Añade aquí qué te parece escribir títulos con curiosidad sin caer en el engaño]
- [Añade aquí qué has aprendido de las diferencias entre plataformas]
- [Añade aquí lo que tú sientas que has aprendido]

## Pendiente
- Publicar 001-pulpo y, al día siguiente, 002-caballo.
- [Añade aquí otros pendientes]
