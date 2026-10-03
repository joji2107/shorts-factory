# Fase 8: Servidor MCP y Claude Code

> Estado: en curso. [Completa con el estado cuando cierres la fase]

## Objetivo
Que Claude Code pueda manejar la fábrica con herramientas concretas y seguras
(ver el estado, preparar un short, consultar errores) y que pueda ampliar la
biblioteca buscando clips con licencia libre, sin que yo tenga que descargarlos
y registrarlos a mano.

## Parte 2: el servidor MCP
`scripts/servidor_mcp.py` se ejecuta dentro del contenedor `shorts-whisper` y
habla con Claude por la entrada y la salida estándar (*stdio*). Por eso nunca
se usa `print()`: cualquier texto suelto rompería la comunicación.

| Herramienta | Qué hace |
|-------------|----------|
| `estado_fabrica` | Qué hay en bandeja, revisión, listos, errores y `data/entrada/`, y las últimas líneas del registro |
| `temas_disponibles` | Etiquetas de vídeo del índice y cuántos clips tiene cada una |
| `listar_shorts` | Las recetas de `shorts/` y el estado de su vídeo |
| `preparar_short` | Copia una grabación de `data/entrada/` a la bandeja con el siguiente número libre |
| `ver_error` | El `.log` de un short que ha fallado |
| `buscar_clips` | (parte 3) Busca clips, los descarga a la biblioteca y los registra en el índice |

El servidor no fabrica shorts: deja el audio en la bandeja y el vigilante hace
el resto. Pasar un vídeo de `revision/` a `listos/` lo decido siempre yo.

---

## Parte 3: búsqueda de clips con `buscar_clips`

### Uso
Se lo pido a Claude en lenguaje normal ("busca 4 clips de caballos") y Claude
llama a la herramienta:

```
buscar_clips(tema="caballo", busqueda_en_ingles="horse", cantidad=4, otras_etiquetas="animal")
```

- `tema`: la etiqueta con la que el vigilante encontrará los clips (minúsculas sin tildes).
- `busqueda_en_ingles`: lo que se busca en la API (los resultados son mejores en inglés).
- `cantidad`: de 1 a 5.
- `otras_etiquetas`: opcional, separadas por punto y coma.

### Qué hace, paso a paso
1. Pide a la API de vídeos de Pixabay hasta 3 páginas de resultados (50 por página).
2. Descarta los vídeos de menos de 6 s y los que ya están en el índice (misma url).
3. Pone primero los verticales. Pixabay no filtra por orientación, y los
   horizontales también sirven porque el montaje los encuadra sobre un fondo desenfocado.
4. De cada vídeo elige la versión más pequeña cuyo lado corto sea de 1080 px
   o más (si no hay, la mayor). Así una versión 1080 gana a la 4K, que ocupa
   más y hace el render más lento.
5. Descarga cada clip como `data/biblioteca/video/<tema>_NN.mp4`, siguiendo la
   numeración que ya exista (mira a la vez la carpeta y el índice).
6. Añade su línea a `biblioteca/indice.csv` con las 8 columnas:
   `archivo,video,Pixabay,autor,url,Pixabay Content License,AAAA-MM-DD,tema;otras`.

Detalles de seguridad:
- La descarga se hace a un archivo `.part` que se renombra al terminar: nunca
  queda un `.mp4` a medias ni se sobrescribe un archivo de la biblioteca.
- Cada línea se añade al índice justo después de su descarga: si algo falla a
  mitad, lo ya descargado queda registrado.
- En la biblioteca solo se **añaden** archivos, y solo mediante esta
  herramienta: los existentes nunca se modifican ni se borran (regla de `CLAUDE.md`).

### Una función por fuente
La idea inicial era usar Pexels, pero Pexels ha pausado la emisión de claves de
su API. Para no rehacer la herramienta cada vez que cambie la fuente, cada una
es una función que devuelve los vídeos en un formato común (`url`, `autor`,
`duracion`, `versiones`). Elegir versión, descargar, numerar y registrar es
igual para todas. La tabla `FUENTES` dice qué variable de entorno, nombre y
licencia usa cada una. Para volver a usar Pexels bastará con escribir
`_buscar_pexels()` y añadirla a `FUENTES`.

