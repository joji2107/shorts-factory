# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es

Pipeline que convierte una grabación de voz en un short vertical (1080x1920, 30 fps) con clips de fondo, música con *ducking*, efectos y subtítulos dinámicos. Es un proyecto de aprendizaje (estudiante de ASIX) organizado por fases: cada fase se trabaja en una rama `fase-N`, se documenta en `docs/NN-*.md` y se une a `main` al terminar. La fase 8 añadió el servidor MCP + Claude Code y la búsqueda de clips con la API de Pixabay (Pexels ha pausado la emisión de claves). La fase actual (9) es estrategia de contenido y canales: textos de publicación para YouTube, Instagram, TikTok y X.

Todo el proyecto está en español: código, nombres de variables, comentarios, mensajes de commit y documentación. Mantener ese idioma y el estilo sencillo (solo biblioteca estándar de Python + `faster-whisper`; FFmpeg vía `subprocess`).

## Comandos

Todo se ejecuta dentro del contenedor `shorts-whisper` (Colima en un Mac M2 con 8 GB; la VM tiene 2 CPU y 3 GB), con el proyecto montado en `/proyecto`:

```bash
colima start
docker build -t shorts-ffmpeg .                              # base: Ubuntu + FFmpeg + fuentes
docker build -f Dockerfile.whisper -t shorts-whisper .       # FROM shorts-ffmpeg + Python + faster-whisper

# Vigilante de la bandeja (uso normal)
docker run --rm -t -v "$PWD:/proyecto" -e HF_HOME=/proyecto/data/modelos \
  shorts-whisper python /proyecto/scripts/vigilar_bandeja.py [--plantilla curiosidades] [--intervalo 5]

# Crear un short concreto o rehacer un paso (y los que dependen de él)
docker run --rm -t -v "$PWD:/proyecto" -e HF_HOME=/proyecto/data/modelos \
  shorts-whisper python /proyecto/scripts/crear_short.py 001-pulpo --rehacer subtitulos
```

Pasos válidos para `--rehacer`: `voz`, `transcripcion`, `subtitulos`, `fondo`, `render`.

No hay tests ni linter. Comprobaciones que usa el proyecto:
- `python -m compileall -q scripts` tras editar código.
- `python -m json.tool archivo.json` para validar configuraciones.
- `md5` para comprobar que un cambio de refactorización produce archivos idénticos.

## Arquitectura

**Flujo**: `data/bandeja/NNN-tema.wav` → `vigilar_bandeja.py` mueve el audio a `data/archivo/`, crea la receta `shorts/NNN-tema/config.json` y llama a `crear()` de `crear_short.py` → vídeo final movido a `data/revision/`. Si falla: audio a `data/errores/` con un `.log`. Si el tema del nombre no tiene clips y se parece al menos un 80 % (`PARECIDO_NOMBRE`, `difflib`) a una receta reservada o a un tema del índice, el error lo sugiere («¿Querías decir 008-orionidas?»); no renombra nada. Todo se anota en `data/registro.log`. El usuario mueve a mano de `revision/` a `listos/`.

**Configuración por capas** (`fusionar()` en `crear_short.py`, fusión recursiva de diccionarios; las listas se sustituyen enteras):
1. `config/por_defecto.json`: todos los valores.
2. `config/plantillas/<plantilla>.json`: se **copia** en la receta al crear el short (no se hereda en vivo; para que un short vea cambios de la plantilla hay que borrar su receta).
3. `shorts/<nombre>/config.json`: la receta, solo con lo que cambia. Va a Git.

Las rutas de las configuraciones (`audio_original`, `musica.archivo`, `efectos.archivos`) son relativas a la raíz del proyecto (`RAIZ`).

