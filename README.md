# Shorts Factory

Pipeline en Docker que convierte una grabación de voz en un vídeo corto
(YouTube Shorts / Reels / TikTok) con imagen de apoyo, música, efectos y
subtítulos automáticos. Suelto un audio en una carpeta y el short se hace solo.

Proyecto de aprendizaje de un estudiante de ASIX: contenedores, Linux,
FFmpeg, Python, Git, agentes de IA y documentación técnica.

## Estado

- [x] Fase 1: Git y GitHub
- [x] Fase 2: Docker con Colima
- [x] Fase 3: FFmpeg dentro de un contenedor
- [x] Fase 4: Voz (grabación en GarageBand, medición y procesado con FFmpeg)
- [x] Fase 5: Subtítulos con Whisper (transcripción y subtítulos dinámicos)
- [x] Fase 6: Montaje del short (clips, voz, música, efectos y subtítulos)
- [x] Fase 7: Automatización con Python (pipeline completo y carpeta bandeja)
- [ ] Fase 8: Servidor MCP y Claude Code
- [ ] Fase 9: Estrategia de contenido y canales
- [ ] Producción: publicar al menos 3 shorts por semana

Shorts terminados: 1 (`shorts/001-pulpo`).

## Uso diario

1. Arrancar Colima: `colima start`
2. Arrancar el vigilante:

```bash
docker run --rm -t -v "$PWD:/proyecto" -e HF_HOME=/proyecto/data/modelos \
  shorts-whisper python /proyecto/scripts/vigilar_bandeja.py
```

3. Grabar la voz y soltarla en `data/bandeja/` con el nombre `NNN-tema.wav`
   (por ejemplo `002-caballo.wav`). El tema debe existir como etiqueta de
   vídeos en `biblioteca/indice.csv`.
4. Revisar el resultado en `data/revision/` y, si está bien, moverlo a `data/listos/`.

Rehacer un paso de un short concreto:

```bash
docker run --rm -t -v "$PWD:/proyecto" -e HF_HOME=/proyecto/data/modelos \
  shorts-whisper python /proyecto/scripts/crear_short.py 002-caballo --rehacer subtitulos
```

Pasos: `voz`, `transcripcion`, `subtitulos`, `fondo`, `render`.

## Estructura del proyecto

```
shorts-factory/
├── Dockerfile            # Imagen shorts-ffmpeg (Ubuntu + FFmpeg + fuentes)
├── Dockerfile.whisper    # Imagen shorts-whisper (anterior + Python + faster-whisper)
├── config/
│   ├── por_defecto.json  # Valores comunes a todos los shorts
│   └── plantillas/       # Plantillas para los shorts nuevos
├── scripts/
│   ├── crear_short.py    # Crea un short paso a paso
│   ├── vigilar_bandeja.py
│   └── pasos/            # Un módulo por paso
├── shorts/               # Receta de cada short (configuración y cortes)
├── biblioteca/           # Índice de licencias del material (indice.csv)
├── docs/                 # Bitácora de cada fase
└── data/                 # NO se sube a Git
    ├── bandeja/          # Audios nuevos (dispara el proceso)
    ├── archivo/          # Audios ya procesados
    ├── revision/         # Shorts terminados, pendientes de revisar
    ├── listos/           # Shorts aprobados para publicar
    ├── errores/          # Audios que fallaron, con su .log
    ├── shorts/           # Archivos de trabajo de cada short
    ├── biblioteca/       # Vídeos, música, efectos y licencias
    ├── modelos/          # Modelos de Whisper
    └── registro.log      # Registro del vigilante
```

Al clonar el repositorio, `data/` no existe. Las carpetas de la bandeja las
crea el vigilante; las de la biblioteca hay que crearlas:

```bash
mkdir -p data/biblioteca/video data/biblioteca/musica data/biblioteca/sfx data/biblioteca/licencias
```

Y construir las imágenes:

```bash
docker build -t shorts-ffmpeg .
docker build -f Dockerfile.whisper -t shorts-whisper .
```

## Documentación

| Fase | Documento |
|------|-----------|
| 1 | `docs/01-git-y-github.md` |
| 2 | `docs/02-docker.md` |
| 3 | `docs/03-ffmpeg.md` |
| 4 | `docs/04-voz.md` |
| 5 | `docs/05-subtitulos.md` |
| 6 | `docs/06-montaje.md` |
| 7 | `docs/07-automatizacion.md` |

## Entorno

- MacBook Pro con chip Apple M2 y 8 GB de RAM
- macOS Sonoma
- Colima (máquina virtual ligera, 2 CPU y 3 GB) en lugar de Docker Desktop
