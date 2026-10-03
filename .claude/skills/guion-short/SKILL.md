---
name: guion-short
description: Escribe el guion de un short sobre un tema (gancho, dato, giro y remate, con datos verificados y sus fuentes), prepara su ficha en shorts/NNN-tema/ con guion.md y config.json (música, efectos), comprobando el material de vídeo, y sus textos de publicación (publicacion.md: títulos, descripción con fuentes y créditos, hashtags y comentario fijado para YouTube, Instagram, TikTok y X). Úsala cuando el usuario pida un short, un guion o un vídeo nuevo sobre un tema, o los textos para publicar un short.
argument-hint: "[tema | NNN-tema]"
---

# Guion y ficha de un short

Tema pedido: $ARGUMENTS

Si el argumento es un short que ya existe (`NNN-tema`, con su carpeta en `shorts/`),
no hay guion que escribir: ve directamente al paso 5 (Publicación) con su `guion.md`.

Todo en español. Explica al usuario qué vas a hacer en cada paso antes de hacerlo
(está aprendiendo) y respeta las reglas de CLAUDE.md: no se toca `data/` salvo con
`buscar_clips`, y no se hacen commits sin preguntar.

## Situación actual (se inyecta al cargar la skill)

Velocidad de lectura (`config/lectura.json`):
!`cat config/lectura.json`

Técnica de interacción de cada short:
!`grep -H -m1 "Técnica de interacción" shorts/*/guion.md || true`

Música de cada short:
!`grep -H -o "musica/[a-z_0-9]*\.mp3" shorts/*/config.json || true`

Último número usado (sin contar los 9xx, que son pruebas):
!`ls shorts data/archivo data/bandeja data/revision data/listos 2>/dev/null | grep -oE "^[0-8][0-9]{2}-" | sort | tail -1 || true`

Música del índice (archivo, etiquetas: la primera es el estado de ánimo):
!`grep ",musica," biblioteca/indice.csv | cut -d, -f1,8 || true`

Efectos del índice:
!`grep ",sfx," biblioteca/indice.csv | cut -d, -f1,8 || true`

El "short anterior" es el de número más alto por debajo de 900.

## 1. Guion

Lee [ejemplo-001-pulpo.md](ejemplo-001-pulpo.md): es el tono que hay que imitar.

**Estructura en cuatro tiempos:**
1. **Gancho**: los 3 primeros segundos, como máximo 12 palabras. Una pregunta o
   afirmación con un dato concreto que sorprenda.
2. **Dato**: el hecho principal, explicado con algo que se pueda imaginar.
3. **Giro**: "Y todavía hay más..." o una variación ("Pero aquí viene lo curioso",
   "Y lo más raro no es eso"). Un segundo dato que sorprenda más que el primero.
4. **Remate**: resume en una imagen, sin datos nuevos, e incluye la interacción.

**Forma:**
- Entre 100 y 120 palabras (unos 40-45 s). Cuenta solo las palabras que se dicen.
- Frases cortas, escritas para decirlas en voz alta: nada de incisos largos,
  paréntesis explicativos, cifras difíciles de pronunciar ni siglas sin explicar.
- **Negrita** en las palabras con énfasis (una o dos por frase como mucho) y
  `(pausa)` donde haya que respirar o dejar que el dato se asiente. La negrita
  también sale en **amarillo en los subtítulos** (`subtitulos.resaltar_negritas`):
  márcala en la palabra clave del dato, no en frases enteras, para que el color
  destaque. Si se cambian las negritas después de grabar, hay que rehacer los
  subtítulos (`--rehacer subtitulos`).

**Interacción indirecta**: una sola técnica por guion, de estas cinco:
- pregunta de respuesta fácil ("¿Lo sabías? Dímelo en una palabra")
- pregunta de opinión ligera ("¿Tú qué preferirías...?")
- bucle (la última frase conecta con la primera y el vídeo invita a volver a verse)
- promesa del siguiente dato ("Mañana te cuento...")
- reto inicial ("A que no adivinas..." en el gancho, con la respuesta en el remate)

No repitas la técnica del short anterior; entre las demás, prefiere la que lleve
más tiempo sin usarse (mira la lista de arriba).

**Rigor (obligatorio):**
- Busca cada dato en la web antes de usarlo y confírmalo en al menos dos fuentes
  fiables e independientes: universidades, museos, organismos científicos u
  oficiales, revistas científicas o divulgación seria que cite estudios.
- Si un dato es dudoso, discutido o un mito popular (aunque sea muy conocido),
  descártalo y busca otro. Si una cifra varía entre fuentes, usa la prudente o
  dila aproximada ("casi", "más de").