**Pasos con dependencias** (`DEPENDE_DE` en `crear_short.py`, estilo `make`): cada paso tiene un archivo de resultado en `data/shorts/<nombre>/`; se rehace si falta, si se pide con `--rehacer` o si se rehízo una dependencia. Un módulo por paso en `scripts/pasos/`:
- `voz.py`: recorte (`inicio` numérico o `"auto"` con `silencedetect`) y cadena de filtros de `config.voz.cadena`. Pasa a mono **al principio** de la cadena (si no, la normalización pierde 3 dB). Después, `quitar_ruidos()` (`voz.quitar_ruidos`) recorta los ruidos sueltos del principio y del final (chasquidos, el clic al parar la grabación): sonidos de menos de 0,15 s a -35 dB separados de la voz al menos 0,2 s o pegados a otro igual. `detectar_voz` no los ve porque solo busca silencios de 0,5 s (en 005-caribe había dos chasquidos antes de la primera palabra y un clic tras la última). Si se rehace la voz de un short con `cortes.txt` manual y cambia el inicio, hay que desplazar los cortes.
- `transcripcion.py`: faster-whisper en CPU (`int8`, 2 hilos) → `palabras.json` con tiempos por palabra (+ `.srt`).
- `subtitulos.py`: agrupa palabras (máx. palabras, pausas, puntuación) en un `.ass` de 1080x1920. Colores de la marca en `subtitulos` de `por_defecto.json`, en formato web (`color_texto`, `color_contorno` azul marino `#14213D`, `color_resaltado` amarillo `#FFC93C`); `color_ass()` les da la vuelta, porque ASS los escribe azul-verde-rojo. Con `resaltar_negritas`, las palabras en **negrita** del `## Guion` de `guion.md` salen en amarillo (`{\1c&H3CC9FF&}...{\r}`): el guion se alinea con la transcripción con `difflib` (sin mayúsculas, tildes ni signos) para resaltar la aparición correcta de cada palabra y no todas las iguales. Sin `guion.md` no se resalta nada. El paso no depende de `guion.md`: si cambian las negritas, `--rehacer subtitulos`. Con `corregir_con_guion`, la misma alineación pone en pantalla el texto del guion (con su puntuación y tildes) donde Whisper oyó mal: tramos de igual número de palabras que se parecen al menos un 50 % (`PARECIDO_MIN`), o de 1-2 palabras entre dos tramos iguales («eso que [hay] después» → «oyes»); `palabras.json` no cambia. Un tramo distinto en el que todo el guion va en negrita se resalta igual («treinta mil» → «30.000»); si el tramo mezcla un número en negrita con palabras normales («**doscientos mil** kilómetros» → «200.000 km»), se resaltan solo las palabras transcritas con cifras (`cifra_en_negrita()`, `NUMERO`). El contador «N de M palabras resaltadas» cuenta palabras transcritas, así que «200.000» cuenta una aunque en el guion sean dos. `unir_cifras()` junta las cifras que Whisper parte («30» + «.000,»). Cada subtítulo dura al menos `subtitulos.duracion_min` (0,7 s) sin pisar el siguiente. La pista `initial_prompt` de Whisper con el guion **no** sirve: se saltaba frases enteras e inventaba texto (y con el guion entero se quedaba sin memoria).
- `cortes.py` (`efectos.inicio_min`: segundos iniciales sin efectos): si la receta **no** tiene `cortes.txt` manual, genera `cortes_auto.txt` cortando en la mejor pausa de cada tramo (`corte_min`–`corte_max`, puntuando finales de frase) y reparte los clips por turnos sin repetir plano (`repartir()`, que no imprime y se puede simular; 0,5 s de margen entre usos de un clip). Después `desplazar()` mueve los cortes de cada clip un desfase al azar dentro de lo que le sobra, para que no empiece siempre en el segundo 0. También elige dónde van los efectos automáticos. Con `cortes.txt` manual, el paso `fondo` no depende de la transcripción. Con `video.buscar_destellos` (rayos y otros temas de un instante), `a_destellos()` mueve cada corte para que empiece 0,4 s antes de un destello del clip (brillo medio `signalstats` ≥ 1,5 veces el típico y +15), sin repetir destello ni pisar tramos. Los cortes llegan solo hasta el final del vídeo (cola o `tras_ultima_palabra` después de la última palabra).
- `montaje.py`: `generar_fondo` corta cada línea de la EDL (redondeada a fotogramas, `-frames:v`) y los concatena; `render` mezcla voz/música/efectos en `mezcla.wav`, mide, aplica la ganancia exacta + `alimiter` (no un segundo `loudnorm`, que caía en modo dinámico) y graba los subtítulos. La voz se alarga con `apad` hasta el final del vídeo: `sidechaincompress` (el *ducking*) acaba con su entrada más corta y, sin eso, la música se cortaba al terminar la voz y la cola quedaba muda. Cada efecto se iguala a `efectos.pico` (dB de pico, medido con `volumedetect`) antes de aplicar `efectos.volumen`, porque los archivos de la biblioteca vienen con niveles muy distintos. En `efectos.lista` un efecto puede llevar `momento` (segundo del centro del efecto) o `palabra` (+ `vez`): empieza al terminar esa palabra de la transcripción (`anclar_a_palabras()` en `crear_short.py`). El vídeo acaba `final.cola` (2,5 s) después de la **última palabra transcrita**, no al final de `voz.wav`: lo que se graba después de la última frase (silencio, ruido al parar la grabación) se queda fuera (en 004-elefante eran 5,5 s y el vídeo tenía 8 s muertos). Si `final.tras_ultima_palabra` no es `null` (técnica *bucle*: 0,5), se usa ese tiempo en vez de la cola. El fundido de salida de la música nunca empieza antes de la última palabra (`min(fundido_salida, total - fin de la última palabra)`). En los efectos anclados a una palabra, `anclar_a_palabras()` resta el silencio inicial del archivo (`silencio_inicial()` en `utilidades.py`, `silencedetect` a -45 dB): `error_01` traía 0,6 s y sonaba a destiempo.
- `utilidades.py`: `ejecutar()` (lanza un comando y lanza `RuntimeError` si falla), `duracion()` (ffprobe) y `silencio_inicial()`.