### Primera prueba real: 4 clips de caballos

| Archivo | Tamaño | Resolución | Duración | fps |
|---|---|---|---|---|
| `caballo_01.mp4` | 2,2 MB | 1080x1920 | 7,0 s | 30 |
| `caballo_02.mp4` | 8,9 MB | 1080x1920 | 15,5 s | 30 |
| `caballo_03.mp4` | 4,3 MB | 1080x1920 | 10,0 s | 23,976 |
| `caballo_04.mp4` | 18 MB | 1080x1920 | 13,4 s | 50 |

Los cuatro son verticales a 1080x1920, las 4 líneas del índice tienen sus 8
columnas y `temas_disponibles` ya muestra `caballo: 4`. El más pesado es el de
50 fps; el render lo pasa a 30 de todas formas.

---

## La clave de la API

### Dónde está y por qué no va a Git
La clave está en el archivo `.env` de la raíz del proyecto:

```
PIXABAY_API_KEY=la_clave_sin_comillas_ni_espacios
```

- La clave es personal: identifica mi cuenta, y quien la tenga puede hacer
  peticiones en mi nombre y gastar mi límite. Si me la bloquean por mal uso,
  me la bloquean a mí.
- Lo que se sube a GitHub queda en el historial para siempre: aunque luego se
  borre el archivo, la clave se puede recuperar de commits anteriores. Además
  hay programas que rastrean GitHub buscando claves publicadas.
- Por eso `.env` está en `.gitignore` desde el primer commit del proyecto y el
  código **no** lleva la clave escrita: solo lee la variable de entorno. Para comprobarlo:

```bash
git check-ignore -v .env                # .gitignore:12:.env   .env
git log --all --oneline -- .env         # vacío: nunca ha estado en Git
```

### Cómo llega al servidor
El servidor corre dentro de Docker, así que la variable tiene que entrar en el
contenedor. Se hace con la opción `--env-file` de `docker run`, en el registro
del servidor en Claude Code:

```bash
claude mcp remove fabrica -s local
claude mcp add fabrica -s local -- docker run -i --rm \
  --env-file /Users/jordirubiobarros/shorts-factory/.env \
  -v /Users/jordirubiobarros/shorts-factory:/proyecto \
  shorts-whisper python /proyecto/scripts/servidor_mcp.py
```

- `--env-file` va antes del nombre de la imagen porque es una opción de
  `docker run`, no del programa que se ejecuta dentro.
- La ruta es completa para no depender de la carpeta desde la que se lance el servidor.
- Docker toma el valor literal: sin comillas ni espacios alrededor del `=`.
- Después de registrarlo hay que reiniciar Claude Code para que arranque el servidor nuevo.

### Cómo se protege dentro del código
- Si la variable no existe, o sigue con el valor de ejemplo `pega_aqui_tu_clave`,
  la herramienta lo dice claramente y no hace ninguna petición.
- En Pixabay la clave **viaja dentro de la URL** (`?key=...`), y las excepciones
  de `urllib` guardan la URL completa. Por eso los errores se describen solo
  por su código (400: clave no válida, 429: límite alcanzado) y se lanzan
  fuera del `except`, para que la excepción original no quede enganchada al
  error que llega a Claude.
- La caché se guarda con una huella (`sha256`) de los parámetros **sin la
  clave**, y la herramienta no escribe nada en `registro.log`.
- Comprobación hecha tras la prueba real: buscar la clave en `data/cache/`
  sin mostrarla (`grep -rqF`) no da ningún resultado.

---

## Condiciones de uso de las fuentes

### Pexels (fuente prevista; ahora sin claves nuevas)
Consultado en la documentación de la API (pexels.com/api/documentation) y la
licencia (pexels.com/license):

- **Licencia**: uso gratuito, se puede modificar y usar en redes sociales. La
  atribución **no es obligatoria** (*"Attribution is not required"*).
