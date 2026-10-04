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
- [x] Fase 8: Servidor MCP y Claude Code (agente, clips de Pixabay y guiones)
- [ ] Fase 9: Estrategia de contenido y canales
- [ ] Producción: publicar al menos 3 shorts por semana

Shorts hechos: 2 (`shorts/001-pulpo` y `shorts/002-caballo`, este en revisión).

## Uso diario

```bash
./arrancar.sh    # Colima + vigilante (si no están en marcha) y estado: Colima, vigilante, bandeja, Git
./apagar.sh      # se niega si hay audios en la bandeja o un short procesándose; avisa de
                 # cambios sin guardar en Git; para el vigilante con SIGINT y apaga Colima
```

Los dos se pueden ejecutar varias veces: lo que ya está en marcha (o parado) no se toca.
Lo que hacen por dentro, por si hace falta a mano:

```bash
colima start
docker run -d --rm --name vigilante -v "$PWD:/proyecto" -e HF_HOME=/proyecto/data/modelos \
  shorts-whisper python /proyecto/scripts/vigilar_bandeja.py --plantilla curiosidades
docker logs -f vigilante                  # ver lo que hace (Ctrl+C solo deja de mirar)
docker kill --signal=SIGINT vigilante     # pararlo (también tras cambiar código, y volver a arrancarlo)
colima stop
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

## Flujo de trabajo

De encender el Mac a tener el short en revisión. Claude Code trabaja en modo
manual: pide permiso antes de cada comando y explica qué va a hacer.

1. **Abrir la terminal** en el proyecto: `cd ~/shorts-factory`.
2. **Arrancar el sistema**: `./arrancar.sh` (Colima y el vigilante en segundo plano).
   Al apagar el Mac se paran, así que hay que arrancarlo cada vez.
3. **Mirar el estado** que enseña al final: Colima y vigilante en marcha, audios
   en la bandeja, rama de Git y cambios sin guardar.
4. **Abrir Claude Code**: `claude`. Comprobar en la barra de estado que pone
   `⏸ manual mode on` (si no, `Shift+Tab` hasta verlo) y con `/mcp` que el
   servidor `fabrica` está conectado.
5. **Pedir el guion**: `/guion-short caballo`, o en lenguaje normal: "pásame un
   guion para un short sobre caballos, divertido y con algo de intriga".
   Claude busca y verifica los datos y me enseña el guion, las palabras, la
   duración estimada, la técnica de interacción y las fuentes.
6. **Revisar el guion**: abrir las fuentes y pedir cambios si hace falta ("más
   corto", "cambia el gancho", "otro dato"). Cuando esté bien: "está perfecto".
7. **Ficha y material**: Claude reserva `shorts/NNN-tema/`, elige música y
   efectos y comprueba con `evaluar_material` si hay clips suficientes. Si
   faltan, me pide permiso para descargarlos con `buscar_clips`.
8. **Grabar**: pedir "crea un documento con lo que tengo que leer y ábrelo"
   (hoja `para_leer.html`, letra grande, énfasis y pausas marcadas). Grabar en
   GarageBand y exportar como `NNN-tema.wav`, con el nombre exacto que dice Claude.
9. **Dejar la grabación** en `data/bandeja/`. También se puede dejar en
   `data/entrada/` con cualquier nombre y pedir "prepara el short con esta
   grabación" (`preparar_short` usa la receta reservada).
10. **Seguir el proceso**: `docker logs -f vigilante`, o pedir a Claude
    "muéstrame el proceso en tiempo real". Tarda unos 2-3 minutos.
11. **Revisar el vídeo** en `data/revision/NNN-tema.mp4`.
12. **Pedir correcciones** describiendo lo que se ve u oye: "el efecto de error
    no se oye", "baja un poco la música", "quiero que suene el error cuando digo
    vomitar", "el final queda en silencio". Claude mide la causa antes de tocar,
    la arregla en la receta y, si es un fallo general, en el código o en
    `config/por_defecto.json`, rehace el short (`crear_short.py --rehacer ...`),
    deja el vídeo nuevo en `data/revision/` y lo apunta en la documentación.
    Si cambia código, reinicia el vigilante.
13. **Aprobar**: mover el vídeo a mano de `data/revision/` a `data/listos/`.
14. **Guardar el trabajo**: pedir a Claude el commit y el push (siempre pregunta antes).
15. **Al terminar**: `./apagar.sh`.

## Estructura del proyecto

```
shorts-factory/
├── Dockerfile            # Imagen shorts-ffmpeg (Ubuntu + FFmpeg + fuentes)
├── Dockerfile.whisper    # Imagen shorts-whisper (anterior + Python + faster-whisper)
├── CLAUDE.md             # Contexto y reglas del proyecto para Claude Code
├── .claude/skills/       # Skill guion-short (guiones y ficha de cada short)
├── config/
│   ├── por_defecto.json  # Valores comunes a todos los shorts
│   ├── lectura.json      # Velocidad de lectura (se afina sola con cada short)
│   └── plantillas/       # Plantillas para los shorts nuevos
├── scripts/
│   ├── crear_short.py    # Crea un short paso a paso
│   ├── vigilar_bandeja.py
│   ├── servidor_mcp.py   # Herramientas de la fábrica para Claude Code
│   ├── material.py       # Clips de un tema: duración, usos y si alcanzan
│   ├── lectura.py        # Velocidad de lectura y estimación de duración
│   └── pasos/            # Un módulo por paso
├── shorts/               # Receta de cada short (guion, configuración y cortes)
├── biblioteca/           # Índice de licencias del material (indice.csv)
├── docs/                 # Bitácora de cada fase
└── data/                 # NO se sube a Git
    ├── entrada/          # Grabaciones para preparar_short (cualquier nombre)
    ├── bandeja/          # Audios nuevos (dispara el proceso)
    ├── archivo/          # Audios ya procesados
    ├── revision/         # Shorts terminados, pendientes de revisar
    ├── listos/           # Shorts aprobados para publicar
    ├── errores/          # Audios que fallaron, con su .log
    ├── shorts/           # Archivos de trabajo de cada short
    ├── biblioteca/       # Vídeos, música, efectos y licencias
    ├── modelos/          # Modelos de Whisper
    ├── cache/            # Búsquedas de Pixabay (24 horas)
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
| 8 | `docs/08-agente.md` |

## Entorno

- MacBook Pro con chip Apple M2 y 8 GB de RAM
- macOS Sonoma
- Colima (máquina virtual ligera, 2 CPU y 3 GB) en lugar de Docker Desktop