**Lista de cortes (EDL)**: una línea por corte, `clip inicio [largo]`; `clip` es el nombre sin extensión de `data/biblioteca/video/<clip>.mp4`. Sin `largo` se usa `video.segundos_corte`.

**Biblioteca**: `biblioteca/indice.csv` (en Git) registra la licencia de cada archivo con 8 columnas: `archivo,tipo,fuente,autor,url,licencia,fecha,etiquetas` (etiquetas separadas por `;`). Las etiquetas de un vídeo empiezan por el tema, siguen con una o dos generales (singular, sin tildes: `animal`, `mar`) y pueden acabar con descriptivas (`noche`, `nieve`, `ia`). La etiqueta `descartado` (al final) marca un clip que no sirve (no muestra el tema, o es IA o animación sin el tema de verdad): sigue en el índice, porque la biblioteca no se borra y así `buscar_clips` no lo vuelve a descargar, pero `clips_del_tema()` de `material.py` no lo devuelve nunca, así que ni el vigilante ni `evaluar_material` ni `temas_disponibles` lo cuentan. Para descartar un clip se añade la etiqueta en el índice, sin tocar el archivo. El vigilante toma los vídeos cuyo `tipo` es `video` y cuyas etiquetas contienen el tema del nombre del audio (`002-caballo` → `caballo`), sin los descartados, y valida que cada línea tenga todas las columnas. Los archivos multimedia viven en `data/biblioteca/{video,musica,sfx,licencias}`.

**Material** (`scripts/material.py`, común al vigilante y al servidor; sin `print()`): mide los clips, cuenta sus usos (`cortes.txt` de las recetas y `cortes_auto.txt` de `data/shorts/`) y simula el reparto con cortes de `corte_min`, de la media y de `corte_max`. Es *suficiente* si llega en los tres casos y hay al menos 6 clips; *justo* si solo falla con cortes mínimos o hay menos de 6. No se usa una proporción fija: con clips de 6-10 s hacen falta unas 2 veces la duración del short (margen de 0,5 s por corte y final de cada clip desaprovechado). El vigilante pasa a `crear()` una función `despues_de_voz` que recibe la duración real (voz detectada + cola): si la receta no tiene `clips` ni `cortes.txt`, elige con `elegir_clips()` los mínimos que den *suficiente* (al menos 6), empezando por los menos usados y al azar entre empatados, y los escribe en la receta (al rehacer se usan los mismos); si ya los tiene, los evalúa. Si el material no alcanza, lo anota en el registro antes de renderizar. `elegir_clips()` deja para el final los clips con la etiqueta `ia` (generados con IA), para que un short no salga solo con IA si hay otros.

