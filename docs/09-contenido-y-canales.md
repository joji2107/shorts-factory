# Fase 9: Estrategia de contenido y canales

> Estado: en curso.

## Objetivo
Publicar los shorts en los canales nuevos (YouTube, Instagram, TikTok y X) con
textos cuidados y honestos: títulos que despierten curiosidad sin engañar,
descripciones con las fuentes de los datos y los créditos de los clips y la música,
y una pregunta que invite a comentar.

| Parte | Qué se hizo | Commit |
|---|---|---|
| 1 | Textos de publicación en la skill `guion-short` y `scripts/creditos.py` | `580af6c` |
| 2 | Subtítulos con los colores de la marca y resaltado de las negritas del guion | `9a0c07e` |
| 3 | Hoja para leer el guion (`scripts/para_leer.py`) y short 003-rayo | `73eaf2d` |
| 4 | Correcciones del 003-rayo: clips reales, bucle, efectos y subtítulos | `73eaf2d` |
| 5 | Short 004-elefante (estudio original) y final del vídeo tras la última palabra | |
| 8 | Publicaciones y métricas: CSV, scripts, skill `registrar-metricas` y avisos en el servidor | |

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

## Parte 2: subtítulos con los colores de la marca

### Colores
Los de la foto de perfil y los banners: azul marino `#14213D` y amarillo `#FFC93C`.
Están en `config/por_defecto.json`, en formato web, no en el código:

```json
"color_texto": "#FFFFFF",
"color_contorno": "#14213D",
"contorno": 7,
"resaltar_negritas": true,
"color_resaltado": "#FFC93C"
```

ASS escribe los colores al revés que la web: azul, verde, rojo (`&HBBGGRR`). La
función `color_ass()` de `subtitulos.py` hace el cambio: `#FFC93C` → `3CC9FF` y
`#14213D` → `3D2114`.

### Contorno: negro o azul
Contraste calculado con la fórmula WCAG (el mínimo recomendado es 4,5:1):

| Texto | Contorno negro | Contorno azul |
|---|---|---|
| Blanco | 21:1 | 16:1 |
| Amarillo | 13,7:1 | 10,4:1 |

Los dos se leen de sobra. Se compararon fotogramas reales de 002-caballo sobre el
clip más claro (nieve) y el más oscuro (noche): sobre la nieve, los dos se leen
igual de bien y el azul se nota como un borde azulado; de noche, el azul separa un
poco mejor las letras del fondo. Se queda el **azul**: es casi igual de legible y es
la combinación de la marca (amarillo sobre azul).

### Resaltado de las negritas
Las palabras que el guion marca en **negrita** salen en amarillo. No basta con buscar
cada palabra suelta: en 002-caballo hay negritas en palabras que se repiten ("no",
"todos", "soñar"), y se resaltarían todas. Por eso se **alinea** el guion con la
transcripción:

1. Del `## Guion` de `guion.md` se sacan las palabras que se dicen (sin las
   etiquetas `**Gancho:**` ni las `(pausa)`), marcando las que están entre `**`.
2. Las palabras del guion y las de la transcripción se normalizan: minúsculas, sin
   tildes (`unicodedata`) y sin signos.
3. `difflib.SequenceMatcher` busca los tramos iguales en las dos listas. Las palabras
   de esos tramos que en el guion iban en negrita se escriben como
   `{\1c&H3CC9FF&}SOÑAR{\r}` (`\1c` cambia el color y `\r` vuelve al del estilo).

Si Whisper escribe alguna palabra de otra manera, solo se pierde esa: el paso dice
cuántas se han resaltado ("19 de 19 palabras en negrita del guion resaltadas"). Sin
`guion.md`, o sin negritas (001-pulpo), no se resalta nada.

### Comprobaciones
- Con contorno negro y sin resaltado, el `.ass` nuevo tiene el mismo `md5` que el
  anterior: el cambio no altera nada más.
- `--rehacer subtitulos` de 002-caballo rehízo los subtítulos y el render (y el fondo,
  que el vigilante había borrado; se repartieron otra vez los cortes al azar, con los
  mismos 6 clips, así que los créditos no cambian). Duración 44,1 s, -14,65 LUFS.
