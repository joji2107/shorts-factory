# Shorts Factory

Pipeline en Docker para crear vídeos cortos (YouTube Shorts / Reels / TikTok)
con voz propia, imagen de apoyo, música y subtítulos automáticos, y un
agente de Claude conectado mediante MCP.

Proyecto de aprendizaje de un estudiante de ASIX: contenedores, Linux,
FFmpeg, scripting, agentes de IA y documentación técnica.

## Estado

- [x] Fase 1: Git y GitHub
- [x] Fase 2: Docker con Colima
- [x] Fase 3: FFmpeg dentro de un contenedor
- [x] Fase 4: Voz (grabación en GarageBand, medición y procesado con FFmpeg)
- [x] Fase 5: Subtítulos con Whisper (transcripción y subtítulos dinámicos)
- [x] Fase 6: Montaje del short (clips, voz, música, efectos y subtítulos)
- [ ] Fase 7: Scripts en Python que automaticen el pipeline
- [ ] Fase 8: Servidor MCP y Claude Code
- [ ] Producción: publicar al menos 3 shorts por semana

Shorts terminados: 1 (`shorts/001-pulpo`).

## Estructura del proyecto

```
shorts-factory/
├── Dockerfile          # Imagen shorts-ffmpeg (Ubuntu + FFmpeg + fuentes)
├── Dockerfile.whisper  # Imagen shorts-whisper (sobre la anterior + faster-whisper)
├── README.md
├── .gitignore
├── biblioteca/         # Índice de licencias del material (indice.csv)
├── shorts/             # Recetas de cada short (cortes y mezcla)
├── scripts/            # Scripts de Python
├── docs/               # Bitácora de cada fase
└── data/               # NO se sube a Git
    ├── entrada/        # Material de origen (voz grabada)
    ├── salida/         # Resultados
    ├── trabajo/        # Archivos intermedios (se pueden borrar)
    ├── modelos/        # Modelos de Whisper
    └── biblioteca/     # Vídeos, música, efectos y licencias descargadas
```

La carpeta `data/` no existe al clonar el repositorio. Hay que crearla:

```bash
mkdir -p data/entrada data/salida data/trabajo
mkdir -p data/biblioteca/video data/biblioteca/musica data/biblioteca/sfx data/biblioteca/licencias
```

## Uso básico

Con Colima arrancado, construir las imágenes:

```bash
colima start
docker build -t shorts-ffmpeg .
docker build -f Dockerfile.whisper -t shorts-whisper .
```

Transcribir un audio (`small` para pruebas, `medium` para versiones finales):

```bash
docker run --rm -t -v "$PWD/data:/data" -v "$PWD/scripts:/scripts" \
  shorts-whisper python /scripts/transcribir.py /data/salida/audio.wav medium es
```

Generar subtítulos dinámicos (.ass) a partir del .json de palabras:

```bash
docker run --rm -v "$PWD/data:/data" -v "$PWD/scripts:/scripts" \
  shorts-whisper python /scripts/generar_ass.py /data/salida/audio.json
```

El proceso completo de montaje está en `docs/06-montaje.md`.

## Documentación

| Fase | Documento |
|------|-----------|
| 1 | `docs/01-git-y-github.md` |
| 2 | `docs/02-docker.md` |
| 3 | `docs/03-ffmpeg.md` |
| 4 | `docs/04-voz.md` |
| 5 | `docs/05-subtitulos.md` |
| 6 | `docs/06-montaje.md` |

## Entorno

- MacBook Pro con chip Apple M2 y 8 GB de RAM
- macOS Sonoma
- Colima (máquina virtual ligera, 2 CPU y 3 GB) en lugar de Docker Desktop