**Receta reservada**: la crea la skill `guion-short` antes de grabar (`guion.md` + `config.json` solo con lo que cambia, sin `audio_original` ni `clips`). Al llegar la grabación, el vigilante la pone encima de la plantilla.

**Velocidad de lectura** (`config/lectura.json`, `scripts/lectura.py`): palabras por segundo para estimar la duración de un guion. Al terminar cada short, el vigilante añade una muestra (palabras transcritas y segundos de la primera a la última palabra, no la duración de `voz.wav`) y la velocidad pasa a ser la mediana de las últimas 5.

**Almacenamiento**: `data/` no va a Git. Los cortes sueltos se borran al unirlos; al terminar un short el vigilante borra `fondo.mp4` y `mezcla.wav` y mueve `final.mp4` (no lo copia). Se conservan `voz.wav` y los archivos de texto para retocar sin volver a transcribir. `data/archivo/` (grabaciones originales) nunca se borra. Un audio nuevo en la bandeja siempre rehace todo desde la voz.

## Servidor MCP

`scripts/servidor_mcp.py` da a Claude herramientas concretas sobre la fábrica:
- `estado_fabrica`: qué hay en bandeja, revisión, listos, errores y `data/entrada/`, qué shorts están publicados, las medidas de métricas que tocan ya y las 3 próximas, más las últimas líneas de `registro.log`.
- `temas_disponibles`: etiquetas de vídeo de `biblioteca/indice.csv` y cuántos clips tiene cada una.
- `listar_shorts`: las recetas de `shorts/`, el estado de su vídeo (`publicado` si está en `publicaciones.csv`), dónde y cuándo se publicó y qué medidas le faltan.
- `preparar_short(grabacion, tema, short="")`: copia una grabación de `data/entrada/` a la bandeja como `NNN-tema`: el de la receta reservada de ese tema si la hay (`short` para elegir si hay varias) o el siguiente número libre (los 9xx se reservan para pruebas).
- `ver_error(nombre)`: el `.log` de `data/errores/`.
- `evaluar_material(tema, duracion_segundos=45)` (duración de la voz, sin la cola: la suma la herramienta): clips del tema con su duración y usos, si llegan sin repetir planos (estado *suficiente*, *justo* o *insuficiente*) y cuántos clips más harían falta.
- `ver_candidatos(busqueda_en_ingles, cantidad=8, orientacion="todas")`: los vídeos que se descargarían, **sin descargarlos**: id, orientación, duración, si Pixabay lo marca como IA (campo `isAiGenerated`, que no sale en su documentación, o etiqueta «ai generated»; no es infalible), etiquetas y miniatura en `data/cache/miniaturas/`. Sirve para elegir viendo las miniaturas.
- `buscar_clips(tema, busqueda_en_ingles="", cantidad=4, etiquetas_generales="", ids="")`: con `ids` (de `ver_candidatos`) descarga exactamente esos; sin `ids`, busca en la API de vídeos de Pixabay clips de 6 s o más cuyas etiquetas contengan la primera palabra de la búsqueda (Pixabay devuelve también vídeos que solo se parecen: piedras o cielos estrellados al buscar rayos), primero los que no son IA y después los verticales. Descarga de cada uno la versión más pequeña cuyo lado corto sea de 1080 px o más (si no hay, la mayor) como `data/biblioteca/video/<tema>_NN.mp4` y añade su línea a `biblioteca/indice.csv`, con la etiqueta descriptiva `ia` si es IA. Etiquetas: el tema y una o dos generales (si el tema ya existe y no se indican, reutiliza las que comparten sus clips; si es nuevo, son obligatorias). Salta los vídeos cuya url ya está en el índice. Máximo 5 por llamada.

