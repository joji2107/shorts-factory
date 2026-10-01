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
- [ ] Fase 4: Voz (grabación en GarageBand, medición y procesado con FFmpeg)
- [ ] Fase 5: Subtítulos automáticos con Whisper
- [ ] Fase 6: Montaje del short (voz, imagen, música y subtítulos)
- [ ] Fase 7: Scripts en Python que automaticen el pipeline
- [ ] Fase 8: Servidor MCP y Claude Code
- [ ] Producción: publicar al menos 3 shorts por semana

## Estructura del proyecto

```
shorts-factory/
├── Dockerfile        # Receta de la imagen con FFmpeg
├── README.md
├── .gitignore
├── docs/             # Bitácora de cada fase
└── data/             # NO se sube a Git (vídeos y audios)
    ├── entrada/      # Material de origen
    └── salida/       # Resultados
```

La carpeta `data/` no existe al clonar el repositorio. Hay que crearla:

```bash
mkdir -p data/entrada data/salida
```

## Uso básico

Con Colima arrancado, construir la imagen y comprobar FFmpeg:

```bash
colima start
docker build -t shorts-ffmpeg .
docker run --rm shorts-ffmpeg ffmpeg -version
```

Ejecutar un comando de FFmpeg sobre la carpeta `data`:

```bash
docker run --rm -v "$PWD/data:/data" shorts-ffmpeg ffmpeg -i /data/entrada/archivo.mp4 ...
```

## Documentación

| Fase | Documento |
|------|-----------|
| 1 | `docs/01-git-y-github.md` |
| 2 | `docs/02-docker.md` |
| 3 | `docs/03-ffmpeg.md` |
| 4 | `docs/04-voz.md` |

## Entorno

- MacBook Pro con chip Apple M2 y 8 GB de RAM
- macOS Sonoma
- Colima (máquina virtual ligera) en lugar de Docker Desktop
