# Fase 3: FFmpeg dentro de Docker

## Objetivo
Construir mi primera imagen propia con FFmpeg y usarla para generar un vídeo
de prueba y convertirlo a formato vertical 9:16, sin instalar FFmpeg en mi Mac.

---

## Conceptos

### Qué es FFmpeg
FFmpeg es un programa de línea de comandos, libre y gratuito, para procesar
audio y vídeo: convertir formatos, cortar, redimensionar, mezclar audio,
añadir subtítulos, comprimir... Por dentro es un conjunto de librerías
(libavcodec para los códecs, libavformat para los formatos de archivo,
libavfilter para los filtros). Muchísimas herramientas de vídeo lo usan por
debajo. No tiene interfaz gráfica: se le dan órdenes escribiendo un comando
con sus opciones.

### Cómo funciona todo junto: Mac, Colima y contenedor

```
Terminal (zsh)  →  docker (cliente)  →  Docker daemon  →  Contenedor
 en mi Mac          en mi Mac           dentro de Colima    Ubuntu + FFmpeg
```

- **El cliente `docker`** que escribo en la Terminal es solo un mando a
  distancia. No ejecuta nada por sí mismo.
- **El daemon de Docker** es el servicio que de verdad crea y gestiona los
  contenedores. Vive dentro de la máquina virtual Linux que crea Colima.
- El cliente y el daemon se comunican por un **socket**, un archivo especial
  de comunicación (el de Colima está en `~/.colima/default/docker.sock`).
- **FFmpeg no está instalado en mi Mac.** Solo existe dentro de la imagen
  `shorts-ffmpeg`, y se ejecuta dentro de un contenedor.

### Cómo le llegan los parámetros a FFmpeg
Todo lo que escribo **después del nombre de la imagen** en `docker run` es la
orden que se ejecutará dentro del contenedor:

```
docker run --rm -v "$PWD/data:/data" shorts-ffmpeg ffmpeg -i entrada.mp4 ...
└────────── opciones de Docker ─────────┘ └imagen┘ └──── orden para dentro ───┘
```

Lo que pasa, paso a paso:

1. **Mi shell (zsh) procesa la línea primero.** Sustituye `$PWD` por la ruta
   real, quita las comillas y junta las líneas partidas con `\`.
2. El cliente `docker` envía la petición al daemon.
3. El daemon crea un contenedor a partir de la imagen `shorts-ffmpeg` y
   conecta mi carpeta `data` con `/data`.
4. Dentro del contenedor, Linux ejecuta `ffmpeg` pasándole los argumentos
   como una lista. Docker no interpreta nada de esa parte: solo la transporta.
5. **FFmpeg es quien lee y entiende sus propios argumentos** (`-i`, `-vf`...).
6. FFmpeg lee y escribe en `/data`, que en realidad es la carpeta `data` de
   mi Mac. Por eso los vídeos aparecen en mi Mac aunque el trabajo se haga
   dentro del contenedor.
7. Al terminar FFmpeg, el contenedor se detiene y, por el `--rm`, se borra.

### Qué es el Dockerfile y cómo me ayuda
El Dockerfile es la **receta** para construir una imagen. Me ayuda por tres
motivos:

- **Reproducible**: cualquiera (o yo en otro ordenador, o dentro de un año)
  puede ejecutar `docker build` y obtener el mismo entorno.
- **Versionable**: es un archivo de texto, así que va a Git. La imagen no va
  a Git, pero su receta sí.
- **Limpio**: no ensucio mi Mac instalando programas. Si algo sale mal, borro
  la imagen y la reconstruyo.

### Qué lenguaje usa un Dockerfile
No es un lenguaje de programación. Es un formato propio, **declarativo**,
con unas pocas instrucciones en mayúsculas que se ejecutan de arriba abajo.
Las líneas que empiezan por `#` son comentarios.