- Al final del guion, la lista de fuentes: qué dato confirma cada una, con su URL.

Enseña al usuario el guion, el recuento de palabras, la duración estimada, la
técnica y las fuentes. **Espera su visto bueno** antes de crear la ficha; si pide
cambios, rehaz el guion.

## 2. Ficha del short

**Duración estimada** = palabras / `palabras_por_segundo` + la cola (`final.cola` de
`config/por_defecto.json`, ahora 2,5 s, para que la música se apague con su fundido). Es solo
una estimación: la duración real la marca la grabación (voz detectada + cola), y
el vigilante vuelve a comprobar el material con ella.

**Número**: el siguiente al último usado (arriba). Crea `shorts/NNN-tema/`. El
tema va en singular, minúsculas, sin tildes y con `_` entre palabras
(`oso_hormiguero`).

**guion.md** con este formato:

```markdown
# NNN-tema: título corto

**Técnica de interacción:** <una de las cinco, con ese nombre exacto>
**Palabras:** N · **Duración estimada:** X s (velocidad X palabras/s + 2,5 s de cola)
**Música:** <archivo> · **Efectos:** <archivos y dónde suenan (palabra o automático)>

## Guion
**Gancho:** ...
**Dato:** ...
**Giro:** ...
**Remate:** ...

## Fuentes
1. <dato>: <fuente> (<url>)
```

**config.json**: solo lo que cambia respecto a la plantilla (el vigilante la pone
debajo al llegar la grabación). Sin `audio_original` (eso marca la receta como
reservada) y sin `clips` (los elige el vigilante con la duración real):

```json
{
  "musica": {"archivo": "data/biblioteca/musica/<archivo>.mp3"},
  "efectos": {
    "automaticos": 3,
    "archivos": ["data/biblioteca/sfx/<a>.mp3", "data/biblioteca/sfx/<b>.mp3"],
    "inicio_min": 8,
    "separacion_min": 12
  }
}
```

Valídalo con `python -m json.tool` en Docker.

**Música**: una canción cuyo estado de ánimo (primera etiqueta) encaje con el
guion (curiosidad, misterio, alegria, relajada...), distinta de la del short
anterior y que dure al menos la duración estimada + 3 s (mídela con ffprobe en
Docker). Si ninguna encaja, dilo y propón buscar una.

**Efectos**: `automaticos` = mín(3, redondeo(duración / 13,5)): uno cada 12-15 s,
ninguno en los primeros 8 s (`inicio_min`) y como máximo 3. Suenan en los cortes que
caen en finales de frase, en orden, así que pon `archivos` en el orden del guion.

Si un efecto tiene que sonar en una palabra concreta del guion (un "error" justo al
decir "vomitar"), no lo dejes al azar: ponlo en `efectos.lista` anclado a la palabra.
Empieza justo al terminar de decirla y se recoloca solo si se regraba. Con `lista`,
los automáticos no se usan, así que incluye en ella todos los efectos:

```json
"efectos": {"lista": [
  {"archivo": "data/biblioteca/sfx/riser_01.mp3", "palabra": "curioso"},
  {"archivo": "data/biblioteca/sfx/error_01.mp3", "palabra": "vomitar"},
  {"archivo": "data/biblioteca/sfx/ding_01.mp3", "palabra": "soñar", "vez": 2}
]}
```

`vez` dice qué aparición de la palabra (1 si no se pone). Escribe la palabra tal como
se dice, sin signos. No hace falta tocar volúmenes: el render iguala el pico de cada
efecto (`efectos.pico`) antes de aplicar `efectos.volumen`, y la música va por
defecto a 0,25.

Tipos:
- `whoosh`: cambio de bloque (del dato al giro, del giro al remate)
- `riser`: tensión antes del giro o de un dato sorprendente
- `ding`: un dato curioso o una idea
- `error`: un mito desmentido o algo que "falla"

## 3. Material

1. `evaluar_material(tema, duración estimada)`.
2. Si no es *suficiente*, di cuántos clips faltan y **pide permiso** antes de
   descargar. Con permiso: `buscar_clips` con la `cantidad` que diga
   `evaluar_material` (máximo 5 por llamada), la búsqueda en inglés y, si el tema
   es nuevo, una o dos `etiquetas_generales` en singular y sin tildes.
3. Vuelve a ejecutar `evaluar_material` para confirmar. Si sigue sin llegar (no hay
   más vídeos en Pixabay, por ejemplo), dilo: el short se puede hacer, pero
   repetirá planos.

## 4. Cierre

