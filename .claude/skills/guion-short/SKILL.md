---
name: guion-short
description: Escribe el guion de un short sobre un tema (gancho, dato, giro y remate, con datos verificados y sus fuentes), prepara su ficha en shorts/NNN-tema/ con guion.md y config.json (música, efectos), comprobando el material de vídeo, y sus textos de publicación (publicacion.md: títulos, descripción con fuentes y créditos, hashtags y comentario fijado para YouTube, Instagram, TikTok y X). Úsala cuando el usuario pida un short, un guion o un vídeo nuevo sobre un tema, o los textos para publicar un short.
argument-hint: "[tema | NNN-tema]"
---

# Guion y ficha de un short

Tema pedido: $ARGUMENTS

Si el argumento es un short que ya existe (`NNN-tema`, con su carpeta en `shorts/`),
no hay guion que escribir: ve directamente al paso 5 (Publicación) con su `guion.md`.

**Versión de la fábrica**: si la versión por defecto (abajo) es 2.0, o el usuario pide un
short "2.0" / "de promesa y recompensa", sigue además la sección **Fábrica 2.0**, que
cambia la estructura del guion, añade marcas de montaje y elige música y protagonistas.
Si no, la estructura clásica (gancho, dato, giro, remate).

Todo en español. Explica al usuario qué vas a hacer en cada paso antes de hacerlo
(está aprendiendo) y respeta las reglas de CLAUDE.md: no se toca `data/` salvo con
`buscar_clips`, y no se hacen commits sin preguntar.

## Situación actual (se inyecta al cargar la skill)

Versión de la fábrica por defecto:
!`grep -o '"version_fabrica": "[^"]*"' config/por_defecto.json || true`

Energía de la música (`biblioteca/musica.json`; momento fuerte en segundos de la canción):
!`python3 -c "import json;d=json.load(open('biblioteca/musica.json'));[print(k, 'dura', d[k]['duracion'], '| momento fuerte', d[k]['momento_fuerte'], '| subida', d[k]['subida_db'], 'dB', '| PLANA' if d[k]['plana'] else '') for k in sorted(d)]" 2>/dev/null || true`

Velocidad de lectura (`config/lectura.json`):
!`cat config/lectura.json`

Técnica de interacción de cada short:
!`grep -H -m1 "Técnica de interacción" shorts/*/guion.md || true`

Música de cada short (por orden de número, sin los 9xx de prueba):
!`grep -H -o "musica/[a-z_0-9]*\.mp3" shorts/[0-8]*/config.json | sort || true`

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

## Fábrica 2.0 (promesa y recompensa)

La idea es la **anticipación**: el espectador sabe desde el principio qué va a ver y se
queda para ver cómo llega. Todo lo demás de la skill (rigor, fuentes, técnica de
interacción rotando, número, publicación) se mantiene.

