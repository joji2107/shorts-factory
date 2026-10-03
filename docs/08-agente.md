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
| `evaluar_material` | (parte 4) Dice si hay clips suficientes para un short y cuántos faltan |

El servidor no fabrica shorts: deja el audio en la bandeja y el vigilante hace
el resto. Pasar un vídeo de `revision/` a `listos/` lo decido siempre yo.

---

## Parte 3: búsqueda de clips con `buscar_clips`

### Uso
Se lo pido a Claude en lenguaje normal ("busca 4 clips de caballos") y Claude
llama a la herramienta:

```
buscar_clips(tema="caballo", busqueda_en_ingles="horse", cantidad=4, etiquetas_generales="animal")
```

- `tema`: la etiqueta con la que el vigilante encontrará los clips (minúsculas sin tildes).
- `busqueda_en_ingles`: lo que se busca en la API (los resultados son mejores en inglés).
- `cantidad`: de 1 a 5.
- `etiquetas_generales`: una o dos categorías más amplias, separadas por punto y coma (ver parte 4).

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
   `archivo,video,Pixabay,autor,url,Pixabay Content License,AAAA-MM-DD,tema;generales`.

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

## Parte 4: cuántos clips necesita un short

### El problema
Hasta ahora el vigilante usaba **todos** los clips del tema, sin saber si
llegaban. Con una biblioteca pequeña se repetían planos; con una grande, todos
los shorts del tema se parecerían, porque siempre salían los mismos clips en el
mismo orden y empezando en el segundo 0.

### Cuánto material hace falta (y por qué no basta 1,6 veces)
La idea de partida era pedir al menos 6 clips y 1,6 veces la duración del short.
Al revisar `cortes.py` y simular su reparto con las duraciones reales salió que
**se gasta más material del que parece**, por dos motivos:

- **El margen**: entre dos usos de un clip se saltan 0,5 s para no repetir
  plano. Con cortes de 1,5 s eso es un 33 % más.
- **El final de cada clip se pierde**: un clip solo se usa si le cabe el corte
  entero. De un clip de 7 s sale un corte de 4 s (+0,5 s de margen) y los
  2,5 s que quedan no sirven para el siguiente.

Material necesario para un short de 45 s, en el peor caso (cortes de 1,5 a 4 s):

| Clips de | 6-8 s | 10 s | 12-15 s | 20 s |
|---|---|---|---|---|
| Hace falta | ~2,0 veces | 1,74 veces | ~1,6 veces | 1,74 veces |

Como depende tanto de lo que dure cada clip, en vez de una proporción fija se
**simula el reparto real** (`repartir()` de `cortes.py`) con tres maneras de
cortar el short: todo con cortes mínimos (`corte_min`), medios y máximos
(`corte_max`). Con la transcripción de 001-pulpo salieron cortes de 1,6 a
3,9 s (media 2,7 s), así que hay que contar con los dos extremos.

| Estado | Condición |
|---|---|
| Suficiente | Al menos 6 clips distintos y llega sin repetir planos en los tres casos |
| Justo | Menos de 6 clips, o solo falla con cortes mínimos |
| Insuficiente | Falla también con cortes medios o máximos |

Regla rápida para explicarlo: unas **2 veces** la duración del short.

### `evaluar_material(tema, duracion_segundos=45)`
Nueva herramienta MCP. Da los clips del tema con su duración y cuántas veces se
han usado (en cuántos shorts y en cuántos cortes, mirando los `cortes.txt` de
`shorts/` y los `cortes_auto.txt` de `data/shorts/`), si llega en cada caso, el
estado y, si falta material, cuántos clips más hacen falta (simula añadir clips
de la duración mediana del tema). Con la biblioteca actual:

- `pulpo`: 5 clips, 69,5 s (1,51 veces un short de 46 s). Llega en los tres
  casos, pero es **justo** por tener menos de 6 clips: falta 1.
- `caballo`: 4 clips, 45,9 s (1,00 veces). **Insuficiente**: faltan 2 clips.

Regla en `CLAUDE.md`: antes de preparar un short, usar `evaluar_material` y
descargar solo los clips que falten.