- Copias de antes y fotogramas de comparación en `data/pruebas/`.

### Investigación: marcador amarillo detrás de una palabra
La idea: un bloque amarillo detrás de la palabra, con el texto en azul, como en la
foto de perfil. Con ASS y FFmpeg (libass 0.17.1 en el contenedor):

- `BorderStyle=3` dibuja una caja opaca, pero detrás de **toda la línea**, no de una
  palabra.
- Se puede dibujar un rectángulo con los comandos de dibujo de ASS (`\p1`), pero hay
  que saber dónde empieza la palabra y cuánto mide en píxeles. Eso exige medir la
  fuente, y con la biblioteca estándar de Python no se puede.
- Truco que no necesita medir: duplicar cada línea con resaltado en una capa de
  debajo con estilo de caja, con todas las palabras transparentes menos la
  resaltada. Como el texto es idéntico, la caja quedaría justo detrás de la palabra.
  Hay que **probar** si libass dibuja la caja solo detrás de las letras visibles.

Implicaría el doble de líneas en el `.ass` y cajas rectangulares (sin esquinas
redondeadas). Azul sobre amarillo se lee muy bien (10,4:1). Decisión: se deja para
más adelante y, antes de programarlo, se prueba el truco con un fotograma suelto.

## Parte 3: hoja para leer el guion

Antes de grabar, siempre se abre una hoja con el guion y cómo leerlo, como la que se
hizo a mano para 002-caballo. Ahora la genera `scripts/para_leer.py` a partir de
`guion.md`, para que nunca se desfase del guion:

```bash
docker run --rm -t -v "$PWD:/proyecto" shorts-whisper python /proyecto/scripts/para_leer.py 003-rayo
open shorts/003-rayo/para_leer.html
```

- Una frase por línea. Una `(pausa)` va con la frase anterior, y unos puntos
  suspensivos seguidos de minúscula ("soñar... hasta") no cortan la frase.
- La **negrita** sale en color y las `(pausa)` en gris, para no leerlas.
- Arriba: nombre de la grabación, palabras, duración estimada y las notas de lectura
  (las líneas `>` de la cabecera de `guion.md`, como la del final de un bucle).

Comprobación: generada para 002-caballo, solo se diferencia de la hecha a mano en la
duración redondeada (46 s en vez de 45) y una línea de estilo para las notas.

## Parte 4: correcciones del 003-rayo

Al revisar la primera versión salieron varios problemas. Cada uno se arregló en la
causa, no solo en este short.

### Clips: casi todos de IA y muchos sin rayo
- `buscar_clips` se quedaba con los primeros resultados de Pixabay, que devuelve
  también vídeos que solo se parecen a la búsqueda (piedras, cielos estrellados, un
  corazón en la playa al buscar rayos), y priorizaba los verticales, que en Pixabay
  son casi siempre IA. Los rayos grabados de verdad suelen ser horizontales.
- La respuesta de la API trae un campo `isAiGenerated` que **no sale en la
  documentación**. Marcaba bien 7 de los 16 primeros clips, pero no es infalible.
- Ahora: `buscar_clips` exige la primera palabra de la búsqueda en las etiquetas del
  vídeo, pone primero los que no son IA y registra los de IA con la etiqueta `ia`
  (`elegir_clips` los deja para el final). Herramienta nueva `ver_candidatos`: enseña
  los candidatos y sus miniaturas **sin descargar**, y `buscar_clips(ids=...)` descarga
  solo los elegidos.
- En las tormentas reales casi todo el tiempo está oscuro y el rayo dura un instante:
  muchos cortes caían en negro. Con `video.buscar_destellos`, `cortes.py` mide el
  brillo de cada fotograma (`signalstats`) y mueve cada corte para que empiece 0,4 s
  antes de un destello: 12 de 13 cortes con rayo.
- Quedan en la biblioteca 16 clips de rayo que no sirven (no se pueden borrar): se
  usan los 6 nuevos grabados de verdad (`rayo_17` a `rayo_20`, `rayo_22`, `rayo_23`) y
  `rayo_05` (IA, con un rayo muy claro).
