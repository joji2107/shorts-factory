---
name: registrar-metricas
description: Registra las métricas de un short publicado (visualizaciones, porcentaje que se quedó a verlo, duración media, likes, comentarios, compartidos, seguidores) a las 48 h o a los 7 días, a partir de números escritos o de capturas de pantalla de YouTube, Instagram, TikTok o X, y avisa de los datos que faltan. También anota las publicaciones nuevas y hace el análisis comparando por técnica, tema y duración. Úsala cuando el usuario pase cifras o capturas de un short, diga que ha publicado uno o pida un análisis de cómo funcionan los shorts.
argument-hint: "[NNN-tema plataforma 48h|7d | análisis]"
---

# Publicaciones y métricas

Petición: $ARGUMENTS

Todo en español. Explica al usuario qué vas a hacer antes de hacerlo (está aprendiendo).
No hagas commits sin preguntar.

Los datos viven en dos archivos de `shorts/` (van a Git) y se escriben **siempre** con el
script, nunca a mano: valida cada cifra, rellena los datos de la ficha y mantiene el orden.
- `publicaciones.csv`: short, plataforma, fecha y hora, archivo publicado y su md5.
- `metricas.csv`: una línea por short, plataforma y momento (`48h` o `7d`). Celda vacía =
  "no lo sé"; 0 = "ninguno". Nunca escribas 0 para un dato que no se sabe.

## Situación actual (se inyecta al cargar la skill)

!`docker run --rm -v "$PWD:/proyecto" -w /proyecto/scripts shorts-whisper python registrar_metricas.py pendientes 2>&1 || echo "(No se ha podido calcular: ¿está Colima en marcha?)"`

Últimas medidas registradas:
!`tail -n 5 shorts/metricas.csv 2>/dev/null || echo "(todavía ninguna)"`

## Comandos

Todos en Docker (`R` es una abreviatura para leer, no existe):

```bash
R="docker run --rm -v $PWD:/proyecto -w /proyecto/scripts shorts-whisper python registrar_metricas.py"
$R publicacion 007-tema youtube "2026-10-05 18:00"           # --archivo si hay varios en listos/
$R medida 001-pulpo youtube 48h --medido "2026-10-05 14:10" \
   --visualizaciones 1200 --se-quedaron 71.5 --duracion-media 29 \
   --likes 40 --comentarios 3 --compartidos 2 --seguidores 1
$R medida 001-pulpo youtube 48h --compartidos 5 --reemplazar  # corrige o completa: lo demás se conserva
$R pendientes
```

Pon solo las cifras que se sepan. `--se-quedaron` solo existe en YouTube. `--medido` es
cuándo se miraron las cifras (la hora de la captura si se ve; si no, pregunta o usa ahora).

## 1. Registrar una medida

1. **Qué short, plataforma y momento.** Si el usuario no lo dice, dedúcelo de la captura
   (título, plataforma) y de la fecha: el momento es el más cercano a 48 h o a 7 días desde
   la publicación (mira la situación de arriba). Si hay duda, pregunta.
2. **Leer las cifras.** Si es una captura, ábrela con Read. Equivalencias:

   | Columna | YouTube Studio | Instagram | TikTok | X |
   |---|---|---|---|---|
   | `visualizaciones` | Visualizaciones | Visualizaciones (antes Reproducciones) | Visualizaciones de vídeo | Visualizaciones de vídeo o Reproducciones |
   | `se_quedaron_pct` | Se quedaron a verlo (frente a «Deslizaron para pasar») | — | — | — |
   | `duracion_media_s` | Duración media de las visualizaciones | Tiempo medio de visualización | Tiempo medio de visualización | Tiempo medio de reproducción (si sale) |
   | `likes` | Me gusta | Me gusta | Me gusta | Me gusta |
   | `comentarios` | Comentarios | Comentarios | Comentarios | Respuestas |
   | `compartidos` | Compartidos | Veces compartido | Compartidos | Reposts |
   | `seguidores` | Suscriptores ganados | Seguidores | Nuevos seguidores | Seguimientos |

   **No confundir**: el «tiempo de visualización» total (en horas) no es la duración media;
   el «porcentaje medio visto» de YouTube no es «se quedaron a verlo»; las impresiones no
   son visualizaciones. Si la captura no dice claramente qué es una cifra, no la uses:
   pregúntala.

   Conversiones: «1,2 mil» o «1.2K» → 1200; «1,5 M» → 1500000; «0:31» → 31; «1:05» → 65;
   «71,5 %» → 71.5. Si la plataforma redondea («1,2 mil»), anótalo en `--notas`
   ("visualizaciones redondeadas por la plataforma").
3. **Confirmar antes de escribir.** Enseña una tabla con lo que has leído (columna, cifra,
   de dónde sale) y **espera el visto bueno**: una captura se puede leer mal.
4. **Escribir** con `medida`. Si da error, explica qué pasa (no está publicado, ya hay una
   medida y hay que usar `--reemplazar`, un porcentaje fuera de rango...).
5. **Avisar**: lo que dice «Faltan:» (pregunta si el usuario los tiene: «¿Tienes los
   compartidos? Suelen estar en...»), los AVISO del script (cifras raras, medida tarde) y
   qué medidas siguen pendientes (`pendientes`).

## 2. Anotar una publicación

«He publicado 007 en YouTube y TikTok»: una línea por plataforma con `publicacion`. Pide la
hora si no la da (vale aproximada, anótalo con `--notas "hora aproximada"`). El script
toma el vídeo de `data/listos/` y su md5; si hay varios del mismo short, pregunta cuál fue y
pásalo con `--archivo`. Después di cuándo tocan sus medidas de 48 h y de 7 días.

## 3. Análisis

```bash
docker run --rm -v "$PWD:/proyecto" -w /proyecto/scripts shorts-whisper python analizar_metricas.py [--momento 7d|48h] [--plataforma youtube]
```

Compara por técnica de interacción, tema y duración, cada plataforma por separado, con
medianas, % visto y las interacciones por cada 1000 visualizaciones. Al explicarlo:

- **Repite siempre los avisos de pocos datos** del script y respétalos: con grupos marcados
  con `*` (menos de 3 shorts) o menos de 10 shorts en una plataforma, habla de pistas,
  nunca de conclusiones ("la técnica X va mejor" no; "de momento, los dos shorts con X
  tienen más compartidos, pero son dos").
- Recuerda lo que va mezclado: cada short cambia a la vez de tema, técnica, música y día;
  los primeros se publicaron con menos seguidores.
- Termina con qué haría falta para saber más (cuántos shorts más, o repetir una técnica con
  temas distintos).