- **Guías de la API**: piden mostrar *"a prominent link to Pexels"* cuando se
  hacen peticiones y *"Always credit our photographers when possible"*
  (por ejemplo, "Video by X on Pexels" con enlace al vídeo).
- **Prohibido**: mostrar a personas identificables de forma ofensiva, sugerir
  que respaldan algo, vender copias sin modificar, redistribuir en otra web de
  stock y usar el contenido como marca.
- **Condiciones generales**: prohibida la copia *"bulk, large-scale or
  systematic"* sin permiso.
- **Límite**: 200 peticiones por hora y 20 000 al mes.

### Pixabay (fuente actual)
Consultado en pixabay.com/api/docs y pixabay.com/service/license-summary:

- **Caché de 24 horas** obligatoria: cada respuesta se guarda en
  `data/cache/pixabay/<huella>.json` (`data/` no va a Git).
- **Indicar el origen** al mostrar resultados: la herramienta termina siempre
  con "Vídeos de Pixabay (https://pixabay.com)".
- **Nada de descargas masivas**: como máximo 5 clips por llamada.
- **No enlazar a sus archivos**: hay que descargarlos (es lo que hacemos).
- **Límite**: 100 peticiones por minuto.
- **Licencia**: no exige créditos, aunque se agradecen. No permite distribuir
  el clip tal cual, usar personas reconocibles de forma inmoral o engañosa, ni
  usar con fines comerciales marcas que aparezcan. Las búsquedas usan `safesearch=true`.

### Qué hacemos para cumplirlas
- En el índice queda el autor y la url de cada clip, con su licencia y la fecha.
- Los créditos en la descripción del short no son obligatorios en ninguna de
  las dos, pero se agradecen: pendiente ponerlos ("Vídeos: <autor> en Pixabay").

---

## Problemas y soluciones

| Síntoma | Causa | Solución | Prevención |
|---------|-------|----------|------------|
| No se puede conseguir clave de Pexels | Pexels ha pausado la emisión de claves de su API | Usar la API de Pixabay | Una función por fuente: cambiar de fuente no obliga a rehacer la herramienta |
| La clave podría salir en un mensaje de error | Pixabay la pide dentro de la URL y las excepciones de `urllib` guardan la URL | Mensajes solo con el código de error, lanzados fuera del `except` | Probar los errores con una clave falsa y buscarla en el texto |
| `buscar_clips` no aparecía en Claude Code | El servidor se había arrancado antes de añadir la herramienta y sin `--env-file` | Volver a registrarlo y reiniciar Claude Code | Reiniciar tras cambiar el código o el registro del servidor |
| Un script de prueba no aparecía dentro del contenedor | Colima solo comparte la carpeta de usuario, no `/private/tmp` | Pasar el script por la entrada estándar (`docker run -i ... python - < script.py`) | |
| [Añade aquí otros problemas] | | | |

## Herramientas aprendidas

| Herramienta | Para qué |
|-------------|----------|
| `urllib.request`, `urllib.parse.urlencode` | Peticiones HTTP solo con la biblioteca estándar |
| `hashlib.sha256` | Huella de un texto: nombre de archivo para la caché |
| `docker run --env-file` | Pasar variables de entorno (claves) desde un archivo |
| `claude mcp add` / `remove` / `get` | Registrar el servidor MCP en Claude Code y ver cómo está registrado |
| `git check-ignore -v` | Comprobar qué regla de `.gitignore` ignora un archivo |
| `grep -rqF` | Buscar un texto sin mostrarlo (solo dice si está) |
| `open -e` | Abrir un archivo con TextEdit desde la terminal |

## Mis conclusiones
- [Añade aquí qué te ha parecido dejar que Claude use la fábrica con herramientas]
- [Añade aquí qué has aprendido sobre guardar claves y secretos]
- [Añade aquí qué opinas de depender de una API externa (como el cierre de claves de Pexels)]
- [Añade aquí lo que tú sientas que has aprendido]

## Pendiente
- Poner los créditos ("Vídeos: <autor> en Pixabay") en la descripción de cada short.
- Añadir Pexels como segunda fuente cuando vuelva a dar claves.
- [Añade aquí otros pendientes]
