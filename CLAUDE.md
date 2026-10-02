# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es

Pipeline que convierte una grabación de voz en un short vertical (1080x1920, 30 fps) con clips de fondo, música con *ducking*, efectos y subtítulos dinámicos. Es un proyecto de aprendizaje (estudiante de ASIX) organizado por fases: cada fase se trabaja en una rama `fase-N`, se documenta en `docs/NN-*.md` y se une a `main` al terminar. La fase actual (8) es servidor MCP + Claude Code y búsqueda de clips con la API de Pexels.

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
- `cortes.py`: si la receta **no** tiene `cortes.txt` manual, genera `cortes_auto.txt` cortando en la mejor pausa de cada tramo (`corte_min`–`corte_max`, puntuando finales de frase) y reparte los clips por turnos sin repetir plano. También elige dónde van los efectos automáticos. Con `cortes.txt` manual, el paso `fondo` no depende de la transcripción.
- `montaje.py`: `generar_fondo` corta cada línea de la EDL (redondeada a fotogramas, `-frames:v`) y los concatena; `render` mezcla voz/música/efectos en `mezcla.wav`, mide, aplica la ganancia exacta + `alimiter` (no un segundo `loudnorm`, que caía en modo dinámico) y graba los subtítulos.
- `utilidades.py`: `ejecutar()` (lanza un comando y lanza `RuntimeError` si falla) y `duracion()` (ffprobe).

**Lista de cortes (EDL)**: una línea por corte, `clip inicio [largo]`; `clip` es el nombre sin extensión de `data/biblioteca/video/<clip>.mp4`. Sin `largo` se usa `video.segundos_corte`.

**Biblioteca**: `biblioteca/indice.csv` (en Git) registra la licencia de cada archivo con 8 columnas: `archivo,tipo,fuente,autor,url,licencia,fecha,etiquetas` (etiquetas separadas por `;`). El vigilante elige los clips cuyo `tipo` es `video` y cuyas etiquetas contienen el tema del nombre del audio (`002-caballo` → `caballo`), y valida que cada línea tenga todas las columnas. Los archivos multimedia viven en `data/biblioteca/{video,musica,sfx,licencias}`.

**Almacenamiento**: `data/` no va a Git. Los cortes sueltos se borran al unirlos; al terminar un short el vigilante borra `fondo.mp4` y `mezcla.wav` y mueve `final.mp4` (no lo copia). Se conservan `voz.wav` y los archivos de texto para retocar sin volver a transcribir. `data/archivo/` (grabaciones originales) nunca se borra. Un audio nuevo en la bandeja siempre rehace todo desde la voz.

## Documentación

Cada fase tiene su bitácora en `docs/` (objetivo, comandos, problemas y soluciones, qué he aprendido). Los huecos entre corchetes del tipo `[Añade aquí...]` o `[completa con...]` son para que los rellene el autor; no inventar su contenido. Al cerrar una fase se actualiza la lista de estado y la tabla de documentos del `README.md`.

## Reglas del proyecto

- Responde siempre en español.
- Explícame qué vas a hacer y por qué antes de hacerlo: estoy aprendiendo.
- Todo se ejecuta en Docker. Los comandos de Python van con la imagen
  `shorts-whisper` y montando el proyecto en `/proyecto`:
  `docker run --rm -t -v "$PWD:/proyecto" -e HF_HOME=/proyecto/data/modelos shorts-whisper ...`
- Nunca borres ni modifiques `data/archivo/`, `data/biblioteca/` ni `data/modelos/`.
- Nunca subas a Git nada de `data/` ni el archivo `.env`.
- Después de editar código, comprueba la sintaxis:
  `python -m compileall -q /proyecto/scripts`.
- Después de editar un JSON, valídalo con `python -m json.tool`.
- Documenta cada cambio importante en `docs/`.
- Trabajo con ramas: una por fase. No hagas commits ni push sin preguntarme.