- **Corrección del 2026-10-04**: esos clips no llevaban ninguna marca y, como el
  vigilante elige primero los menos usados, el próximo short de rayos los habría
  elegido a ellos. Se revisaron uno a uno (la marca `isAiGenerated` guardada en
  `data/cache/pixabay/` y hojas de contactos en `data/pruebas/rayo_revision_a.png` y
  `_b.png`) y en `biblioteca/indice.csv` se les añadió la etiqueta nueva `descartado`:
  - sin rayo: 04 (habitación de neón), 08 (olas), 09 (piedras), 12 (arrozales), 13 (árbol
    y luna), 15 y 16 (árboles con estrellas);
  - IA o animación en vez de rayos de verdad: 01, 02, 03, 06, 10, 11, 14 y 07 (un rayo
    dibujado).

  `clips_del_tema()` de `material.py` ya no devuelve los descartados. Además, `ia` en
  los 7 que Pixabay marca y en `rayo_05`, que Pixabay **no** marca pero se ve generado:
  así el vigilante lo deja para el final. `rayo_21` no se descarta: es un rayo real,
  casi todo negro con un destello, justo el caso de `buscar_destellos`. Quedan 8 clips
  de rayo utilizables y `evaluar_material` da *suficiente* para 40 s; simulando
  `elegir_clips`, salen 6 clips reales y `rayo_05` se queda fuera.

### El efecto de error, a destiempo
`error_01.mp3` empieza con 0,6 s de silencio, así que sonaba 0,6 s después de la
palabra. `anclar_a_palabras()` resta ahora el silencio inicial de cada efecto
(`silencio_inicial()`, con `silencedetect`). Además, un sonido de error es de broma: en
un short serio queda mal, así que se quitó del 003 y la skill lo reserva para guiones
de tono divertido.

### El final del bucle
El vídeo acababa casi 3 s después de la última palabra (2,5 s de cola más el silencio
del final de `voz.wav`) y el bucle no enlazaba. Con `final.tras_ultima_palabra: 0.5`
acaba medio segundo después de la última palabra transcrita, y el fundido de salida
de la música ya no empieza nunca antes de la última palabra (aquí, 0,5 s).

### Subtítulos
- Whisper escribe las cifras con dígitos («30.000», «20»): las negritas «treinta mil»
  y «veinte» no se resaltaban. Un tramo distinto en el que todo el guion va en negrita
  se resalta igual.
- Whisper partía «30.000» en «30» y «.000,»: `unir_cifras()` los junta.
- «Eso que oyes» salía «Eso qué hay». Se probó a darle el guion a Whisper como pista
  (`initial_prompt`): con el guion entero se quedaba sin memoria (código 137) y con
  medio guion **se saltó 36 palabras e inventó una frase**. Se descartó. Ahora los
  subtítulos se corrigen con el guion (`corregir_con_guion`): en los tramos iguales se
  usa la forma escrita del guion (tildes y puntuación) y en los distintos, si se
  parecen lo bastante o son 1-2 palabras entre tramos iguales, el texto del guion con
  los tiempos de Whisper. En 002-caballo encontró dos errores que ya estaban en su
  vídeo: «un ochado» (uno echado) y «no le despiertes» (no lo despiertes).
- La última palabra, «está», duraba 0,1 s: cada subtítulo dura ahora al menos
  `subtitulos.duracion_min` (0,7 s) sin pisar el siguiente.

Resultado: 37,3 s (0,5 s tras la última palabra), -14,49 LUFS, 2 efectos. La primera
versión queda en `data/pruebas/003-rayo_v1.mp4`.

En total entraron 23 clips de rayo en el índice (`rayo_01` a `rayo_23`; el mensaje del
commit `73eaf2d` dice 13 por error).

## Parte 5: 004-elefante

