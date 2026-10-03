# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es

Pipeline que convierte una grabación de voz en un short vertical (1080x1920, 30 fps) con clips de fondo, música con *ducking*, efectos y subtítulos dinámicos. Es un proyecto de aprendizaje (estudiante de ASIX) organizado por fases: cada fase se trabaja en una rama `fase-N`, se documenta en `docs/NN-*.md` y se une a `main` al terminar. La fase actual (8) es servidor MCP + Claude Code y búsqueda de clips con la API de Pixabay (Pexels ha pausado la emisión de claves).

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

**Flujo**: `data/bandeja/NNN-tema.wav` → `vigilar_bandeja.py` mueve el audio a `data/archivo/`, crea la receta `shorts/NNN-tema/config.json` y llama a `crear()` de `crear_short.py` → vídeo final movido a `data/revision/`. Si falla: audio a `data/errores/` con un `.log`. Todo se anota en `data/registro.log`. El usuario mueve a mano de `revision/` a `listos/`.

**Configuración por capas** (`fusionar()` en `crear_short.py`, fusión recursiva de diccionarios; las listas se sustituyen enteras):
1. `config/por_defecto.json`: todos los valores.
2. `config/plantillas/<plantilla>.json`: se **copia** en la receta al crear el short (no se hereda en vivo; para que un short vea cambios de la plantilla hay que borrar su receta).
3. `shorts/<nombre>/config.json`: la receta, solo con lo que cambia. Va a Git.

Las rutas de las configuraciones (`audio_original`, `musica.archivo`, `efectos.archivos`) son relativas a la raíz del proyecto (`RAIZ`).

**Pasos con dependencias** (`DEPENDE_DE` en `crear_short.py`, estilo `make`): cada paso tiene un archivo de resultado en `data/shorts/<nombre>/`; se rehace si falta, si se pide con `--rehacer` o si se rehízo una dependencia. Un módulo por paso en `scripts/pasos/`:
- `voz.py`: recorte (`inicio` numérico o `"auto"` con `silencedetect`) y cadena de filtros de `config.voz.cadena`. Pasa a mono **al principio** de la cadena (si no, la normalización pierde 3 dB).
- `transcripcion.py`: faster-whisper en CPU (`int8`, 2 hilos) → `palabras.json` con tiempos por palabra (+ `.srt`).
- `subtitulos.py`: agrupa palabras (máx. palabras, pausas, puntuación) en un `.ass` de 1080x1920.
- `cortes.py`: si la receta **no** tiene `cortes.txt` manual, genera `cortes_auto.txt` cortando en la mejor pausa de cada tramo (`corte_min`–`corte_max`, puntuando finales de frase) y reparte los clips por turnos sin repetir plano (`repartir()`, que no imprime y se puede simular; 0,5 s de margen entre usos de un clip). Después `desplazar()` mueve los cortes de cada clip un desfase al azar dentro de lo que le sobra, para que no empiece siempre en el segundo 0. También elige dónde van los efectos automáticos. Con `cortes.txt` manual, el paso `fondo` no depende de la transcripción.
- `montaje.py`: `generar_fondo` corta cada línea de la EDL (redondeada a fotogramas, `-frames:v`) y los concatena; `render` mezcla voz/música/efectos en `mezcla.wav`, mide, aplica la ganancia exacta + `alimiter` (no un segundo `loudnorm`, que caía en modo dinámico) y graba los subtítulos.
- `utilidades.py`: `ejecutar()` (lanza un comando y lanza `RuntimeError` si falla) y `duracion()` (ffprobe).

**Lista de cortes (EDL)**: una línea por corte, `clip inicio [largo]`; `clip` es el nombre sin extensión de `data/biblioteca/video/<clip>.mp4`. Sin `largo` se usa `video.segundos_corte`.

**Biblioteca**: `biblioteca/indice.csv` (en Git) registra la licencia de cada archivo con 8 columnas: `archivo,tipo,fuente,autor,url,licencia,fecha,etiquetas` (etiquetas separadas por `;`). Las etiquetas de un vídeo empiezan por el tema, siguen con una o dos generales (singular, sin tildes: `animal`, `mar`) y pueden acabar con descriptivas (`noche`, `nieve`). El vigilante toma los vídeos cuyo `tipo` es `video` y cuyas etiquetas contienen el tema del nombre del audio (`002-caballo` → `caballo`), y valida que cada línea tenga todas las columnas.