**Estructura** (las etiquetas en negrita son estas, en vez de las clásicas):
1. **Promesa** (como mucho 12 palabras): dice qué va a ver ("Esto es lo más violento que
   puede hacer la Tierra"), sin revelarlo. Tiene que cumplirse de verdad al final.
2. **Escalones**: 3 o 4 descubrimientos pequeños, cada uno más fuerte que el anterior, que
   acercan a X sin decirlo. Nada del dato principal todavía.
3. **Revelación**: `[respiro]` justo antes de X, con el plano protagonista más
   impresionante y la música en su momento fuerte. Después, X en una frase corta.
4. **Cierre**: enlaza con la promesa (un eco de la primera frase) e incluye la interacción.
   Encaja con *bucle*, pero la técnica sigue rotando como siempre.

**Longitud**: 90-110 palabras (los respiros añaden segundos). Duración estimada =
palabras / velocidad + segundos de respiros + cola.

**Marcas de montaje** (entre corchetes, **antes de la palabra** en la que actúan; no se
leen y la hoja para leer las trata sola):
- `[respiro N]`: N segundos de silencio de voz (sin N, 2,5 s). El sistema lo inserta: el
  usuario lee seguido. 1 o 2 por short; el **último es la revelación** (la música se
  sincroniza con él). Ni al principio ni al final del guion.
- `[plano clip desde largo]`: plano protagonista, desde ese segundo del clip y durante
  `largo` s (5-9; como mucho `video.ritmo.plano_max`, 9). Empieza 0,1 s antes de la
  palabra siguiente, o con el respiro si va justo detrás de uno (`[respiro 3] [plano
  volcan_03 12 7] Y entonces...`: el plano cubre el silencio y el principio de la frase).
  2 o 3 por short, sin pisarse; el resto es relleno de cortes rápidos (1-2,2 s).

**Protagonistas**: después de tener el material (paso 3), genera las hojas de fotogramas
del tema y míralas con Read:

```bash
docker run --rm -t -v "$PWD:/proyecto" shorts-whisper python /proyecto/scripts/hoja_fotogramas.py <tema>
```

(`data/cache/fotogramas/<clip>.jpg`, un fotograma por segundo con el segundo escrito.)
Elige los planos que encajan muy bien con una frase o son especialmente impresionantes o
divertidos, y el `desde` en el que empieza lo bueno. Comprueba que `desde + largo` no pase
de la duración del clip. El mejor, para la revelación. Los protagonistas deben ser
grabaciones reales (no IA).

**Música**: además de las reglas de siempre (no repetir en 5 shorts...), solo canciones
**no planas con subida de 5 dB o más** (tabla de energía de arriba). Con `"inicio":
"auto"` (lo pone la versión 2.0), la canción empieza en `momento fuerte − segundo de la
revelación`, así que hace falta:
- momento fuerte ≥ segundo estimado de la revelación (si no, empieza en 0 y el momento
  fuerte llega antes);
- duración de la canción ≥ momento fuerte − revelación + duración del short.

Si ninguna libre cumple, dilo y pide al usuario música nueva (que la analice con
`analizar_musica.py`). **Respiros en valles**: con el inicio calculado, mira en la curva
de `biblioteca/musica.json` qué suena en los demás respiros (segundo de la canción =
inicio + segundo del respiro en el vídeo). Si cae 6 dB o más por debajo de la mediana, el
respiro sonará casi en silencio (en 902-respiros, el primero caía en el valle de antes del
drop de misterio_03): muévelo o quítalo. El render también lo avisa.

**config.json** de un short 2.0 (la versión 2.0 ya activa respiros, ritmo y música
automática):

```json
{
  "version_fabrica": "2.0",
  "musica": {"archivo": "data/biblioteca/musica/<archivo>.mp3"},
  "efectos": {"lista": [...]}
}
```

**Material**: `evaluar_material(tema, duración, version="2.0")`, con duración = voz +
respiros − planos protagonistas (el relleno se corta más rápido y gasta más clips).

**guion.md**: en la cabecera, además, `**Música:** <archivo> (momento fuerte en el
segundo N, inicio automático)` y una línea `**Planos:**` con cada protagonista y por qué.

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

> <opcional: nota de lectura, si hay algo especial (el final de un bucle, una
> palabra difícil...). Sale arriba en la hoja para leer.>

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
reservada) y sin `clips` (los elige el vigilante con la duración real). Siempre con
`version_fabrica` (`"1.0"` o `"2.0"`): fija con qué valores se hace el short aunque luego
cambie la versión por defecto.