Cada fuente de clips es una función (`_buscar_pixabay`) registrada en `FUENTES`, que devuelve los vídeos en un formato común; elegir versión, descargar, numerar y registrar es común. Pexels se podrá añadir así cuando vuelva a dar claves.

Condiciones de Pixabay: las búsquedas se guardan en caché 24 horas en `data/cache/`, no se permiten descargas masivas y hay que indicar que los vídeos son de Pixabay. La clave está en `.env` (`PIXABAY_API_KEY`, nunca va a Git) y llega al contenedor con `docker run --env-file`, en el registro del servidor en Claude Code. En Pixabay la clave viaja dentro de la URL: **nunca se muestra ni se registra una URL completa de la API**, y los errores se describen solo por su código.

No crea shorts directamente: `preparar_short` solo deja el audio en la bandeja, y el vigilante (que tiene que estar en marcha) hace el resto, igual que si el usuario hubiera dejado el archivo a mano. Pasar de `revision/` a `listos/` lo decide siempre el usuario.

El servidor se comunica con Claude por stdio, así que **nunca se usa `print()`** en él: cualquier texto en la salida estándar rompería la comunicación. Las herramientas devuelven el resultado con `return`.

## Skill `guion-short`

`.claude/skills/guion-short/` (se invoca con `/guion-short <tema>` o al pedir un short): escribe el guion (gancho, dato, giro, remate; 100-120 palabras; datos verificados con fuentes; una técnica de interacción rotando) y prepara la receta reservada `shorts/NNN-tema/` con `guion.md` y `config.json` (música que no se haya usado en los últimos 5 shorts, efectos), comprobando el material con `evaluar_material`. Ejemplo de tono: `ejemplo-001-pulpo.md`.

Después prepara `publicacion.md` (paso 5; con `/guion-short NNN-tema` va directo a él en un short que ya existe): 3 títulos de unos 60 caracteres con la favorita marcada (tema al principio, curiosidad que el vídeo resuelve; con *reto inicial* no dan la respuesta), descripción (gancho, 2-3 frases, pregunta ligada a la técnica, fuentes, créditos y 3-5 hashtags en español), comentario fijado de 150 caracteres como máximo y una versión aparte solo para la plataforma que lo necesite (X, con fuentes y créditos en una respuesta). Los bloques ```text van bajo secciones `##` con las plataformas que los usan (`## YouTube, Instagram y TikTok`) y apartados `###` (`Título`, `Descripción`, `Comentario fijado`, `Post`, `Respuesta`).

Hoja para leer: **siempre** que un short está preparado, antes de arrancar el vigilante, se genera `shorts/NNN-tema/para_leer.html` con `scripts/para_leer.py NNN-tema` (en Docker) y se abre con `open`. Sale de `guion.md`: una frase por línea, la negrita en color, `(pausa)` en gris y las líneas `>` de la cabecera como notas de lectura.

`scripts/creditos.py NNN-tema` (en Docker, después del render): toma los clips de la lista de cortes (`cortes.txt` o `cortes_auto.txt`; si no hay, los de la receta), la música y los efectos que suenan, busca sus autores en el índice y sustituye la línea `Créditos:` (versión larga, hasta la primera línea vacía) y la línea `Créditos: ...` (versión corta, para X). Luego mide cada bloque con `LIMITES` (comprobados el 2026-10-03; si cambian, actualizar también la tabla de la skill) y termina con código 1 si alguno se pasa. Repetirlo no cambia nada.

## Publicaciones y métricas

Dos CSV en `shorts/` (van a Git), escritos siempre con `scripts/registrar_metricas.py` (en Docker), nunca a mano:
- `publicaciones.csv`: `short,plataforma,publicado,archivo,md5,notas`. Plataformas `youtube`, `instagram`, `tiktok`, `x`; fecha `AAAA-MM-DD HH:MM` (hora de Madrid). `archivo` y `md5` (8 caracteres) dicen qué versión exacta de `data/listos/` se publicó (hay dos `002-caballo.mp4` distintos). Las horas de 001 a 006 son aproximadas (nota `hora aproximada`).
- `metricas.csv`: una línea por short, plataforma y momento (`48h` o `7d`): `medido`, `visualizaciones`, `se_quedaron_pct` (solo YouTube), `duracion_media_s`, `likes`, `comentarios`, `compartidos`, `seguidores`, y de la ficha `tecnica` (de `guion.md`), `tema`, `musica` y `duracion_s` (del vídeo publicado). Celda vacía = no se sabe; 0 = ninguno.