### Verificación con el estudio original
El dato venía de noticias ("los elefantes se llaman por su nombre"), así que se leyó
el artículo entero: Pardo et al., *Nature Ecology & Evolution*, 2024
(https://doi.org/10.1038/s41559-024-02420-w). La web de Nature pide sesión, así que se
usó una copia del PDF; para leerlo hizo falta `pdftotext`, que se instaló solo dentro
de un contenedor de usar y tirar (`docker run --rm ... apt-get install poppler-utils`),
sin tocar la imagen ni el Mac.

Lo que afirma y lo que no está en `shorts/004-elefante/guion.md`. Resumen: un modelo
acertó a quién iba dirigida una llamada en el 27,5 % de los casos (8 % al azar), las
llamadas probablemente no imitan al receptor (delfines y loros sí) y 17 elefantes
reaccionaron antes a llamadas que eran para ellos. No se sabe qué parte del sonido es
el "nombre", no todas las llamadas lo llevan y no está claro que todos usen el mismo
para el mismo elefante. Por eso el guion dice "algo parecido a un nombre", "al
parecer" y "quizá". Una de las fuentes (PBS) la firma el propio autor: se marcó como
no independiente.

### Clips
Elegidos con `ver_candidatos` y sus miniaturas: 7 elefantes africanos grabados de
verdad, ninguno de IA. Se descartó uno de elefantes asiáticos (el estudio es de
africanos).

### La grabación llegó antes que los clips
El audio se dejó en la bandeja antes de descargar los clips: el vigilante lo apartó a
`data/errores/` ("No hay vídeos con la etiqueta 'elefante'") sin tocar la receta. Con
los clips ya en la biblioteca, bastó con devolverlo a la bandeja.

### 8 segundos muertos al final
La última palabra acababa en 45,5 s y el vídeo duraba 53,5 s: la grabación seguía
5,5 s con ruido de fondo (de -40 a -48 dB, frente a -11/-16 dB de la voz) y un golpe al
pararla, y el vídeo duraba "toda la grabación + 2,5 s". El paso `voz` solo recorta el
silencio del principio. Ahora el vídeo acaba la cola (2,5 s) después de la **última
palabra transcrita** (en un bucle, `tras_ultima_palabra`). La velocidad de lectura
también se medía con toda la grabación (51 s, 2,35 palabras/s): ahora se mide de la
primera palabra a la última, y se recalcularon las cuatro muestras (referencia 2,76).
Resultado: 48,0 s, fundido de la música de 2,5 s desde la última palabra, -14,04 LUFS.
La primera versión queda en `data/pruebas/004-elefante_v1.mp4`.

### Música repetida
004-elefante usa `curiosidad_01`, la misma que 001-pulpo: la skill solo evitaba la canción
del short anterior. Se deja así, pero ahora la skill no repite ninguna canción de los
últimos 5 shorts y elige la que lleva más tiempo sin usarse (si ninguna libre encaja,
propone buscar música nueva).

## Parte 6: 005-caribe

### Del larimar al pez loro
La primera idea era el larimar, pero en Pixabay no hay ni un vídeo de esa piedra
(`ver_candidatos` con "larimar" y "Barahona": 0), y con "blue gemstone" solo salen
diamantes en 3D y zafiros: habría sido enseñar otra piedra como si fuera larimar. El
tema pasó a las playas del Caribe: su arena blanca es, en parte, coral triturado por el
pez loro. Se descartó la arena rosa de Barbuda porque solo aparecía en blogs de
cruceros (las fuentes serias hablan de Bermudas, que no está en el Caribe).

### Clips
Primero en vertical; los horizontales solo si no hay verticales reales. De 8 clips, 4
son verticales: en vertical, casi todo lo tropical era IA. Se descartaron dos playas
de Martinica de arena **negra** (el guion habla de arena blanca), una piscina y una
playa que parecía de Indonesia. Del pez loro solo hay un vídeo real en Pixabay
(`caribe_05`, mordiendo coral). Con un `cortes.txt` manual, el pez loro y el arrecife
(`caribe_05` y `caribe_08`) ocupan el 77 % del vídeo, repitiendo planos, y el pez
loro sale justo al decir «pez loro».

### Chasquidos al principio y al final
La grabación tenía dos chasquidos antes de la primera palabra (0,18 y 0,31-0,43 s) y
un clic de 30 ms medio segundo después de la última. `detectar_voz` solo busca
silencios de 0,5 s, y entre el ruido y la voz no los hay. Ahora `quitar_ruidos()` en
`voz.py` mide, sobre la voz ya procesada, los tramos con sonido (silencios de 0,1 s a
-35 dB) y recorta los sonidos sueltos de menos de 0,15 s separados de la voz al menos
0,2 s o pegados a otro igual (`voz.quitar_ruidos` en `por_defecto.json`). Probado con
copias de las voces de 001 a 005: en 005 quita los dos ruidos; en 002 un ruido 0,8 s
después de «soñando»; en 003, 0,02 s; en 001 y 004, nada. Como la voz empieza 0,51 s
antes, el primer corte del `cortes.txt` se acortó lo mismo para que cada plano siga en
su frase. La versión con ruidos queda en `data/revision/005-caribe.mp4` y la nueva en
`data/revision/005-caribe_sin_ruidos.mp4`.

## Parte 8: publicaciones y métricas

### Por qué
Los 6 primeros shorts ya están publicados en YouTube, Instagram, TikTok y X, pero el
proyecto no lo sabía: `listar_shorts` decía "sin vídeo (publicado o pendiente de
procesar)". Y sin cifras guardadas no hay forma de saber qué técnica, tema o duración
funciona mejor.