```json
{
  "version_fabrica": "1.0",
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
guion (curiosidad, misterio, alegria, relajada...) y que dure al menos la duración
estimada + 3 s (mídela con ffprobe en Docker). Las canciones no se repiten tan
rápido: **ninguna de los últimos 5 shorts** (mira la lista de arriba) y, entre las
que encajan, la que lleve más tiempo sin usarse (primero las que no se han usado
nunca). Si ninguna libre encaja, no repitas: dilo y propón buscar música nueva.
(004-elefante repitió la de 001-pulpo porque antes solo se evitaba la del short
anterior.)

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
- `error`: un mito desmentido o algo que "falla". Es un sonido de broma: solo en
  guiones de tono divertido (música `alegria`). En uno serio o de misterio queda mal
  (en 003-rayo hubo que quitarlo).

**Bucle**: si la técnica es *bucle*, el vídeo tiene que acabar justo después de la
última palabra para que enlace con la primera. Pon en `config.json`
`"final": {"tras_ultima_palabra": 0.5}`: el vídeo acaba 0,5 s después de la última
palabra (en vez de 2,5 s de cola) y la música se funde en ese medio segundo.

## 3. Material

1. `evaluar_material(tema, duración de la voz)`: palabras / `palabras_por_segundo`,
   **sin la cola**, porque la herramienta ya la suma (si se le pasa la duración
   estimada, la cola se cuenta dos veces y pide clips de más).
2. Si no es *suficiente*, di cuántos clips faltan y **pide permiso** antes de
   descargar. Con permiso:
   - `ver_candidatos(búsqueda en inglés)`: no descarga nada. La primera palabra de
     la búsqueda tiene que estar en las etiquetas del vídeo. Prueba también
     `orientacion="horizontal"`: lo grabado de verdad suele ser horizontal y en
     vertical abunda la IA.
   - **Mira las miniaturas** (`data/cache/miniaturas/`): que se vea el tema de
     verdad y que no sea todo IA o animación 3D (la marca de IA de Pixabay falla a
     veces). Algún clip de IA vale, pero no puede ser la norma: como mucho 1 de cada
     6-7 clips del short (como en 003-rayo, que el usuario dio por perfecto).
   - `buscar_clips(tema, ids="id1,id2")` con los elegidos (máximo 5 por llamada) y,
     si el tema es nuevo, una o dos `etiquetas_generales` en singular y sin tildes.
   - Después, comprueba los clips descargados con fotogramas: lo que entra en la
     biblioteca ya no se puede borrar. Si alguno no sirve (no se ve el tema, o es IA o
     animación sin el tema de verdad), añade al final de sus etiquetas en
     `biblioteca/indice.csv` `;descartado` (y `;ia` si es IA aunque Pixabay no lo
     marque): el vigilante y `evaluar_material` dejan de contarlo.
   - Si el tema es algo que dura un instante (rayos, relámpagos, fuegos
     artificiales), pon `"video": {"buscar_destellos": true}` en `config.json`:
     cada corte empieza justo antes de un destello. Si no, en un clip de tormenta
     de 50 s casi todos los cortes caen en negro.
   - Si un clip solo enseña el tema unos instantes y no es un destello de luz (la
     estrella fugaz animada de 008-orionidas cruza 5 veces en 58 s), míralo segundo a
     segundo (un fotograma por segundo en una hoja) y, tras el render, fija sus cortes
     en un `cortes.txt` medio segundo antes de cada momento: el reparto al azar los
     puede cortar entre dos.
3. Vuelve a ejecutar `evaluar_material` para confirmar. Si sigue sin llegar (no hay
   más vídeos en Pixabay, por ejemplo), dilo: el short se puede hacer, pero
   repetirá planos.

## 4. Cierre

**Hoja para leer (siempre, antes de arrancar el vigilante):** genera la hoja con el
guion y cómo leerlo y ábresela al usuario:

```bash
docker run --rm -t -v "$PWD:/proyecto" shorts-whisper python /proyecto/scripts/para_leer.py NNN-tema
open shorts/NNN-tema/para_leer.html
```

Sale de `guion.md` (una frase por línea, la negrita en color, las pausas en gris y
las notas `>` de la cabecera arriba), así que si el guion cambia, vuelve a generarla.

Dile al usuario:
- El nombre exacto de la grabación: `NNN-tema.wav` (también vale .mp3, .m4a, .aif),
  para dejarla en `data/bandeja/` con el vigilante en marcha. O bien dejarla en
  `data/entrada/` con cualquier nombre y pedir `preparar_short`, que usará esta
  receta reservada.
- Que grabe con el **micro a 10-15 cm** de la boca: en la prueba de voz (fase 9, parte 10)
  es lo que más mejoró el sonido (3-4 dB más de voz sobre el ruido).
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