`scripts/metricas.py` es el módulo común (sin `print()`, lo importa el servidor): lectura y escritura ordenada, `ficha()`, `pendientes()` (una medida es *pendiente* cuando han pasado 48 h o 168 h desde la publicación y no está, y *próxima* si aún no) y `nueva_medida()`, que valida (publicado en esa plataforma, enteros, porcentaje 0-100, sin duplicados) y devuelve lo que falta y avisos (más likes que visualizaciones, medida más de 12 h tarde o pronto). `registrar_metricas.py` tiene `publicacion`, `medida` (`--reemplazar` corrige o completa: lo que no se indica se conserva) y `pendientes`; `--carpeta data/pruebas/...` para probar sin tocar los CSV reales.

`scripts/analizar_metricas.py [--momento] [--plataforma]`: por plataforma (nunca mezcladas), agrupa por técnica, tema y duración (menos de 40 s, 40-45, más de 45) con medianas, % visto e interacciones por cada 1000 visualizaciones. Marca con `*` los grupos de menos de 3 shorts, avisa con menos de 10 shorts por plataforma y cuando cada tema tiene un solo short (tema y técnica mezclados).

Skill `registrar-metricas` (`.claude/skills/registrar-metricas/`): lee cifras escritas o capturas (con tabla de equivalencias por plataforma), las enseña y espera confirmación antes de escribir, avisa de lo que falta y de las medidas pendientes; también anota publicaciones nuevas y explica el análisis sin sacar conclusiones con pocos datos.

## Documentación

Cada fase tiene su bitácora en `docs/` (objetivo, comandos, problemas y soluciones, qué he aprendido). Los huecos entre corchetes del tipo `[Añade aquí...]` o `[completa con...]` son para que los rellene el autor; no inventar su contenido. Al cerrar una fase se actualiza la lista de estado y la tabla de documentos del `README.md`.

## Reglas del proyecto

- Responde siempre en español.
- Explícame qué vas a hacer y por qué antes de hacerlo: estoy aprendiendo.
- Todo se ejecuta en Docker. Los comandos de Python van con la imagen
  `shorts-whisper` y montando el proyecto en `/proyecto`:
  `docker run --rm -t -v "$PWD:/proyecto" -e HF_HOME=/proyecto/data/modelos shorts-whisper ...`
- Nunca borres ni modifiques `data/archivo/`, `data/biblioteca/` ni `data/modelos/`.
  En `data/biblioteca/` solo se pueden **añadir** archivos nuevos, y únicamente mediante la
  herramienta `buscar_clips`; los existentes nunca se modifican ni se borran.
- Nunca subas a Git nada de `data/` ni el archivo `.env`.
- Después de editar código, comprueba la sintaxis:
  `python -m compileall -q /proyecto/scripts`.
- Después de editar un JSON, valídalo con `python -m json.tool`.
- Antes de preparar un short, usa `evaluar_material` con su tema y duración, y descarga
  con `buscar_clips` solo los clips que falten (los que diga `evaluar_material`),
  eligiéndolos antes con `ver_candidatos` y mirando sus miniaturas.
- Los clips generados con IA se pueden usar, pero no pueden ser la norma: como mucho
  1 de cada 6-7 clips de un short (la proporción de 003-rayo). Lo grabado de verdad, primero.
- Documenta cada cambio importante en `docs/`.
- Cuando el usuario corrige algo de un short (volúmenes, fundidos, efectos...), arregla la causa
  en el código o en los valores por defecto, no solo en esa receta, y regístralo (CLAUDE.md,
  la skill si afecta a los guiones y la bitácora) para que no se repita.
- Trabajo con ramas: una por fase. No hagas commits ni push sin preguntarme.