### Dos archivos en `shorts/`
- `publicaciones.csv`: short, plataforma, fecha y hora, archivo y `md5`. El `md5` hace
  falta porque el nombre no basta: hay dos `002-caballo.mp4` distintos (el publicado, en
  `listos/`, y el de los colores de la marca, en `revision/`).
- `metricas.csv`: una línea por short, plataforma y momento (`48h` y `7d`). Guarda también
  la técnica, el tema, la música y la duración del short, para comparar sin tener que
  cruzar archivos.

Una celda vacía es "no lo sé" y un 0 es "ninguno": si se mezclan, un dato que falta
contaría como un fracaso. El porcentaje que se quedó a verlo solo lo da YouTube, así que
en las otras plataformas el script no lo deja poner.

Las horas de publicación de 001 a 006 son **aproximadas**: se sabía que el 001 salió hace
unas 20 horas y el 006 hace unas 10. Repartir las demás a partes iguales habría puesto el
004 publicado antes de existir (llegó a `listos/` a las 20:42), así que cada una va poco
después de que su vídeo llegara a `listos/`. Llevan la nota `hora aproximada`.

### Scripts
```bash
docker run --rm -v "$PWD:/proyecto" -w /proyecto/scripts shorts-whisper python registrar_metricas.py pendientes
docker run --rm -v "$PWD:/proyecto" -w /proyecto/scripts shorts-whisper python registrar_metricas.py medida 001-pulpo youtube 48h --visualizaciones 1200 --likes 40
docker run --rm -v "$PWD:/proyecto" -w /proyecto/scripts shorts-whisper python analizar_metricas.py
```

- `metricas.py`: módulo común, sin `print()` porque lo importa el servidor.
- `registrar_metricas.py`: `publicacion`, `medida` y `pendientes`. Valida antes de
  escribir (que el short esté publicado en esa plataforma, enteros donde toca, porcentaje
  de 0 a 100, sin medidas repetidas), dice qué falta y avisa de lo raro: más likes que
  visualizaciones o una medida hecha más de 12 h tarde. `--reemplazar` corrige o completa
  una medida: en la primera versión sustituía la línea entera y, al añadir solo los
  compartidos, se perdía todo lo demás.
- `analizar_metricas.py`: cada plataforma por separado, medianas (un vídeo viral no
  arrastra a su grupo) e interacciones por cada 1000 visualizaciones (si no, gana siempre
  el que más se vio). Marca los grupos de menos de 3 shorts y avisa con menos de 10 por
  plataforma. Con un solo short por tema, comparar temas es comparar shorts sueltos.

### Servidor y skill
- `estado_fabrica` dice qué shorts están publicados, qué medidas tocan ya y las 3
  próximas; `listar_shorts`, dónde y cuándo se publicó cada short y qué medidas le faltan.