**Material** (`scripts/material.py`, común al vigilante y al servidor; sin `print()`): mide los clips, cuenta sus usos (`cortes.txt` de las recetas y `cortes_auto.txt` de `data/shorts/`) y simula el reparto con cortes de `corte_min`, de la media y de `corte_max`. Es *suficiente* si llega en los tres casos y hay al menos 6 clips; *justo* si solo falla con cortes mínimos o hay menos de 6. No se usa una proporción fija: con clips de 6-10 s hacen falta unas 2 veces la duración del short (margen de 0,5 s por corte y final de cada clip desaprovechado). Si la receta no tiene `clips` ni `cortes.txt`, el vigilante elige con `elegir_clips()` los mínimos que den *suficiente* (al menos 6), empezando por los menos usados y al azar entre empatados, y los escribe en la receta (al rehacer se usan los mismos). Los archivos multimedia viven en `data/biblioteca/{video,musica,sfx,licencias}`.

**Almacenamiento**: `data/` no va a Git. Los cortes sueltos se borran al unirlos; al terminar un short el vigilante borra `fondo.mp4` y `mezcla.wav` y mueve `final.mp4` (no lo copia). Se conservan `voz.wav` y los archivos de texto para retocar sin volver a transcribir. `data/archivo/` (grabaciones originales) nunca se borra. Un audio nuevo en la bandeja siempre rehace todo desde la voz.

## Servidor MCP

`scripts/servidor_mcp.py` da a Claude herramientas concretas sobre la fábrica:
- `estado_fabrica`: qué hay en bandeja, revisión, listos, errores y `data/entrada/`, más las últimas líneas de `registro.log`.
- `temas_disponibles`: etiquetas de vídeo de `biblioteca/indice.csv` y cuántos clips tiene cada una.
- `listar_shorts`: las recetas de `shorts/` y el estado de su vídeo.
- `preparar_short(grabacion, tema)`: copia una grabación de `data/entrada/` a la bandeja como `NNN-tema` con el siguiente número libre (los 9xx se reservan para pruebas).
- `ver_error(nombre)`: el `.log` de `data/errores/`.
- `evaluar_material(tema, duracion_segundos=45)`: clips del tema con su duración y usos, si llegan sin repetir planos (estado *suficiente*, *justo* o *insuficiente*) y cuántos clips más harían falta.
- `buscar_clips(tema, busqueda_en_ingles, cantidad=4, etiquetas_generales="")`: busca en la API de vídeos de Pixabay clips de 6 s o más (primero los verticales; los horizontales sirven por el fondo desenfocado), descarga de cada uno la versión más pequeña cuyo lado corto sea de 1080 px o más (si no hay, la mayor) como `data/biblioteca/video/<tema>_NN.mp4` y añade su línea a `biblioteca/indice.csv`. Etiquetas: el tema y una o dos generales (si el tema ya existe y no se indican, reutiliza las que comparten sus clips; si es nuevo, son obligatorias). Salta los vídeos cuya url ya está en el índice. Máximo 5 por llamada.

Cada fuente de clips es una función (`_buscar_pixabay`) registrada en `FUENTES`, que devuelve los vídeos en un formato común; elegir versión, descargar, numerar y registrar es común. Pexels se podrá añadir así cuando vuelva a dar claves.

Condiciones de Pixabay: las búsquedas se guardan en caché 24 horas en `data/cache/`, no se permiten descargas masivas y hay que indicar que los vídeos son de Pixabay. La clave está en `.env` (`PIXABAY_API_KEY`, nunca va a Git) y llega al contenedor con `docker run --env-file`, en el registro del servidor en Claude Code. En Pixabay la clave viaja dentro de la URL: **nunca se muestra ni se registra una URL completa de la API**, y los errores se describen solo por su código.

No crea shorts directamente: `preparar_short` solo deja el audio en la bandeja, y el vigilante (que tiene que estar en marcha) hace el resto, igual que si el usuario hubiera dejado el archivo a mano. Pasar de `revision/` a `listos/` lo decide siempre el usuario.

El servidor se comunica con Claude por stdio, así que **nunca se usa `print()`** en él: cualquier texto en la salida estándar rompería la comunicación. Las herramientas devuelven el resultado con `return`.

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
  con `buscar_clips` solo los clips que falten (los que diga `evaluar_material`).
- Documenta cada cambio importante en `docs/`.
- Trabajo con ramas: una por fase. No hagas commits ni push sin preguntarme.
