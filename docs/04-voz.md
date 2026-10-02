# Fase 4: Voz

## Objetivo
Grabar mi voz con GarageBand, medirla con datos objetivos y procesarla con
FFmpeg dentro de Docker hasta dejarla lista para un short: volumen
estandarizado, poco ruido y dinámica controlada. Primer audio de trabajo:
la lectura de un guion de prueba sobre los tres corazones del pulpo.

---

## Material y configuración

**Equipo:** micrófono de condensador Neewer NW-800 → entrada 1 de la
interfaz Behringer U-Phoria UMC202HD (con alimentación phantom +48V) →
MacBook Pro M2 → GarageBand.

**Orden de conexión:** ganancia al mínimo, micro conectado, y solo entonces
+48V (evita el pop al conectar un condensador con el phantom activo).

**Ajustes de GarageBand** (Ajustes → Avanzado y pista):
- Resolución de grabación de audio: 24 bits.
- **Auto Normalizar desactivado.** Por defecto GarageBand sube el volumen al
  exportar, y yo quiero medir el audio tal como lo grabé.
- Metrónomo y conteo previo desactivados.
- Control automático de nivel de la pista desactivado: la ganancia la
  controlo con el potenciómetro de la interfaz.
- Todos los efectos de la pista desactivados para grabar la voz limpia.
- Monitorización por software desactivada; me escucho con el Direct Monitor
  de la interfaz para evitar latencia.

**Exportación:** Compartir → Exportar canción al disco → WAVE, a
`data/entrada/voz_prueba.wav`. GarageBand exporta en **estéreo** aunque grabe
con un solo micro (la misma señal en los dos canales), y en mi caso a
**44,1 kHz / 24 bits**, así que convierto a mono y a 48 kHz después con FFmpeg.

---

## Conceptos

### dBFS, LUFS, dBTP y LRA
- **dBFS**: nivel de la señal digital. 0 dBFS es el máximo; por encima se
  satura (clipping) y no tiene arreglo.
- **LUFS**: volumen **percibido** medio de todo el archivo. No mide picos, mide
  cuánto "suena" de fuerte. Es la unidad que usan las plataformas.
- **dBTP (True Peak)**: el pico real más alto, incluidos los que aparecen al
  reconvertir el audio. Se deja por debajo de 0 (yo uso -1,5).
- **LRA**: cuánto varía el volumen entre las partes fuertes y las suaves.
- **-14 LUFS** es una referencia habitual para contenido online. No todas las
  plataformas la aplican igual, así que la uso como punto de partida.

### Relación señal/ruido
Diferencia, en dB, entre el nivel de mi voz y el del ruido de fondo. Al
normalizar subo voz y ruido **la misma cantidad**, así que cuanto mejor sea
esta relación en la grabación, menos se nota el ruido al final. Es mejor
arreglar el ruido al grabar que con filtros después.

### Qué hace cada filtro de la cadena
| Filtro | Qué hace |
|--------|----------|
| `highpass=f=80` | Corta por debajo de 80 Hz (retumbos, golpes de mesa) |
| `afftdn` | Reduce ruido de fondo. `nr` = cuántos dB intenta quitar; `nf` = nivel de ruido que le indico |
| `acompressor` | Reduce la diferencia entre lo fuerte y lo flojo |
| `loudnorm` | Ajusta el volumen final al objetivo (-14 LUFS, pico -1,5) |

**El orden importa:** primero se reduce el ruido y se comprime, y **al final**
se normaliza. Si normalizara antes, el compresor volvería a cambiar el volumen.

### Dos trucos de FFmpeg que aprendí
- `-ss` y `-t` colocados **antes de `-i`** son para la entrada: `-ss 5` empieza
  a leer en el segundo 5 y `-t 4` lee solo 4 segundos. No tocan el original.
- `-f null -` procesa el audio **sin guardar ningún archivo**: sirve para medir.

---

## Flujo de trabajo

### 1. Inspeccionar el archivo
```bash
docker run --rm -v "$PWD/data:/data" shorts-ffmpeg \
  ffprobe -hide_banner /data/entrada/voz_prueba.wav
```

### 2. Medir el ruido de fondo (4 s de silencio al principio)
```bash
docker run --rm -v "$PWD/data:/data" shorts-ffmpeg \
  ffmpeg -hide_banner -t 4 -i /data/entrada/voz_prueba.wav \
         -af volumedetect -f null -
```
**El ruido se lee en `mean_volume`, no en `max_volume`.** El máximo son
eventos puntuales (un clic, una respiración).

