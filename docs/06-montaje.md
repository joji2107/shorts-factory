# Fase 6: Montaje del short

> Estado: primer short terminado (`data/salida/pulpo_v4.mp4`).
> Recetas guardadas en `shorts/001-pulpo/`.

## Objetivo
Juntar en un solo short vertical mis clips de vídeo, mi voz procesada,
música de fondo, efectos de sonido y los subtítulos dinámicos, todo con
FFmpeg dentro de Docker.

```
clips (con licencia) ─ normalizar ─ cortes de 3 s ─ unir ─ subtítulos ─┐
voz procesada ─────────────────────────────────────────────────────────┤
música ─ volumen ─ fundidos ─ ducking (controlado por la voz) ─────────├─ short final
whoosh ─ volumen ─ retrasos (3 apariciones) ───────────────────────────┘
```

---

## 1. Biblioteca de medios

### Estructura
```
data/biblioteca/          # Archivos (NO van a Git: pesan mucho)
├── video/                # pulpo_01.mp4, pulpo_02.mp4...
├── musica/               # curiosidad_01.mp3...
├── sfx/                  # whoosh_01.mp3...
└── licencias/            # Certificados descargados
biblioteca/indice.csv     # Índice de licencias (SÍ va a Git)
```
Los archivos y su índice están separados a propósito: los medios pesan y
se quedan en local; la información de licencias pesa poco y es lo que me
protege ante una reclamación, así que se versiona.

### El índice `biblioteca/indice.csv`
```
archivo,tipo,fuente,autor,url,licencia,fecha,etiquetas
```
- **licencia**: el nombre de la licencia (`Pexels License`,
  `Pixabay Content License`), no "Free". "Free" dice el precio, no las
  condiciones.
- **url**: la página del clip, no la del archivo descargado.
- **fecha**: el día de la descarga (`AAAA-MM-DD`). Las licencias pueden
  cambiar; cuenta la que había ese día.
- **etiquetas**: separadas por `;` para no confundirlas con columnas.

### Fuentes
| Fuente | Para qué | Notas |
|--------|----------|-------|
| Pexels | Vídeo | Uso comercial gratuito. Buscar en inglés |
| Pixabay | Vídeo, música, efectos | Uso comercial sin atribución obligatoria |
| Pixabay Music | Música | Descartar pistas con "Content ID Registered" |
| Biblioteca de audio de YouTube | Música | Revisar condiciones si publico fuera de YouTube |
| Wikimedia Commons | Casos especiales | Evitar CC BY-SA |

Aviso sobre música: "gratis" no significa "sin reclamaciones de Content ID".
Guardar siempre la licencia de cada pista para poder disputar.

Reglas para todo el material: sin personas reconocibles, logos ni marcas.

### Nombres de archivo
En minúsculas, sin espacios ni tildes: `pulpo_01.mp4`, `curiosidad_01.mp3`,
`whoosh_01.mp3`. Los espacios complican cualquier comando y script. La
música lleva un nombre según su uso (curiosidad), porque se reutiliza
en muchos shorts.

---

## 2. Inspeccionar el material

```bash
for f in data/biblioteca/video/*.mp4; do
  echo "$f"
  docker run --rm -v "$PWD/data:/data" shorts-ffmpeg \
    ffprobe -v error -select_streams v:0 \
      -show_entries stream=width,height,r_frame_rate:format=duration \
      -of csv=p=0 "/$f"
done
```
- `*.mp4`: comodín; la shell lo cambia por la lista de archivos.
- `"/$f"`: convierte la ruta del Mac (`data/...`) en la del contenedor
  (`/data/...`).
- Para audio: `-select_streams a:0` y `stream=sample_rate,channels`.