- Skill `registrar-metricas`: lee las cifras escritas o de una captura con una tabla de
  equivalencias por plataforma (el "tiempo de visualización" total no es la duración media,
  ni el "porcentaje medio visto" es "se quedaron a verlo"), las enseña y espera el visto
  bueno antes de escribir.

### Comprobaciones
Sobre una copia en `data/pruebas/metricas/` (`--carpeta`), con cifras inventadas: medida
completa, incompleta (avisa de lo que falta), repetida (error), porcentaje en TikTok
(error), likes con decimales (error), completar con `--reemplazar` (conserva lo anterior)
y el análisis con 6 shorts en YouTube y 3 en TikTok (salen todos los avisos). Con los
datos reales: ninguna medida pendiente hoy; la primera es 001-pulpo a las 48 h, el
2026-10-05 a las 13:45.

## Problemas y soluciones

| Síntoma | Causa | Solución | Prevención |
|---------|-------|----------|------------|
| No se pueden poner los créditos al escribir el guion | Los clips los elige el vigilante después de grabar | Créditos pendientes en `publicacion.md` y `creditos.py` después del render | |
| 001-pulpo no tenía fuentes | Se grabó antes de la skill, que exige verificar los datos | Buscarlas después y anotar que confirman lo que ya se dijo | Todos los guiones nuevos pasan por la skill |
| Algunas páginas de fuentes no se dejan abrir (Smithsonian, la revista del estudio) | Bloquean las descargas automáticas (error 403) | Comprobar el contenido por el extracto del buscador y anotarlo en la fuente | |
| La url de un estudio podía cambiar | Las revistas cambian de web | Usar su DOI (`https://doi.org/...`), que siempre lleva al artículo | |
| Muchas webs decían que Instagram admite 30 hashtags | Páginas de contadores sin actualizar | Buscar el anuncio oficial (5 desde diciembre de 2025) | Fecha de comprobación junto a cada límite |
| Buscar cada negrita suelta resaltaría todas las veces que sale esa palabra | "no", "todos" o "soñar" se repiten en el guion | Alinear guion y transcripción con `difflib` | |
| El paso de subtítulos no se entera de que cambian las negritas | Solo depende de la transcripción | `--rehacer subtitulos` | Anotado en la skill |
| `awk` daba los tiempos de los cortes redondeados | Con el idioma del Mac, `awk` espera coma decimal | `LC_ALL=C awk ...` | |
| Con 6 clips de rayo, `evaluar_material` decía "justo" y pedía uno más (003-rayo) | La skill le pasaba la duración estimada (con la cola) y la herramienta vuelve a sumar la cola: 47 s en vez de 44,4 | Pasarle la duración de la voz (palabras / velocidad); con 41,9 s, "suficiente" | Skill, docstring de la herramienta y `CLAUDE.md` dicen que es sin la cola |
| `buscar_clips` descargó clips sin rayo o hechos con IA | Se quedaba con los primeros resultados de Pixabay, que mezcla vídeos parecidos, y priorizaba los verticales | Palabra clave en las etiquetas, primero los que no son IA, `ver_candidatos` con miniaturas y descarga por `ids` | Mirar las miniaturas antes de descargar: lo que entra en la biblioteca no se borra |
| El próximo short de rayos habría elegido los 15 clips que no sirven | Seguían en el índice sin marca y `elegir_clips` empieza por los menos usados | Etiqueta `descartado`, que `clips_del_tema()` excluye; `ia` en `rayo_05` | Al descargar un clip que luego no sirve, descartarlo en el índice en el momento |
| Cortes de tormenta en negro | En lo grabado de verdad, el rayo dura un instante | `video.buscar_destellos`: cada corte empieza antes de un destello | La skill lo pide para temas de un instante |
| El efecto de error sonaba tarde | `error_01.mp3` empieza con 0,6 s de silencio | Restar el silencio inicial al anclar a una palabra | Medir los efectos nuevos con `silencedetect` |
| El bucle no enlazaba | El vídeo acababa casi 3 s después de la última palabra | `final.tras_ultima_palabra` y fundido de la música que no empieza antes de la última palabra | La skill lo pone en los guiones con bucle |
| «Eso qué hay» en vez de «Eso que oyes» | Whisper lo oyó mal | Corregir los subtítulos con el guion | El guion como pista de Whisper no sirve (se salta frases) |
| La transcripción murió sin mensaje | `grep` ocultaba el código de salida; era 137 (sin memoria) | Guardar la salida en un archivo y mirar `$?` | No filtrar con tuberías los comandos largos |
| El vídeo del 004 tenía 8 s muertos al final | Duraba toda la grabación + la cola, y la grabación seguía 5,5 s después de la última frase | El vídeo acaba la cola después de la última palabra transcrita | La velocidad de lectura también se mide de la primera a la última palabra |
| El 004 falló al llegar a la bandeja | La grabación llegó antes de descargar los clips | Devolver el audio de `data/errores/` a la bandeja tras descargarlos | Descargar los clips antes de grabar |
| No se podía leer el PDF del estudio | El Mac no tiene poppler y la web de Nature pide sesión | `pdftotext` en un contenedor de usar y tirar | |
| 004-elefante repitió la música de 001-pulpo | La skill solo evitaba la canción del short anterior | Ninguna canción de los últimos 5 shorts; la que lleva más tiempo sin usarse | Lista de músicas por orden de número en la skill |
| `creditos.py` no habría encontrado al autor de `playa_01` | El índice decía `playa_01.mp4` y el archivo es `.mp3` | Corregir la extensión en `biblioteca/indice.csv` | |
| Chasquidos al principio y al final del 005 | El recorte automático solo quita silencios de 0,5 s o más | `quitar_ruidos()` en `voz.py`: fuera los sonidos sueltos de menos de 0,15 s en los bordes | Valores en `voz.quitar_ruidos` de `por_defecto.json` |
| [Añade aquí otros problemas] | | | |