### 3. Medir el volumen de la voz (saltando el silencio)
```bash
docker run --rm -v "$PWD/data:/data" shorts-ffmpeg \
  ffmpeg -hide_banner -ss 5 -i /data/entrada/voz_prueba.wav \
         -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json \
         -f null -
```
Valores que me interesan: `input_i` (LUFS), `input_tp` (dBTP) e `input_lra`.

### 4. Procesar con varias intensidades de reducción de ruido
```bash
for NR in 6 10 14; do
  docker run --rm -v "$PWD/data:/data" shorts-ffmpeg \
    ffmpeg -hide_banner -loglevel error -y -ss 5 -i /data/entrada/voz_prueba.wav \
           -af "highpass=f=80,afftdn=nr=${NR}:nf=-66,acompressor=threshold=-24dB:ratio=3:attack=10:release=200,loudnorm=I=-14:TP=-1.5:LRA=11" \
           -ac 1 -ar 48000 -c:a pcm_s24le \
           /data/salida/voz_v2_nr${NR}.wav
done
```
- `for ... do ... done` repite el bloque; la shell sustituye `${NR}` por
  6, 10 y 14 antes de ejecutar.
- `-ac 1` pasa a mono y `-ar 48000` fuerza 48 kHz.
- `-c:a pcm_s24le` guarda en WAV de 24 bits sin pérdida.

### 5. Medir los resultados y escucharlos con auriculares
```bash
for NR in 6 10 14; do
  echo "nr=$NR"
  docker run --rm -v "$PWD/data:/data" shorts-ffmpeg \
    ffmpeg -hide_banner -i /data/salida/voz_v2_nr${NR}.wav \
           -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null - 2>&1 \
    | grep -E '"input_(i|tp|lra)"'
done
```
- `2>&1` junta la salida de errores (por donde FFmpeg escribe su
  información) con la salida normal.
- `|` (pipe) pasa la salida de un comando al siguiente y `grep -E` se queda
  solo con las líneas que coinciden con el patrón.

---

## Resultados

| Medida | Grabación 1 | Grabación 2 |
|--------|-------------|-------------|
| Volumen (`input_i`) | -33,34 LUFS | -23,06 LUFS |
| Pico (`input_tp`) | -13,29 dBTP | -4,30 dBTP |
| Rango (`input_lra`) | 4,30 LU | 3,90 LU |
| Ruido de sala (`mean_volume`) | -67,7 dB | -66,5 dB |
| Relación voz/ruido (aprox.) | ~34 dB | ~43 dB |
| Subida necesaria hasta -14 LUFS | ~19,3 dB | ~9,1 dB |
| Lo que predice `loudnorm` de una pasada | -14,94 LUFS | -15,05 LUFS |

La relación voz/ruido es una **estimación** (resta de `input_i` y
`mean_volume`, que no se miden exactamente igual), pero el orden de magnitud
sirve para comparar.

**Qué cambié entre la grabación 1 y la 2:** [completa: distancia al micro,
Colima parado, ganancia, energía de la lectura...]

**Versión elegida:** `voz_v2_nr14.wav` (la que mejor suena a mi oído).
Medidas del archivo final: `input_i` = [ ], `input_tp` = [ ], `input_lra` = [ ].

### Cadena final
```
highpass 80 Hz → afftdn (nr=14, nf=-66) → acompressor (-24 dB, 3:1,
10 ms / 200 ms) → loudnorm (-14 LUFS, -1,5 dBTP) → mono, 48 kHz, 24 bits
```

---

## Comandos usados

| Comando | Para qué sirve |
|---------|----------------|
| `ffprobe` | Muestra los datos técnicos de un archivo sin modificarlo |
| `volumedetect` | Mide `mean_volume` y `max_volume` |
| `loudnorm ... print_format=json` | Mide LUFS, pico y rango dinámico |
| `-ss` / `-t` (antes de `-i`) | Empezar en un segundo / leer solo unos segundos |
| `-f null -` | Procesar sin guardar archivo (para medir) |
| `-ac 1` / `-ar 48000` | Pasar a mono / forzar 48 kHz |
| `for ... do ... done` | Repetir un comando con valores distintos |
| `2>&1` y `\|` y `grep -E` | Juntar salidas, encadenar comandos y filtrar líneas |
| `mv` | Mover o renombrar un archivo |
| `echo "texto" >> archivo` | Añadir una línea al final de un archivo |

---

## Problemas y soluciones