| Clip | Resolución | fps | Duración |
|------|-----------|-----|----------|
| pulpo_01 | 2160x3840 (vertical) | 25 | 17,3 s |
| pulpo_02 | 1920x1080 | 29,97 | 23,0 s |
| pulpo_03 | 1920x1080 | 59,94 | 9,1 s |
| pulpo_04 | 1920x1080 | 30 | 12,0 s |
| pulpo_05 | 1920x1080 | 59,94 | 8,0 s |

Problema: velocidades y orientaciones distintas. Para unir clips, tienen
que ser idénticos, así que antes hay que **normalizarlos**.

---

## 3. Encuadre: relleno frente a fondo desenfocado

**Relleno** (llena la pantalla, recorta el centro, amplía casi el doble):
```
scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1
```

**Fondo desenfocado** (plano completo en el centro sobre una copia
ampliada y desenfocada). **Es el que elegí:**
```
split[a][b];
[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:2[fondo];
[b]scale=1080:-2[frente];
[fondo][frente]overlay=(W-w)/2:(H-h)/2,fps=30,setsar=1
```
- `split`: duplica la imagen en dos caminos.
- `force_original_aspect_ratio=increase`: escala manteniendo la forma
  hasta **cubrir** el tamaño pedido.
- `scale=1080:-2`: ancho 1080 y altura automática en número par.
- `overlay=(W-w)/2:(H-h)/2`: pone una imagen sobre otra, centrada.
- `fps=30` y `setsar=1`: misma velocidad y píxeles cuadrados en todos.
- Los dos filtros sirven igual para clips verticales y horizontales.

---

## 4. Cortes rápidos con una lista (EDL)

Para dar dinamismo: 16 cortes de 3 s, alternando clips y usando
distintos momentos de cada uno, así nunca se repite el mismo plano.

La lista de cortes (`cortes.txt`) es una **EDL** (*Edit Decision List*):
cada línea es un clip y el segundo en que empieza. Cambiar el montaje es
editar este archivo, no los comandos.

```
pulpo_01 0
pulpo_02 0
...
```

```bash
rm -f data/trabajo/lista_cortes.txt
i=0
while read -r clip inicio; do
  i=$((i+1))
  nombre=$(printf "corte_%02d.mp4" $i)
  echo "$nombre: $clip desde el segundo $inicio"
  docker run --rm -v "$PWD/data:/data" shorts-ffmpeg \
    ffmpeg -hide_banner -loglevel error -y \
      -ss $inicio -i /data/biblioteca/video/${clip}.mp4 -t 3 \
      -vf "[FILTRO DEL FONDO DESENFOCADO]" \
      -an -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
      /data/trabajo/$nombre < /dev/null
  echo "file '$nombre'" >> data/trabajo/lista_cortes.txt
done < data/trabajo/cortes.txt
```
- `while read -r clip inicio`: lee el archivo línea a línea y separa
  las dos columnas en dos variables.
- `i=$((i+1))`: contador. `printf "corte_%02d.mp4"` da `corte_01.mp4`...
- `< /dev/null`: sin esto, `docker` se "come" el resto de la lista y el
  bucle termina tras el primer corte.
- `-an`: quita el audio de los clips. `-crf 18`: calidad alta en los
  archivos intermedios, porque se recodifican después.
- `>` sobrescribe un archivo; `>>` añade al final.

---

## 5. Unir los cortes sin recodificar

```bash
docker run --rm -v "$PWD/data:/data" shorts-ffmpeg \
  ffmpeg -hide_banner -loglevel error -y \
    -f concat -safe 0 -i /data/trabajo/lista_cortes.txt \
    -c copy /data/trabajo/fondo_cortes.mp4
```
- `-f concat`: la entrada es una lista de archivos para encadenar.
- `-c copy`: copia sin recodificar (instantáneo y sin perder calidad).
  Solo funciona porque todos los cortes son idénticos en formato.

---

## 6. Mezcla final

El grafo de filtros está en un archivo (`mezcla.txt`) porque es demasiado
largo para el comando:

```
[0:v]ass=/data/salida/voz_v2_nr14.ass[video];
[1:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[voz][voz_sc];
[2:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.25,afade=t=in:d=1,afade=t=out:st=42:d=1.6[musica];
[musica][voz_sc]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[musica_duck];
[3:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.25,asplit=2[w1a][w1b];
[4:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.25[w2a];
[w1a]adelay=11250:all=1[s1];
[w2a]adelay=22700:all=1[s2];
[w1b]adelay=35250:all=1[s3];
[voz][musica_duck][s1][s2][s3]amix=inputs=5:duration=longest:normalize=0,loudnorm=I=-14:TP=-2:LRA=11[audio]
```

| Pieza | Qué hace |
|-------|----------|
| `[1:a]`, `[2:a]`... | Audio de la entrada 1, 2... (la 0 es el vídeo) |
| `[voz]`, `[musica]`... | Etiquetas que pongo yo para conectar pasos, como cablear una mesa de mezclas |
| `aformat=...stereo` | Todo a estéreo y 48 kHz antes de mezclar |
| `asplit` | Duplica una señal (la voz va a la mezcla y al control del ducking) |
| `volume=0.25` | Música y efectos a un 25 % de amplitud (unos -12 dB) |
| `afade` | Entrada de 1 s y salida de 1,6 s de la música |
| `sidechaincompress` | **Ducking**: la voz controla un compresor que baja la música solo cuando hablo |
| `adelay=11250:all=1` | Retrasa un efecto 11.250 ms en todos los canales |
| `amix=...:normalize=0` | Suma las señales sin bajar cada entrada |
| `loudnorm=...:TP=-2` | Volumen final a -14 LUFS con pico máximo de -2 dBTP |

### Colocación de los efectos
Solo 3 *whoosh*, en los cortes donde el guion cambia de bloque. Cada uno
empieza la mitad de su duración antes del corte, para que su centro
coincida con el cambio de plano:

| Corte | Frase siguiente | Efecto (duración) | Retraso |
|-------|-----------------|-------------------|---------|
| 12 s | "Pero aquí viene lo curioso" | whoosh_01 (1,49 s) | 11.250 ms |
| 24 s | "Y todavía hay más" | whoosh_02 (2,58 s) | 22.700 ms |
| 36 s | "Si te ha sorprendido, sígueme" | whoosh_01 (1,49 s) | 35.250 ms |

### Render
```bash
time docker run --rm -v "$PWD/data:/data" shorts-ffmpeg \
  ffmpeg -hide_banner -y \
    -i /data/trabajo/fondo_cortes.mp4 \
    -i /data/salida/voz_v2_nr14.wav \
    -ss 0 -t 44 -i /data/biblioteca/musica/curiosidad_01.mp3 \
    -i /data/biblioteca/sfx/whoosh_01.mp3 \
    -i /data/biblioteca/sfx/whoosh_02.mp3 \
    -filter_complex_script /data/trabajo/mezcla.txt \
    -map "[video]" -map "[audio]" \
    -t 43.6 \
    -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p \
    -c:a aac -b:a 192k -ar 48000 \
    /data/salida/pulpo_v4.mp4
```
- `-ss 0 -t 44` delante de la música: qué fragmento de la pista se usa.
- `-filter_complex_script`: lee el grafo desde un archivo.
- `-map "[video]" -map "[audio]"`: usa las salidas con nombre del grafo.
- `-t 43.6`: mi voz (42,6 s) más un segundo de cola musical.

### Medición del resultado
```bash
docker run --rm -v "$PWD/data:/data" shorts-ffmpeg \
  ffmpeg -hide_banner -i /data/salida/pulpo_v4.mp4 -vn \
    -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null - 2>&1 \
  | grep -E '"input_(i|tp|lra)"'
```
`-vn` ignora el vídeo y mide solo el audio.

---

## Resultados