## Herramientas aprendidas

| Herramienta | Para qué |
|-------------|----------|
| `doi.org` | Enlace permanente a un artículo científico |
| `curl -sI` | Ver solo la respuesta de una web (código y redirección) sin descargarla |
| `re.split`, `re.findall` | Separar las plataformas de una sección y contar urls y hashtags |
| `dict.fromkeys` | Quitar repetidos de una lista sin cambiar el orden |
| `difflib.SequenceMatcher` | Alinear dos listas de palabras parecidas (guion y transcripción) |
| `unicodedata.normalize("NFD")` | Separar las tildes de las letras para quitarlas |
| `{\1c&HBBGGRR&}` y `{\r}` en ASS | Cambiar el color de una palabra y volver al estilo |
| `ffmpeg ... split, hstack, drawtext` | Poner dos versiones de un fotograma lado a lado con su nombre |
| `signalstats` (`YAVG`) | Brillo medio de cada fotograma: encontrar los destellos de un rayo |
| `xstack` | Hojas de contactos con varios fotogramas o miniaturas |
| `silencedetect` | Medir el silencio del principio de un efecto |
| Código de salida 137 | El sistema mató el proceso por falta de memoria |
| `pdftotext` (poppler) en `docker run --rm` | Leer un PDF sin instalar nada en el Mac ni en la imagen |
| `wave` e `int.from_bytes` | Medir el volumen de un WAV de 24 bits con la biblioteca estándar |

## Mis conclusiones
- [Añade aquí qué te parece escribir títulos con curiosidad sin caer en el engaño]
- [Añade aquí qué has aprendido de las diferencias entre plataformas]
- [Añade aquí lo que tú sientas que has aprendido]

## Pendiente
- Publicar 001-pulpo y, al día siguiente, 002-caballo.
- Decidir si se publica el 002-caballo nuevo (colores de la marca y subtítulos
  corregidos con el guion, en `data/revision/002-caballo.mp4`) en lugar del de `data/listos/`.
- Medir los 6 shorts publicados a las 48 h (desde el 2026-10-05) y a los 7 días (desde el 2026-10-10) con la skill `registrar-metricas`.
- Probar el marcador amarillo con un fotograma suelto (parte 2).
- 001-pulpo no tiene negritas en el guion: si se quieren palabras en amarillo, hay
  que marcarlas y rehacer sus subtítulos.
- [Añade aquí otros pendientes]
