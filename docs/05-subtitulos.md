# Fase 5: Subtítulos automáticos con Whisper

> Estado: transcripción terminada. Los subtítulos dinámicos (pocas palabras
> por pantalla, grabados en el vídeo) quedan para la siguiente sesión.

## Objetivo
Transcribir mi voz con tiempos por palabra, dentro de Docker y con solo 8 GB
de RAM, para generar los subtítulos del short.

---

## Conceptos

- **Whisper**: modelo de voz a texto que da la transcripción con marcas de
  tiempo, en muchos idiomas.
- **faster-whisper**: reimplementación más rápida y ligera, que usa el motor
  CTranslate2 y funciona bien en CPU. En Docker sobre Mac no hay GPU, así que
  esto me conviene.
- **Cuantización `int8`**: guardar los números del modelo con menos precisión
  (enteros pequeños). Ocupa mucha menos RAM con poca pérdida de calidad.
- **Tamaños de modelo**: `tiny`, `base`, `small` (~244 M parámetros) y
  `medium` (~769 M). Más grande = más preciso, más lento y más RAM.
- **Entorno virtual (`venv`)**: Ubuntu 24.04 no deja instalar paquetes de
  Python en el sistema para no romper sus herramientas. La solución estándar
  es crear un entorno aislado (`/opt/venv`) e instalar ahí.
- **Formato SRT**: texto con bloques numerados, tiempo de inicio y fin, y la
  frase. Los tiempos van como `00:01:05,500`.

---

## Una segunda imagen basada en la primera

`Dockerfile.whisper` parte de mi imagen `shorts-ffmpeg` (Ubuntu + FFmpeg) y
le añade Python y faster-whisper. Así la primera imagen no se toca:

```dockerfile
FROM shorts-ffmpeg

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir faster-whisper "av==18.1.0"

ENV PATH="/opt/venv/bin:$PATH"
ENV HF_HOME=/data/modelos

WORKDIR /data
CMD ["bash"]
```

- `FROM shorts-ffmpeg`: parte de una imagen local mía, no de Docker Hub.
- `ENV`: define una variable de entorno que existe siempre en el contenedor.
- `HF_HOME=/data/modelos`: los modelos se descargan en mi carpeta `data`, que
  persiste. Sin esto, cada `--rm` los borraría y se bajarían cada vez.
- `"av==18.1.0"`: fija la versión exacta de `av`. Ver el problema 1.

Se construye con `-f` porque el archivo ya no se llama `Dockerfile`:

```bash
docker build -f Dockerfile.whisper -t shorts-whisper .
```

---

## El script `scripts/transcribir.py`

Mi primer script de Python. Vive en el repositorio y se **monta** en el
contenedor (`-v "$PWD/scripts:/scripts"`) en vez de copiarlo a la imagen, así
puedo editarlo sin reconstruir nada.

Uso: `python transcribir.py <audio> [modelo] [idioma]`

| Parte del script | Qué hace |
|------------------|----------|
| `sys.argv` | Lista de lo que escribo tras el nombre del script. El modelo e idioma tienen valor por defecto (`small`, `es`) |
| `compute_type="int8"` | La cuantización |
| `cpu_threads=2` | Coincide con los 2 núcleos de la VM de Colima |
| `word_timestamps=True` | Pide el tiempo de **cada palabra**, no solo de cada frase |
| `vad_filter=True` | Detecta dónde hay voz y salta los silencios, para que no se invente texto en las pausas |
| `formato_srt()` | Convierte segundos (65,5) a `00:01:05,500` con `divmod` |
| `resource.getrusage(...)` | Mide la RAM pico del proceso |
| `if __name__ == "__main__":` | Ejecuta `main()` solo si lanzo el archivo directamente |

Genera dos archivos junto al audio: un `.srt` (subtítulos por frases) y un
`.json` (cada palabra con su inicio y fin).

### Cómo se ejecuta
```bash
time docker run --rm -t \
  -v "$PWD/data:/data" \
  -v "$PWD/scripts:/scripts" \
  shorts-whisper \
  python /scripts/transcribir.py /data/salida/voz_v2_nr14.wav medium es
```
- `time` mide cuánto tarda.
- `-t` da una terminal al contenedor; sin ella no se ve la barra de progreso
  de la descarga del modelo.

---

## Comparación de modelos (mismo audio, 42,6 s)

| | `small` | `medium` |
|---|---------|----------|
| Tiempo total | 10,2 s | 30,3 s |
| RAM pico del proceso | 690 MB | 1.716 MB |
| Segmentos / palabras | 15 / 107 | 18 / 108 |
| Errores de texto frente al guion | 3 | 0 |