| Versión | Cambios | Volumen | Pico | Rango | Render |
|---------|---------|---------|------|-------|--------|
| v1 | 5 clips de 9,5 s, relleno, sin música | | | | |
| v2 | 16 cortes de 3 s, desenfocado, sin música | | | | ~45 s |
| v3 | + música, ducking y 6 whoosh a 0,4 | -14,51 LUFS | -0,99 dBTP | 3,40 LU | 63 s |
| v4 | 3 whoosh a 0,25 y `TP=-2` | -15,05 LUFS | -1,63 dBTP | 2,70 LU | [ ] |

---

## Comandos usados

| Comando | Para qué sirve |
|---------|----------------|
| `mkdir -p a b c` | Crear varias carpetas de una vez |
| `mv origen destino` | Mover y renombrar archivos descargados |
| `ffprobe -select_streams v:0 / a:0` | Ver datos del vídeo o del audio |
| `for f in carpeta/*.mp4` | Recorrer todos los archivos de un tipo |
| `while read -r a b; do ... done < archivo` | Recorrer un archivo línea a línea |
| `$((i+1))` y `printf "%02d"` | Contador y número con dos cifras |
| `< /dev/null` | Dar una entrada vacía a un comando dentro de un bucle |
| `> archivo` / `>> archivo` | Sobrescribir / añadir al final |
| `-f concat -c copy` | Unir vídeos sin recodificar |
| `-map` | Elegir qué pistas de qué entradas van a la salida |
| `-filter_complex_script` | Grafo de filtros desde un archivo |
| `time` | Medir el tiempo (el valor antes de `total`) |

---

## Problemas y soluciones

### 1. No sabía dónde mirar el tiempo de `time`
- **Solución:** es el número antes de `total` en la última línea. Los de
  `user` y `system` son del cliente `docker` del Mac y salen casi a cero.
- **Dato útil:** renderizar un short tarda aproximadamente lo que dura.

### 2. Efectos demasiado altos y demasiado frecuentes
- **Síntoma:** 6 *whoosh* cada 6 segundos sonaban mecánicos y molestaban.
- **Solución:** bajar de 0,4 a 0,25 (unos 4 dB) y dejar solo 3, en los
  cambios de bloque del guion.
- **Aprendizaje:** un efecto debe subrayar algo de la historia, no
  sonar porque toca.

### 3. Pico por encima del límite tras la codificación
- **Síntoma:** `loudnorm` dejaba el pico en -1,5, pero el archivo final
  medía -0,99 dBTP.
- **Causa:** la codificación AAC cambia ligeramente la onda y crea picos
  algo más altos.
- **Solución:** pedir `TP=-2` en la normalización para dejarle margen.
  Resultado: -1,63 dBTP.

### 4. [Anota aquí cualquier otro problema]

---

## Qué he aprendido
- Normalizar el material antes de unirlo: mismo tamaño, velocidad y formato.
- Que los cortes rápidos dan dinamismo, y que reutilizar clips no se nota
  si cada corte usa un momento distinto.
- A escribir decisiones en archivos (EDL, grafo de mezcla) en vez de en
  los comandos, y a guardarlos en Git como receta del short.
- El ducking con sidechain en FFmpeg, igual que en una mesa de mezclas.
- Que la codificación final puede alterar las medidas, y por eso se mide
  el archivo terminado.
- [Añade aquí lo que tú sientas que has aprendido]

## Pendiente
- Ver el short en el **móvil** antes de publicar: subtítulos frente a los
  botones de la plataforma, y sonido en el altavoz.
- Descripción del vídeo con créditos (cortesía hacia los autores).
- Fase 7 (script de automatización):
  - Cortes en las pausas entre frases usando el `.json`, no cada 3 s fijos.
  - Calcular los retrasos de los efectos a partir de la lista de cortes.
  - `loudnorm` en dos pasadas para acertar exactamente los -14 LUFS.
  - Calcular la duración final a partir de la voz.
  - Carpeta "bandeja" que dispara todo el proceso.