| Instrucción | Qué hace |
|-------------|----------|
| `FROM` | Imagen de partida (aquí `ubuntu:24.04`) |
| `RUN` | Ejecuta un comando **al construir** la imagen |
| `WORKDIR` | Carpeta de trabajo por defecto dentro del contenedor |
| `CMD` | Comando por defecto **al arrancar** el contenedor |

Lo que va **dentro** de un `RUN` sí son comandos de shell de Linux
(`apt-get install ...`), porque se ejecutan dentro de Ubuntu.
`&&` encadena comandos (el siguiente solo se ejecuta si el anterior fue bien)
y `\` parte una línea larga en varias para que sea legible.

Cada `RUN` crea una **capa** de la imagen. Docker guarda las capas en caché,
así que si cambio algo al final del Dockerfile no tiene que repetir todo
desde el principio.

### `docker run --rm`
- `docker run` = crear un contenedor a partir de una imagen **y** arrancarlo.
- `--rm` = **borrar el contenedor automáticamente cuando termine**.

Sin `--rm`, cada ejecución dejaría un contenedor parado (se ve con
`docker ps -a`) y se irían acumulando. Con `--rm` no queda basura.
Ojo: borra el **contenedor**, no la imagen ni los archivos de la carpeta
conectada con `-v`. Mis vídeos se quedan en mi Mac.

### `$PWD` y `-v`
- `$PWD` es una variable de la shell que contiene la **ruta completa de la
  carpeta en la que estoy** (*Print Working Directory*, igual que el comando
  `pwd`). La shell la sustituye por la ruta real antes de ejecutar el comando.
  Si estoy en `/Users/yo/shorts-factory`, `$PWD/data` se convierte en
  `/Users/yo/shorts-factory/data`.
- Las comillas `"$PWD/data:/data"` evitan problemas si la ruta tuviera
  espacios.
- `-v origen:destino` conecta una carpeta de mi Mac (origen) con una carpeta
  dentro del contenedor (destino). Es un **bind mount**.

### `touch`
Comando de Linux que **crea un archivo vacío** si no existe (y si existe,
solo actualiza su fecha de modificación). Lo usé como prueba rápida para
comprobar que el contenedor podía escribir en mi carpeta `data`.

---

## Cómo se crea el vídeo

### Primer comando: generar un vídeo de prueba

```bash
docker run --rm -v "$PWD/data:/data" shorts-ffmpeg \
  ffmpeg -f lavfi -i testsrc=duration=5:size=1280x720:rate=30 \
         -f lavfi -i sine=frequency=440:duration=5 \
         -c:v libx264 -c:a aac -pix_fmt yuv420p \
         /data/entrada/prueba_horizontal.mp4
```

| Parte | Significado |
|-------|-------------|
| `-f lavfi` | La entrada no es un archivo, sino una fuente **virtual** generada por los filtros de FFmpeg |
| `-i testsrc=...` | Genera una imagen de test de 5 s, 1280x720, a 30 fotogramas por segundo |
| `-i sine=frequency=440...` | Genera un tono de audio de 440 Hz (la nota La) de 5 s |
| `-c:v libx264` | Codifica el vídeo con H.264, compatible con todas las plataformas |
| `-c:a aac` | Codifica el audio con AAC |
| `-pix_fmt yuv420p` | Formato de color que reproducen todos los móviles |
| `/data/entrada/...mp4` | Archivo de salida. La extensión `.mp4` decide el formato del contenedor de vídeo |

El **orden importa**: una opción colocada antes de un `-i` se aplica a esa
entrada (por eso `-f lavfi` va antes de cada `-i`). Lo que va al final, antes
del archivo de salida, se aplica a la salida.

### Segundo comando: pasar a vertical 9:16

```bash
docker run --rm -v "$PWD/data:/data" shorts-ffmpeg \
  ffmpeg -i /data/entrada/prueba_horizontal.mp4 \
         -vf "crop=ih*9/16:ih,scale=1080:1920" \
         -c:v libx264 -c:a aac -pix_fmt yuv420p \
         /data/salida/prueba_vertical.mp4
