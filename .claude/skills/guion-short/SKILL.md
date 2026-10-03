---
name: guion-short
description: Escribe el guion de un short sobre un tema (gancho, dato, giro y remate, con datos verificados y sus fuentes) y prepara su ficha en shorts/NNN-tema/ con guion.md y config.json (música, efectos), comprobando el material de vídeo. Úsala cuando el usuario pida un short, un guion o un vídeo nuevo sobre un tema.
argument-hint: "[tema]"
---

# Guion y ficha de un short

Tema pedido: $ARGUMENTS

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
  `(pausa)` donde haya que respirar o dejar que el dato se asiente.

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