Dile al usuario:
- El nombre exacto de la grabación: `NNN-tema.wav` (también vale .mp3, .m4a, .aif),
  para dejarla en `data/bandeja/` con el vigilante en marcha. O bien dejarla en
  `data/entrada/` con cualquier nombre y pedir `preparar_short`, que usará esta
  receta reservada.
- Que lea el guion a su ritmo: la duración real la marca su voz. El vigilante
  elegirá los clips con esa duración, anotará en `data/registro.log` si el material
  no alcanza, y al terminar sumará la grabación a la velocidad de lectura.
- Un resumen: guion.md, música, efectos y estado del material.
- Que `publicacion.md` ya tiene los textos, pero los créditos se completan después
  del render (paso 5).

## 5. Publicación

Prepara `shorts/NNN-tema/publicacion.md` con los textos para publicar el short. Se
hace justo después de la ficha (o directamente, si el short ya existe). Todo sale del
guion: no añadas datos que no estén en él o en sus fuentes.

**Títulos**: 3 opciones de unos 60 caracteres como máximo (YouTube corta hacia ahí en
el móvil; el límite es 100). El tema o la palabra clave al principio y una brecha de
curiosidad que el vídeo **resuelva de verdad**: nada que prometa algo que el vídeo no
da, ni exageraciones que el guion no diga. Si la técnica es *reto inicial*, el título
plantea el reto sin dar la respuesta. Marca tu favorita y di por qué.

**Descripción** (en este orden):
1. Primera línea: el gancho en una frase de 80 caracteres como mucho, porque es lo
   único que se ve antes de "más" en TikTok (en Instagram, unos 125).
2. 2 o 3 frases que amplíen el dato, sacadas de las fuentes del guion.
3. Una pregunta que conecte con la técnica de interacción del guion (con *promesa del
   siguiente dato*, que pregunte qué animal quieren después; con *reto inicial*, si lo
   habían adivinado...).
4. `Fuentes:` con el medio y la url de cada fuente del guion.
5. Los créditos: una línea `Créditos:` sola, seguida de `(pendientes: se rellenan con
   creditos.py)`. Los escribe el script con los datos del índice; no los copies a mano.
6. Entre 3 y 5 hashtags en español, sin tildes ni `#shorts`: el del tema primero, uno
   o dos generales (`#animales`, `#curiosidades`) y alguno del dato (`#pulpo`,
   `#sangreazul`). YouTube enseña los tres primeros encima del título e Instagram solo
   tiene en cuenta 5.

**Comentario fijado**: una pregunta que invite a contestar, fácil de responder y
distinta de la de la descripción. 150 caracteres como máximo (el límite de TikTok),
para que sirva en todas.

**Plataformas**: escribe una sola versión mientras quepa en todas y sepárala solo
cuando una plataforma lo necesite:

| Plataforma | Límites (comprobados el 2026-10-03) |
|---|---|
| YouTube | título 100 · descripción 5000 · comentario 10 000 |
| Instagram | descripción 2200 (se ven unos 125) · como máximo 5 hashtags |
| TikTok | descripción 4000 (se ven unos 80) · comentario 150 |
| X | 280 por post (cada url cuenta 23): no caben fuentes ni créditos, que van en una respuesta al propio post |

Plantilla (los nombres de las secciones `##` y `###` son los que mide el script):

````markdown
# NNN-tema: publicación

**Técnica de interacción:** <la del guion> · **Título favorito:** <número>, porque <motivo>

## Títulos
```text
<opción 1>
<opción 2>
<opción 3>
```

## YouTube
### Título
```text
<la favorita>
```

## YouTube, Instagram y TikTok
### Descripción
```text
<gancho, 80 caracteres como mucho>

<2 o 3 frases>

<pregunta>

Fuentes:
- <medio>: <url>

Créditos:
(pendientes: se rellenan con creditos.py)

#tema #general #dato
```
### Comentario fijado
```text
<pregunta>
```

## X
### Post
```text
<gancho, una frase del dato, la pregunta y 1 o 2 hashtags>
```
### Respuesta
```text
Fuentes: <url> <url>
Créditos: (pendientes)
```
````

**Medir y completar**: los caracteres no se cuentan a ojo. Después de escribir el
archivo, y otra vez cuando el short tenga clips (tras el render), ejecuta:

```bash
docker run --rm -t -v "$PWD:/proyecto" shorts-whisper python /proyecto/scripts/creditos.py NNN-tema
```

Rellena los créditos con los clips que el short usa de verdad (de su lista de cortes),
la música y los efectos, y mide cada texto con el límite de cada plataforma. Si algo
"SE PASA", acórtalo y vuelve a ejecutarlo. Enseña al usuario los títulos con tu
favorita y las medidas.