```

- `-i`: ahora la entrada es un archivo real.
- `-vf`: aplica una cadena de **filtros de vídeo**, separados por comas, que
  se ejecutan en orden:
  - `crop=ih*9/16:ih`: recorta el centro. Mantiene toda la altura (`ih` =
    *input height*) y calcula el ancho para que la proporción sea 9:16.
    Con 720 de alto, el ancho es 405.
  - `scale=1080:1920`: escala el resultado a la resolución estándar de un short.
- Las comillas son necesarias para que mi shell no interprete el `*` ni
  las comas, y se lo pase intacto a FFmpeg.

### ¿Por qué lo hicimos en dos pasos? ¿No se podía hacer directo?
**No es necesario hacerlo en dos pasos.** Solo lo hicimos así para
**simular un caso real**: normalmente tendré un vídeo horizontal ya hecho
(un gameplay o un vídeo descargado) y querré convertirlo. El primer comando
solo fabricó ese vídeo de origen de mentira.

Para generar un vídeo vertical directamente, bastaba con cambiar
`size=1280x720` por `size=1080x1920` en el primer comando.

En un flujo real, además, **conviene hacerlo todo en una sola pasada**:
FFmpeg permite encadenar muchos filtros en un mismo comando (recortar,
escalar, añadir subtítulos, mezclar audio...). Cada vez que un vídeo se
vuelve a codificar pierde un poco de calidad, así que cuantas menos
pasadas, mejor.

### ¿Qué lenguaje se usa para pedirle cosas a FFmpeg?
**Ninguno en sentido estricto.** Es la **línea de comandos de FFmpeg**:
el nombre del programa seguido de **opciones** (`-i`, `-c:v`, `-vf`...) y
sus valores. Lo interpreta el propio FFmpeg al arrancar.

Lo único parecido a un mini-lenguaje es la sintaxis de los filtros dentro
de `-vf` (`crop=...,scale=...`), que FFmpeg llama *filtergraph*.

Más adelante, un script de Python ejecutará estos mismos comandos de forma
automática. No cambiará el comando: solo quién lo escribe.

---

## Comandos usados

| Comando | Para qué sirve |
|---------|----------------|
| `docker build -t shorts-ffmpeg .` | Construye la imagen con la receta del Dockerfile |
| `docker images` | Lista las imágenes que tengo |
| `docker run --rm ...` | Crea y arranca un contenedor y lo borra al terminar |
| `-v "$PWD/data:/data"` | Conecta mi carpeta `data` con `/data` del contenedor |
| `touch` | Crea un archivo vacío |
| `ffmpeg -version` | Muestra la versión de FFmpeg |
| `ffmpeg -i` | Indica el archivo de entrada |
| `-vf "crop=...,scale=..."` | Aplica filtros de vídeo (recortar y escalar) |
| `open archivo.mp4` | Abre el archivo con la aplicación por defecto del Mac |

## Problemas y soluciones
[Anota aquí lo que te falló, aunque sea pequeño: ¿pudo el contenedor escribir
en la carpeta `data` a la primera? ¿Algún error al construir la imagen o al
copiar comandos?]

## Qué he aprendido
- Un contenedor es efímero; lo que quiero conservar vive en una carpeta de
  mi Mac conectada con `-v`.
- El Dockerfile es la receta reproducible de mi entorno y va a Git.
- Docker solo transporta la orden: es FFmpeg quien interpreta sus argumentos.
- Conviene encadenar filtros en una sola pasada para no perder calidad.
- [Añade aquí lo que tú sientas que has aprendido]

## Preguntas abiertas
- [Anota dudas que te queden]
- Un recorte central pierde mucha imagen en un gameplay real. Más adelante:
  vídeo completo en el centro con fondo desenfocado.