Los tres errores de `small`, comparados con el guion:

| Guion | `small` | `medium` |
|-------|---------|----------|
| prefiere | prefiero | prefiere |
| nadar le | nadarle | nadar le |
| te ha sorprendido | te has sorprendido | te ha sorprendido |

El resto de diferencias del `diff` eran cosméticas: tiempos desplazados unas
décimas de segundo y frases cortadas de otra manera.

**Qué dije yo realmente en esas tres frases:** [completa: ¿"prefiere" o
"prefiero"? ¿"nadar le" o "nadarle"? ¿"ha" o "has"? Si leí lo del guion, el
error fue de `small`.]

### Decisión
- **`medium`** para las versiones finales que voy a publicar.
- **`small`** para pruebas rápidas.

Razón: la RAM de `medium` solo se usa durante unos 30 segundos y se libera
después, y cupo en los 3 GB de Colima. Un error en un subtítulo lo ve
cualquiera que mire el short.

---

## Comandos usados

| Comando | Para qué sirve |
|---------|----------------|
| `docker build -f ... -t ...` | Construye una imagen con un Dockerfile que no se llama `Dockerfile` |
| `docker run -t` | Da terminal al contenedor (para ver barras de progreso) |
| `time` | Mide cuánto tarda un comando |
| `bash -c '...'` | Ejecuta una cadena de comandos; `&&` encadena si el anterior fue bien |
| `pip show` | Muestra versión y datos de un paquete de Python |
| `cat` / `head -n 20` / `tail -n 8` | Ver un archivo / sus primeras líneas / sus últimas |
| `cp origen destino` | Copiar un archivo |
| `diff a b` | Muestra solo las líneas distintas entre dos archivos (`<` del primero, `>` del segundo) |
| `du -sh carpeta` | Tamaño total de una carpeta |

---

## Problemas y soluciones

### 1. `TypeError: open() got an unexpected keyword argument 'metadata_errors'`
- **Síntoma:** la transcripción fallaba justo al abrir el audio.
- **Cómo se lee un error de Python:** de abajo hacia arriba. La última línea
  es el error; las de arriba son el camino hasta él.
- **Primera hipótesis (incorrecta):** pensé que `av` era demasiado antiguo.
  `pip install --upgrade av` dijo que ya tenía la 19.0.0, la más nueva.
- **Causa real:** PyAV 19.0.0 (publicada el 29 de septiembre de 2026)
  eliminó el argumento `metadata_errors`, y faster-whisper 1.2.1, su última
  versión, todavía lo pasa. Mi imagen se construyó dos días después, y como
  no fijé versiones, `pip` instaló la más nueva.
- **Solución:** fijar `av==18.1.0` en el Dockerfile.
- **Aprendizaje:** las dependencias sin versión fijada pueden romperse de un
  día para otro. Comprobar con `pip show` antes de arreglar a ciegas.
- **Pendiente:** cuando faster-whisper publique una versión compatible con
  PyAV 19, se podrá quitar el límite.

### 2. La descarga de `medium` parecía colgada
- **Síntoma:** pulsé `Ctrl + C` tras unos 4 minutos sin ver progreso.
- **Causa:** sin `-t`, Docker no dibuja la barra de descarga. El modelo
  pesa del orden de un gigabyte y medio.
- **Solución:** relanzar con `-t` y vigilar con `du -sh data/modelos`.
- **Aprendizaje:** el aviso `HF_TOKEN` es solo informativo; no hace falta
  token. Y si un día se usa, nunca va en el Dockerfile ni en Git.

### 3. [Anota aquí cualquier otro problema que tuvieras]

---

## Qué he aprendido
- Leer un traceback de abajo hacia arriba.
- Que fijar versiones es parte de la reproducibilidad.
- Que más RAM no siempre compensa, pero aquí `medium` sí: cero errores por
  20 segundos más y RAM que se libera al terminar.
- Que `diff` ayuda a separar el ruido de las diferencias que importan.
- [Añade aquí lo que tú sientas que has aprendido]

## Pendiente
- Subtítulos dinámicos: convertir el `.json` (palabra a palabra) en bloques de
  pocas palabras y grabarlos en el vídeo con FFmpeg.
- Si se añade intro o música antes de la voz, hay que desplazar los tiempos
  de los subtítulos esa misma cantidad.
- Revisar el `.srt` antes de publicar, aunque se use `medium`.
- Revisar si faster-whisper ya soporta PyAV 19.
