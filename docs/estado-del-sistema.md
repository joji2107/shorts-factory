# Estado del sistema

> Foto del proyecto el 2026-10-04, en la rama `fase-9` (último commit `a11f6a1`).
> Pensado para alguien que conoce el proyecto hasta el cierre de la fase 8
> (`ac1031a`, que es donde está `main`) y no ha visto lo que vino después.

## 1. Flujo completo, de pedir un guion a publicar

1. **Arrancar la fábrica**: `colima start` y el vigilante en segundo plano, en un
   contenedor llamado `vigilante`:

   ```bash
   docker run -d --rm --name vigilante -v "$PWD:/proyecto" -e HF_HOME=/proyecto/data/modelos \
     shorts-whisper python /proyecto/scripts/vigilar_bandeja.py
   ```

   Se para con `docker kill --signal=SIGINT vigilante` (`docker stop` acaba en
   código 137: Python es el PID 1 e ignora SIGTERM). El servidor MCP `fabrica` también
   corre en Docker: si Claude Code se abre con Colima parado, no conecta y hay que
   reconectarlo con `/mcp`.
2. **Pedir el short**: `/guion-short <tema>` en Claude Code (o pedir "un short
   sobre..."). La skill:
   - escribe el guion (gancho, dato, giro, remate; 100-120 palabras), con cada dato
     comprobado en al menos dos fuentes y la lista de fuentes al final;
   - elige una técnica de interacción distinta de la del short anterior;
   - **espera el visto bueno** del usuario antes de seguir.
3. **Ficha del short** (`shorts/NNN-tema/`): `guion.md` y un `config.json` *reservado*,
   que solo lleva lo que cambia: música, efectos anclados a palabras y, si hace falta,
   `final.tras_ultima_palabra` o `video.buscar_destellos`. No lleva `audio_original` ni
   `clips`. La música no puede ser ninguna de los últimos 5 shorts.
4. **Material**: `evaluar_material(tema, duración de la voz)`. Si falta, y con permiso
   del usuario: `ver_candidatos` → se miran las miniaturas → `buscar_clips(ids=...)` →
   se comprueban los clips descargados con fotogramas, porque lo que entra en la
   biblioteca ya no se borra.
5. **Textos de publicación**: `publicacion.md` con 3 títulos (uno marcado como
   favorito), la descripción, el comentario fijado y la versión para X. Los créditos
   quedan pendientes.
6. **Hoja para leer**: `scripts/para_leer.py NNN-tema` genera `para_leer.html` y se
   abre con `open`.
7. **Grabar**: el audio se guarda como `data/bandeja/NNN-tema.wav`, o en `data/entrada/`
   con cualquier nombre y luego se pide `preparar_short`.
8. **Vigilante**: archiva el audio en `data/archivo/`, pone la receta reservada encima
   de la plantilla y procesa la voz. Con la duración de la voz elige los clips (los
   menos usados primero y los de IA al final) y los escribe en la receta. Después
   transcribe, genera los subtítulos (corregidos y resaltados con el guion), el fondo y
   el render. El vídeo va a `data/revision/`, borra los temporales pesados y anota la
   velocidad de lectura. Si algo falla, el audio va a `data/errores/` con un `.log`.
9. **Revisión**: el usuario mira el vídeo. Si corrige algo, se arregla la causa en el
   código o en los valores por defecto (no solo en la receta) y se rehace con
   `crear_short.py NNN-tema --rehacer <paso>`.
10. **Créditos**: `scripts/creditos.py NNN-tema` rellena los créditos de
    `publicacion.md` con los clips que se usan de verdad, la música y los efectos, y
    mide cada texto con los límites de cada plataforma. Si algo se pasa, termina con
    código 1.
11. **Aprobar y publicar**: el usuario mueve el vídeo a mano de `revision/` a
    `listos/` y lo sube a YouTube, Instagram, TikTok y X copiando los textos de
    `publicacion.md`. La publicación no está automatizada.

## 2. Componentes

### Scripts (`scripts/`)

| Archivo | Líneas | Función |
|---|---|---|
| `vigilar_bandeja.py` | 207 | Vigila `data/bandeja/`: archiva el audio, prepara la receta, elige o comprueba los clips con la duración real (`material_despues_de_voz`), llama a `crear()`, mueve el vídeo a `revision/`, limpia y anota la lectura. Todo queda en `data/registro.log`. |
| `crear_short.py` | 154 | Orquestador: `fusionar()` de las capas de configuración, pasos con dependencias (`DEPENDE_DE`) y `anclar_a_palabras()` para los efectos. También se usa a mano con `--rehacer`. |
| `material.py` | 148 | Lee el índice (y valida las columnas), mide los clips, cuenta sus usos, simula el reparto (estado *suficiente*, *justo* o *insuficiente*) y elige los clips de un short (`elegir_clips`). Lo usan el vigilante y el servidor; no usa `print()`. |
| `lectura.py` | 46 | Velocidad de lectura: mediana de las últimas 5 muestras de `config/lectura.json`. |
| `para_leer.py` | 112 | **Nuevo.** Hoja HTML para leer el guion: una frase por línea, la negrita en color, las pausas en gris y las notas de lectura. |
| `creditos.py` | 225 | **Nuevo.** Créditos de los archivos usados, sacados del índice, y medida de cada texto con `LIMITES` (comprobados el 2026-10-03). |
| `servidor_mcp.py` | 603 | Servidor MCP por stdio (sin `print()`); ver la tabla de abajo. |

### Pasos (`scripts/pasos/`)

| Módulo | Resultado | Función |
|---|---|---|
| `voz.py` | `voz.wav` | Inicio automático (`silencedetect`), cadena de filtros (mono primero) y, **nuevo**, `quitar_ruidos()`: recorta los chasquidos sueltos del principio y del final. |
| `transcripcion.py` | `palabras.json` | faster-whisper `medium`, CPU, `int8`, 2 hilos, con tiempos por palabra. |
| `subtitulos.py` | `subtitulos.ass` | Agrupa las palabras (3 como máximo). **Nuevo**: colores de la marca, negritas del guion en amarillo, corrección con el guion (`difflib`), `unir_cifras()` y duración mínima de 0,7 s. |
| `cortes.py` | `cortes_auto.txt` | Corta en las pausas, reparte los clips sin repetir plano y desplaza el inicio de cada uno. **Nuevo**: `a_destellos()` para temas de un instante. También elige dónde van los efectos automáticos. |
| `montaje.py` | `fondo.mp4`, `final.mp4` | Fondo a partir de la lista de cortes (encuadre `desenfocado` o `relleno`). Render: mezcla, ducking, efectos igualados a `efectos.pico`, ganancia medida + `alimiter`, y subtítulos. **Nuevo**: el final se calcula desde la última palabra. |
| `utilidades.py` | — | `ejecutar()`, `duracion()` y, **nuevo**, `silencio_inicial()`. |

### Herramientas del servidor MCP

| Herramienta | Parámetros | Qué hace |
|---|---|---|
| `estado_fabrica` | `lineas_registro=15` | Bandeja, revisión, listos, errores, entrada y el final del registro. |
| `temas_disponibles` | — | Etiquetas de vídeo del índice y cuántos clips tiene cada una. |
| `listar_shorts` | — | Recetas de `shorts/` y el estado de su vídeo. |
| `preparar_short` | `grabacion`, `tema`, `short=""` | Copia una grabación de `data/entrada/` a la bandeja como `NNN-tema`. Usa la receta reservada del tema si la hay; los 9xx son pruebas. |
| `ver_error` | `nombre` | El `.log` de `data/errores/`. |
| `evaluar_material` | `tema`, `duracion_segundos=45` | Dice si los clips del tema llegan sin repetir planos. La duración es la de la voz **sin la cola**, porque la herramienta ya la suma. |
| `ver_candidatos` | `busqueda_en_ingles`, `cantidad=8` (máx. 12), `orientacion="todas"\|"vertical"\|"horizontal"` | **Nueva.** Candidatos de Pixabay **sin descargarlos**: id, orientación, duración, marca de IA, etiquetas y miniatura en `data/cache/miniaturas/`. |
| `buscar_clips` | `tema`, `busqueda_en_ingles=""`, `cantidad=4` (máx. 5), `etiquetas_generales=""`, `ids=""` | Descarga a `data/biblioteca/video/<tema>_NN.mp4` y añade la línea al índice. **Nuevo**: con `ids` descarga exactamente esos; sin ellos, exige la palabra clave en las etiquetas, pone primero los clips que no son IA y etiqueta `ia` los que sí. |

La clave de Pixabay llega al contenedor con `--env-file` desde `.env`. El servidor
nunca muestra ni registra una URL completa de la API, porque la clave viaja dentro de
ella.

### Skills

Solo hay una: **`guion-short`** (`.claude/skills/guion-short/`). Con un tema hace los
pasos 2 a 6 del flujo: guion, ficha, material, cierre con la hoja para leer y
publicación. Con un short que ya existe (`/guion-short 003-rayo`) va directa a los
textos de publicación. Al cargarse recibe la situación actual: velocidad de lectura,
técnicas y músicas de cada short, último número, música y efectos del índice. El tono
de ejemplo está en `ejemplo-001-pulpo.md`.

## 3. Configuración

### `config/por_defecto.json` (valores clave)

| Bloque | Valores |
|---|---|
| `voz` | `inicio: 0`; `quitar_ruidos`: umbral -35 dB, sonidos de 0,15 s como máximo, hueco de 0,2 s, margen de 0,15 s; cadena: paso alto a 80 Hz → `afftdn` → ecualización → doble compresión → `loudnorm` a -14 LUFS |
| `transcripcion` | modelo `medium`, idioma `es` |
| `subtitulos` | 3 palabras como máximo, pausa de corte 0,45 s, mayúsculas, DejaVu Sans 80, margen vertical 560; texto `#FFFFFF`, contorno `#14213D` de 7, resaltado `#FFC93C`; `resaltar_negritas` y `corregir_con_guion` activados; `duracion_min` 0,7 s |
| `video` | encuadre `desenfocado`; cortes de 1,5 a 4 s (3 s sin `largo` en la lista de cortes); `pausa_corte` 0,15; `buscar_destellos: false` |
| `musica` | volumen 0,25; fundidos de 1 s (entrada) y 3 s (salida); ducking: umbral 0,042, ratio 6, ataque 20 ms, relajación 400 ms |
| `efectos` | volumen 0,5 sobre un pico igualado a -3 dB; 0 automáticos; `separacion_min` 8 s; `inicio_min` 3 s |
| `final` | `cola` 2,5 s después de la última palabra; `tras_ultima_palabra: null` (0,5 en los bucles); `loudnorm` I=-14, TP=-2; `crf` 20 |

### Plantillas

Solo existe `config/plantillas/curiosidades.json`:

- `voz`: inicio automático (umbral de silencio de -40 dB, margen de 0,15 s).
- `musica`: `curiosidad_01.mp3`. Las recetas de la skill la sustituyen siempre.
- `efectos`: 3 automáticos con `whoosh_01` y `whoosh_02`.

### `config/lectura.json`

Referencia: 2,90 palabras/s (mediana de las últimas 5 muestras: 002 a 006).

## 4. Cambios desde que se cerró la fase 8

Son 7 commits (`580af6c` → `a11f6a1`), todos del 2026-10-03. 39 archivos cambiados y
unas 2400 líneas añadidas. Agrupados por tema:

### Publicación en las redes
- **`publicacion.md` en la skill (paso 5)** y **`creditos.py`**. *Por qué*: los clips
  no se conocen hasta después de grabar, así que los créditos no pueden escribirse a
  mano en el guion. Además, los límites de cada plataforma son distintos y contar
  caracteres a ojo falla (en X cada URL cuenta 23).
- **Fuentes del 001-pulpo**, añadidas después. *Por qué*: se grabó antes de que la
  skill exigiera fuentes.

### Subtítulos
- **Colores de la marca** (blanco, contorno azul marino, resaltado amarillo), escritos
  en formato web en la configuración; `color_ass()` los pasa al orden de ASS. *Por
  qué*: dar identidad al canal. Se eligió el contorno azul después de comparar
  fotogramas sobre clips claros y oscuros.
- **Negritas del guion en amarillo**, alineando guion y transcripción con `difflib`.
  *Por qué*: buscar cada palabra suelta resaltaría todas sus apariciones ("no",
  "todos").
- **Corrección con el guion**, `unir_cifras()` y duración mínima. *Por qué*: Whisper
  oía mal algunas frases («Eso qué hay» por «Eso que oyes»), partía «30.000» y dejaba
  la última palabra 0,1 s en pantalla. Pasarle el guion a Whisper como pista se
  descartó: se saltaba frases e inventaba texto.

### Clips de vídeo
- **`ver_candidatos`, descarga por `ids`, palabra clave obligatoria y etiqueta `ia`**.
  *Por qué*: en el 003-rayo, `buscar_clips` bajó vídeos sin rayos y casi todos de IA,
  y lo descargado no se puede borrar.
- **Regla de la IA**: como mucho 1 de cada 6-7 clips, y `elegir_clips` deja los de IA
  para el final. *Por qué*: lo grabado de verdad, primero.
- **`video.buscar_destellos`**. *Por qué*: en las tormentas reales casi todo está
  oscuro y los cortes caían en negro.

### Audio y final del vídeo
- **El vídeo acaba 2,5 s después de la última palabra transcrita**, y no al final de
  la grabación. *Por qué*: el 004-elefante tenía 8 s muertos.
- **`final.tras_ultima_palabra`** y fundido de la música que no empieza antes de la
  última palabra. *Por qué*: el bucle del 003-rayo no enlazaba.
- **`quitar_ruidos()`**. *Por qué*: chasquidos antes de la primera palabra y un clic
  al final en el 005-caribe.
- **Silencio inicial de los efectos descontado** al anclarlos a una palabra. *Por
  qué*: `error_01` traía 0,6 s de silencio y sonaba tarde.

### Guiones y skill
- **Hoja para leer** generada desde `guion.md`. *Por qué*: antes se hacía a mano y
  podía desfasarse del guion.
- **Música sin repetir en 5 shorts**. *Por qué*: el 004 repitió la del 001.
- **Velocidad de lectura medida de la primera a la última palabra**. *Por qué*: el
  silencio grabado al final bajaba la velocidad.
- **`evaluar_material` recibe la duración sin la cola**. *Por qué*: la cola se sumaba
  dos veces y pedía clips de más.

### Shorts nuevos
003-rayo, 004-elefante (verificado con el estudio original), 005-caribe (con
`cortes.txt` manual) y 006-columna, cada uno con sus clips en el índice.

### Sin commit todavía
- `docs/07-automatizacion.md`: sección "Hora del registro". Explica `ENV TZ=Europe/Madrid`
  en `Dockerfile.whisper`; esa línea ya está en el repositorio desde `a3ee82e`.

## 5. Estado de los datos

### Biblioteca (`biblioteca/indice.csv`: 75 archivos; los multimedia coinciden uno a uno con el índice)

**Vídeo por tema** (56 clips):

| Tema | Clips | Fuente |
|---|---|---|
| rayo | 23 | Pixabay |
| caribe | 8 | Pixabay |
| columna | 7 | Pixabay |
| elefante | 7 | Pixabay |
| caballo | 6 | Pixabay |
| pulpo | 5 | Pexels |

**Música por estado de ánimo** (primera etiqueta; 11 canciones):

| Ánimo | Canciones | Usada en |
|---|---|---|
| alegria | `alegria_01`, `alegria_02`, `alegria_03` | `alegria_03`: 002 |
| misterio | `misterio_01`, `misterio_02`, `misterio_03` | `misterio_01`: 003 |
| relajada | `relajada_01`, `relajada_02` | — |
| curiosidad | `curiosidad_01` | 001 y 004 |
| playa | `playa_01` | 005 |
| ciencia | `ciencia_01` | 006 |

El próximo short no puede usar `alegria_03`, `misterio_01`, `curiosidad_01`,
`playa_01` ni `ciencia_01`. Sin usar nunca: `alegria_01`, `alegria_02`,
`relajada_01`, `relajada_02`, `misterio_02` y `misterio_03`.

**Efectos por tipo** (8):

| Tipo | Archivos | Uso |
|---|---|---|
| whoosh | `whoosh_01`, `whoosh_02` | en todos los shorts |
| riser | `riser_01`, `riser_02` | `riser_01` en 002, 004, 005 y 006; `riser_02` en 003 |
| ding | `ding_01`, `ding_02` | `ding_01` en 004, 005 y 006; `ding_02` nunca |
| error | `error_01`, `error_02` | `error_01` en 002; `error_02` nunca |

### Shorts

| Short | Técnica | Música | Clips | Vídeo |
|---|---|---|---|---|
| 001-pulpo | promesa del siguiente dato | curiosidad_01 | 5 (`cortes.txt` manual) | `listos/` (43,6 s) |
| 002-caballo | reto inicial | alegria_03 | 6 | `listos/` (44,1 s) y una versión nueva en `revision/`, con los colores de la marca y los subtítulos corregidos, pendiente de decidir cuál se publica |
| 003-rayo | bucle | misterio_01 | 7 (1 de IA) | `listos/` (37,3 s) |
| 004-elefante | pregunta de opinión ligera | curiosidad_01 | 6 | `listos/` (48,0 s) |
| 005-caribe | promesa del siguiente dato | playa_01 | 4 (`cortes.txt` manual) | `listos/005-caribe_sin_ruidos.mp4` (44,0 s); la versión con ruidos sigue en `revision/` |
| 006-columna | reto inicial | ciencia_01 | 6 | `listos/` (41,4 s) |
| 900-pulpo | — | curiosidad_01 | 5 | receta de prueba |

Los 6 tienen `publicacion.md` con los créditos completos y del 002 al 006 tienen hoja
para leer. La técnica *pregunta de respuesta fácil* aún no se ha usado. En el
repositorio no queda constancia de qué se ha publicado ya.

### Espacio en `data/` (3,2 GB)

| Carpeta | Tamaño | Nota |
|---|---|---|
| `modelos/` | 1,9 GB | modelo de Whisper |
| `biblioteca/` | 771 MB | no se toca |
| `listos/` | 178 MB | |
| `shorts/` | 111 MB | unos 80 MB son `fondo.mp4` y `mezcla.wav` que quedaron en 002 y 003 tras rehacerlos a mano |
| `pruebas/` | 78 MB | comparaciones y versiones anteriores |
| `revision/` | 72 MB | |
| `archivo/` | 65 MB | grabaciones originales, no se toca |
| `cache/` | 46 MB | 42 MB de miniaturas |
| `entrada/` | 12 MB | archivos de prueba |

## 6. Métricas

`shorts/metricas.csv` **no existe**: no hay ningún archivo de métricas en el proyecto,
así que no hay nada que resumir. Ver el punto pendiente en la sección 7.

## 7. Problemas conocidos, pendientes y mejoras

### Problemas conocidos
- **Los clips de rayo viejos no llevan la etiqueta `ia`**. Ningún clip del índice la
  tiene, ni siquiera `rayo_05`, que la bitácora identifica como IA. Los clips
  `rayo_01` a `rayo_16` se descargaron antes de la corrección. Como `elegir_clips`
  empieza por los menos usados, un próximo short de rayos elegiría justo esos 16, que
  la bitácora da por inservibles (sin rayo o de IA). Habría que etiquetarlos en el
  índice (está en Git, no en `data/`) o marcarlos de algún modo para que no se elijan.
- **Rehacer el fondo cambia los cortes al azar.** El paso `fondo` vuelve a llamar a
  `crear_edl()` aunque ya exista `cortes_auto.txt`. Como el vigilante borra
  `fondo.mp4`, un `--rehacer subtitulos` posterior regenera el fondo con otros cortes
  (pasó en el 002). Puede cambiar los créditos y lo que ya se había revisado.
- **La duración para elegir clips se mide con todo `voz.wav` + la cola**, no hasta la
  última palabra (todavía no hay transcripción en ese momento). Si la grabación tiene
  silencio al final, o en un bucle (0,5 s en vez de 2,5), se piden más clips de los
  necesarios.
- **Números de línea del error del índice**: `leer_indice()` cuenta las filas que
  devuelve `csv.DictReader`, que se salta las líneas vacías. El índice tiene una
  línea vacía en la 61, así que un error a partir de ahí diría un número uno menor.
- **`crear_short.py` a mano no limpia**: no borra `fondo.mp4` ni `mezcla.wav` (unos 80 MB
  en 002 y 003).
- **Restos en las carpetas**: `data/errores/004-elefante.log` es de un fallo ya
  resuelto (el vigilante no lo borra cuando el short sale bien) y `data/revision/`
  tiene la versión vieja del 005.
- **El servidor MCP no conecta si Colima está parado** al abrir Claude Code.

### Pendientes
- Decidir qué versión del 002-caballo se publica.
- Publicar 001-pulpo y, al día siguiente, 002-caballo (el remate del 001 lo promete).
- Probar el marcador amarillo detrás de una palabra con un fotograma suelto.
- 001-pulpo no tiene negritas en el guion: si se quieren palabras en amarillo, hay que
  marcarlas y rehacer sus subtítulos.
- Bitácora de la fase 9: falta la parte 7 (006-columna), los commits de las partes 5
  a 7 en la tabla y actualizar los pendientes (el de reconectar el MCP ya está hecho).
- Hacer commit de la sección "Hora del registro" de `docs/07`.
- Empezar a registrar métricas (`shorts/metricas.csv`), por ejemplo: short,
  plataforma, fecha de publicación, visualizaciones, retención media, me gusta y
  comentarios. Sin datos no se puede saber qué técnicas o temas funcionan mejor.
- Cerrar la fase 9: estado y tabla de documentos del `README.md` y unir a `main`.

### Partes del código que mejoraría
- **`cortes.py` / `crear_short.py`**: reutilizar `cortes_auto.txt` si existe y la
  transcripción no se ha rehecho; repartir los cortes otra vez solo cuando se pida.
- **`material.py`**: una forma de excluir clips (una etiqueta como `descartado`) para
  no depender de que nunca se elijan.
- **`vigilar_bandeja.py`**: borrar el `.log` de errores antiguo de un short cuando sale
  bien, y calcular la duración para los clips con el final real (por ejemplo,
  recortando también el silencio final en el paso `voz`).
- **Recetas**: las que usan `efectos.lista` arrastran `automaticos` y `archivos` de la
  plantilla, que no se usan. No es un error, pero confunde al leerlas.
- **Variedad de efectos**: del 004 al 006 se repite la misma combinación (`ding_01`,
  `riser_01`, `whoosh_01`). La skill podría rotarlos como hace con la música.
- **Sin tests**: la lógica pura (`repartir`, `alinear`, `corregir_con_guion`,
  `unir_cifras`, `fusionar`, `medir`) se podría probar con `unittest` de la biblioteca
  estándar. Ahora las comprobaciones son a mano (`md5`, fotogramas).
- **`servidor_mcp.py`** (603 líneas) mezcla las herramientas con el cliente de
  Pixabay. Separar la parte de Pixabay a su propio módulo facilitaría añadir Pexels.

## Seguridad

- `.env` está en `.gitignore` y **nunca se ha subido**. Se comprobó el 2026-10-04 con
  `git log --all --full-history` y recorriendo el árbol de todos los commits de todas
  las ramas, sin ningún resultado.
- El valor de la clave tampoco aparece en ningún commit ni en ningún archivo del
  proyecto fuera de `data/` (búsqueda con `git grep` en todos los commits, sin mostrar
  la clave).
- Este documento no incluye claves, contraseñas, correos ni datos personales. Los
  autores de los clips están en el índice y en los créditos, no aquí.