### Selección de clips en el vigilante
La lógica común está en `scripts/material.py`, que usan el vigilante y el
servidor (por eso tampoco tiene `print()`). Si la receta no dice qué clips
usar, el vigilante:

1. Calcula la duración del short con `ffprobe` sobre el audio más la cola
   (sale algo más larga, porque aún no se ha recortado el silencio del
   principio: el margen va a favor).
2. Ordena los clips del tema de menos a más usados, al azar entre empatados.
3. Coge los mínimos que den *suficiente* (nunca menos de 6). Si ni con todos
   llega, usa todos y lo anota en el registro con un `AVISO`.
4. Escribe la lista en la receta: al rehacer el short se usan los mismos clips.

Prueba con un tema simulado de 12 clips: para 46 s elige 6, distintos en cada
intento y dejando fuera los ya usados; para 90 s elige 10.

### Cada clip empieza en un punto al azar
`cortes.py` (versión 4) separa el reparto (`repartir()`, que ya no imprime y se
puede simular desde el servidor) de la escritura. Después, `desplazar()` suma a
todos los cortes de un clip el mismo desfase al azar, entre 0 y lo que le sobra
al final. El reparto y el material necesario no cambian, pero el primer plano
de un clip ya no se repite en todos los shorts que lo usan.

Comprobaciones:
- Antes de añadir el desfase, `md5` idéntico de `cortes_auto.txt` antes y
  después de separar `repartir()` (la refactorización no cambia nada).
- Con 20 semillas: ningún corte se pasa del final de su clip y `pulpo_01`
  empieza en 19 puntos distintos. El desfase se redondea **hacia abajo** a
  fotogramas enteros, para no pasarse del final por medio fotograma.

### Etiquetas generales
`buscar_clips` sustituye `otras_etiquetas` por `etiquetas_generales`: una o dos
categorías más amplias que el tema, en singular y sin tildes (caballo →
`animal`). Si el tema ya existe y no se indican, reutiliza las que comparten
todos sus clips; si es nuevo, son obligatorias. El código comprueba las tildes
y el número, pero no el singular (no se puede saber de forma fiable: "mar" o
"pais" no son plurales), eso lo pide la descripción de la herramienta.

Cambios en el índice (con permiso):
- Pulpos: todos con `pulpo;animal;mar` (antes había dos órdenes distintos).
- Caballos: además de `animal`, una descriptiva según su imagen: `caballo_01`
  `noche` (silueta con la luna), `caballo_02` `nieve`, `caballo_03` `granja`
  (establo) y `caballo_04` `campo`.

---

## Problemas y soluciones

| Síntoma | Causa | Solución | Prevención |
|---------|-------|----------|------------|
| No se puede conseguir clave de Pexels | Pexels ha pausado la emisión de claves de su API | Usar la API de Pixabay | Una función por fuente: cambiar de fuente no obliga a rehacer la herramienta |
| La clave podría salir en un mensaje de error | Pixabay la pide dentro de la URL y las excepciones de `urllib` guardan la URL | Mensajes solo con el código de error, lanzados fuera del `except` | Probar los errores con una clave falsa y buscarla en el texto |
| `buscar_clips` no aparecía en Claude Code | El servidor se había arrancado antes de añadir la herramienta y sin `--env-file` | Volver a registrarlo y reiniciar Claude Code | Reiniciar tras cambiar el código o el registro del servidor |
| Un script de prueba no aparecía dentro del contenedor | Colima solo comparte la carpeta de usuario, no `/private/tmp` | Pasar el script por la entrada estándar (`docker run -i ... python - < script.py`) | |
| Con 1,6 veces la duración del short se repetían planos | Cada corte gasta 0,5 s de margen y se pierde el final de cada clip | Simular el reparto real con cortes mínimos, medios y máximos | Comprobar los números de partida con una simulación |
| El servidor no podía usar `asignar_clips` | Imprimía avisos con `print()`, que rompe la comunicación MCP | Separar `repartir()`, que devuelve los avisos | `md5` para comprobar que la refactorización no cambia el resultado |
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
- Aviso: `musica/relajada_02.mp3` dura 47,9 s (medido con `ffprobe`), menos de
  los 50 s recomendados. Solo sirve para shorts de unos 45 s como mucho.
- [Añade aquí otros pendientes]