### 1. La primera captura salía casi en silencio
- **Síntoma:** `mean_volume` de -71 dB y `max_volume` de -49,6 dB. Eso es
  nivel de ruido, no de voz.
- **Causa:** el volumen de entrada del micrófono en los ajustes de sonido
  del Mac estaba a la mitad.
- **Solución:** subirlo y volver a medir. Después, `max_volume` de -13,3 dB.
- **Aprendizaje:** medir con `volumedetect` antes de seguir me evitó
  procesar un audio que no tenía la voz.

### 2. Siseo que se nota más en el archivo procesado
- **Síntoma:** se oye siseo, y más aún tras procesar.
- **Causa:** mi voz estaba 19 dB por debajo del objetivo. Al normalizar, el
  ruido subía lo mismo que la voz. Además, la diferencia entre pico y volumen
  medio obligaba a `loudnorm` a limitar.
- **Solución:** mejorar la grabación (más cerca del micro, mejor nivel) y
  ajustar la cadena con la reducción de ruido adecuada. Pasé de unos
  34 dB a unos 43 dB de relación voz/ruido.
- **Aprendizaje:** el ruido se arregla sobre todo al grabar, no con filtros.

### 3. Confundí `max_volume` con el nivel de ruido
- **Síntoma:** pensé que -44,2 dB era un ruido muy alto.
- **Causa:** ese valor era el **pico**. El ruido se lee en `mean_volume`
  (-67,7 dB).
- **Aprendizaje:** antes de alarmarme, comprobar qué mide cada número.

### 4. [Anota aquí cualquier otro problema que tuvieras]

---

## Qué he aprendido
- Medir antes de procesar: sin números no sé si el problema es la grabación
  o la cadena.
- La diferencia entre dBFS (digital), LUFS (percibido) y dBTP (pico real).
- Que normalizar sube también el ruido, y que por eso importa la relación
  voz/ruido de partida.
- Que el orden de los filtros importa.
- [Añade aquí lo que tú sientas que has aprendido]

## Preguntas abiertas y próximos pasos
- `loudnorm` de una pasada es aproximado: probar las **dos pasadas** al
  automatizarlo con Python.
- Si aún hay siseo entre frases, probar una puerta de ruido (`agate`).
- Mejorar la acústica de la sala (reverberación) al grabar.
- Siguiente fase: subtítulos automáticos con Whisper.


---

## Revisión: ecualización y doble compresión

### El problema
Al ver el primer short en el móvil, la voz sonaba bien, pero le faltaba
algo para sonar profesional. [Describe aquí con tus palabras qué notabas.]

### Diagnóstico
- **El pitch quedó descartado**: cambiar el tono suele sonar artificial y
  no es lo que hacen los locutores.
- **Mi cadena no tenía ninguna ecualización.** Filtraba graves, reducía
  ruido, comprimía y normalizaba, pero no daba forma al timbre.
- **La interpretación** también cuenta (energía, ritmo, hablarle a una
  persona) y mejora con la práctica.

### Prueba A/B/C
- A: cadena anterior (`voz_v2_nr14.wav`).
- B: + ecualización (`voz_v3_eq.wav`).
- C: + ecualización y segunda compresión (`voz_v3_eq_comp.wav`). **Elegida.**

| Filtro | Qué hace | Por qué |
|--------|----------|---------|
| `bass=g=2:f=120` | +2 dB por debajo de 120 Hz | Calidez y cuerpo |
| `equalizer=f=300:t=q:w=1:g=-3` | -3 dB en torno a 300 Hz | Quita el sonido "de caja" |
| `equalizer=f=4000:t=q:w=1:g=3` | +3 dB en torno a 4 kHz | Presencia e inteligibilidad |
| `treble=g=2:f=10000` | +2 dB por encima de 10 kHz | Aire y brillo |
| 2.º `acompressor` (-16 dB, 4:1, 5 ms / 60 ms) | Compresión rápida | Densidad y cercanía |

### Cadena actual
```
highpass → afftdn → bass → equalizer 300 Hz → equalizer 4 kHz → treble
→ acompressor → acompressor → loudnorm
```
Guardada como receta en `shorts/001-pulpo/voz.txt`.

Como la voz nueva empieza en el mismo punto (`-ss 5`), los tiempos de los
subtítulos siguen valiendo y no hizo falta volver a transcribir.

### Pendiente
- Si las eses suenan ásperas por el realce de 4 kHz, añadir un de-esser.
- Ajustar los valores a mi voz con la experiencia de los próximos shorts.
