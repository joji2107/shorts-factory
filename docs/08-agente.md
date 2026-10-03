# Fase 8: Servidor MCP y Claude Code

> Estado: fase terminada. El short 002-caballo se hizo de principio a fin con
> Claude Code: guion con la skill, clips de Pixabay, grabación y vigilante.

## Objetivo
Trabajar con un agente de IA (Claude Code) sobre la fábrica: que entienda el
proyecto y sus reglas, que pueda manejarla con herramientas concretas y seguras
(ver el estado, preparar un short, consultar errores), que amplíe la biblioteca
con clips de licencia libre y que me ayude a escribir los guiones, sin que yo
pierda el control de lo que se hace.

| Parte | Qué se hizo | Commit |
|---|---|---|
| 1 | Claude Code y `CLAUDE.md` con la descripción y las reglas del proyecto | `aa665d4` |
| 2 | Servidor MCP con las herramientas de la fábrica | `a3ee82e` |
| 3 | `buscar_clips` con la API de Pixabay y la clave en `.env` | `11c999c` |
| 4 | `evaluar_material` y selección de clips por uso | `c1cc821` |
| 5 | Skill `guion-short`, receta reservada y estimación de duración | `288dc50` |
| 6 | Primer short con la skill (002-caballo) y arreglos de mezcla | `288dc50` |

Antes de empezar, en la misma rama, se reforzó el vigilante: no sobrescribe una
grabación ya archivada (la nueva se guarda con la fecha y la hora en el nombre) e
ignora los audios vacíos sin bloquear la bandeja (`b91850a`, documentado en
`docs/07-automatizacion.md`).

---

## Parte 1: Claude Code

### Instalación
Claude Code es un agente que trabaja en la terminal: lee el proyecto, ejecuta
comandos y edita archivos, siempre dentro de los permisos que le doy.

Lo instalé con Homebrew (paquete `claude-code`, versión 2.1.285):

```bash
brew install --cask claude-code
claude --version                 # 2.1.285 (Claude Code)
cd ~/shorts-factory && claude    # abre una sesión en el proyecto (la primera vez pide iniciar sesión)
```

- El paquete `claude-code` sigue el canal *estable*, que va aproximadamente una
  semana por detrás y se salta las versiones con fallos graves.
- Con Homebrew **no se actualiza solo**: hay que hacer `brew upgrade claude-code`
  de vez en cuando (y `brew cleanup` para borrar versiones viejas).
- `claude doctor` revisa la instalación y los ajustes sin abrir una sesión.

### Modos de permisos
El modo de permisos decide qué puede hacer Claude sin preguntarme
(documentación oficial: code.claude.com/docs/en/permission-modes):

| Modo | Qué hace sin preguntar | Para qué sirve |
|---|---|---|
| Manual (`default`) | Solo leer | Revisar cada acción yo mismo |
| `acceptEdits` | Leer, editar archivos y comandos sencillos de archivos (`mkdir`, `mv`, `cp`...) | Iterar sobre código que estoy revisando |
| `plan` | Leer (y comandos que aprueba el clasificador si el modo auto está disponible) | Explorar y proponer un plan antes de tocar nada |
| `auto` | Todo, con comprobaciones de seguridad en segundo plano | Tareas largas sin tantas preguntas |
| `dontAsk` | Leer y las herramientas aprobadas de antemano; el resto se rechaza | Scripts y CI |
| `bypassPermissions` | Todo | Solo contenedores o máquinas aisladas |

- Se cambia durante la sesión con **`Shift+Tab`**. La barra de estado lo indica:
  `⏸ manual mode on`, `⏵⏵ accept edits on`, `⏸ plan mode on`, `⏵⏵ auto mode on`...
- Desde la versión 2.1.283, **las sesiones empiezan en modo `auto`**. Para
  empezar siempre en manual, se puede fijar en `~/.claude/settings.json`:

```json
{
  "permissions": {
    "defaultMode": "default"
  }
}
```

### Por qué uso el modo manual
- Estoy aprendiendo: en `CLAUDE.md` le pido que me explique qué va a hacer y por
  qué antes de hacerlo, y en manual veo y apruebo cada comando que ejecuta.
- Hay cosas que no se deben hacer sin mí: borrar o modificar `data/archivo/`,
  `data/biblioteca/` o `data/modelos/`, hacer commits o push, o descargar
  material. En manual, cada una de esas acciones me pide permiso.
- Si algo sale mal, sé exactamente qué comando lo hizo.
- Para cambios grandes uso **`/plan`** al principio del mensaje: Claude investiga,
  propone un plan y no toca nada hasta que lo apruebo.
- [Añade aquí por qué prefieres el modo manual, con tus palabras]

### `CLAUDE.md`
Es un archivo en la raíz del proyecto que Claude Code lee al empezar cada sesión.
Contiene lo que necesita saber para trabajar en el proyecto sin que se lo repita:

- Qué es la fábrica, los comandos (todo en Docker) y cómo comprobar los cambios
  (`compileall`, `json.tool`, `md5`).
- La arquitectura: el flujo de la bandeja, la configuración por capas, los pasos
  con dependencias, la biblioteca, el material y el servidor MCP.
- Las reglas del proyecto: responder en español, explicar antes de actuar, no
  tocar ciertas carpetas, no subir `data/` ni `.env`, no hacer commits sin
  preguntar, y arreglar las correcciones de raíz.

Se ha ido actualizando en cada parte de la fase. Va a Git, así que cualquier
sesión nueva en el proyecto parte del estado actual.

---

## Parte 2: el servidor MCP
MCP (*Model Context Protocol*) permite darle a Claude herramientas propias.
`scripts/servidor_mcp.py` se ejecuta dentro del contenedor `shorts-whisper` y
habla con Claude por la entrada y la salida estándar (*stdio*). Por eso nunca
se usa `print()`: cualquier texto suelto rompería la comunicación. Las
herramientas devuelven su resultado con `return`.

| Herramienta | Qué hace |
|-------------|----------|
| `estado_fabrica` | Qué hay en bandeja, revisión, listos, errores y `data/entrada/`, y las últimas líneas del registro |
| `temas_disponibles` | Etiquetas de vídeo del índice y cuántos clips tiene cada una |
| `listar_shorts` | Las recetas de `shorts/` y el estado de su vídeo |
| `preparar_short` | Copia una grabación de `data/entrada/` a la bandeja: con el número de la receta reservada del tema, si la hay, o con el siguiente número libre |
| `ver_error` | El `.log` de un short que ha fallado |
| `buscar_clips` | (parte 3) Busca clips en Pixabay, los descarga a la biblioteca y los registra en el índice |
| `evaluar_material` | (parte 4) Dice si hay clips suficientes para un short y cuántos faltan |

### Por qué no crea shorts directamente
- **Un solo camino**: `preparar_short` deja el audio en la bandeja y el vigilante
  hace el resto, igual que si lo hubiera dejado yo. No hay una segunda forma de
  crear shorts que se pueda comportar distinto (archivado, registro, errores,
  limpieza...).
- **Render largo**: un short tarda unos 2-3 minutos. Es mejor que lo haga el
  vigilante en su contenedor que dejar a Claude esperando dentro de una llamada.
- **Lo que pasa queda registrado** en `data/registro.log`, venga de Claude o de mí.

### Por qué no hay herramientas para aprobar ni borrar
- **Aprobar** (pasar de `revision/` a `listos/`) es decidir qué se publica: lo
  decido yo después de ver el vídeo.
- **Borrar** no tiene vuelta atrás, y las carpetas importantes (`data/archivo/`,
  la biblioteca, los modelos) no se tocan nunca.
- Es el principio del **mínimo privilegio**: el agente solo tiene las
  herramientas que necesita. Lo que no está en la lista no lo puede hacer desde
  MCP. Y en modo manual, todo lo que haga en la terminal pasa antes por mí.

### Registrar el servidor y reiniciar tras cambiarlo

```bash
claude mcp add fabrica -s local -- docker run -i --rm \
  --env-file /Users/jordirubiobarros/shorts-factory/.env \
  -v /Users/jordirubiobarros/shorts-factory:/proyecto \
  shorts-whisper python /proyecto/scripts/servidor_mcp.py
claude mcp get fabrica        # ver cómo está registrado y si conecta
```

- Claude Code **arranca el servidor al abrir la sesión** (un contenedor nuevo)
  y le pregunta qué herramientas tiene. El código se carga en ese momento.
- Si cambio `servidor_mcp.py` (o algo que importe) o el registro, **hay que
  reiniciar Claude Code**. Si no, sigue usando el servidor de antes, sin las
  herramientas nuevas. `/mcp`, dentro de la sesión, muestra los servidores y su estado.
- La imagen `shorts-whisper` incluye la biblioteca `mcp` (en `Dockerfile.whisper`).

---

## Parte 3: búsqueda de clips con `buscar_clips`

### Por qué Pixabay y no Pexels
La idea inicial era usar la API de Pexels, pero Pexels ha pausado la emisión de
claves de su API. Se cambió a la API de vídeos de Pixabay, adaptando lo que ya
estaba hecho. Para no rehacer la herramienta cada vez que cambie la fuente, cada
una es una función que devuelve los vídeos en un formato común (`url`, `autor`,
`duracion`, `versiones`). Elegir versión, descargar, numerar y registrar es igual
para todas. La tabla `FUENTES` dice qué variable de entorno, nombre y licencia
usa cada una. Para volver a usar Pexels bastará con escribir `_buscar_pexels()`
y añadirla a `FUENTES`.

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

### La clave de la API

**Dónde está y por qué no va a Git.** La clave está en el archivo `.env` de la
raíz del proyecto:

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

**Cómo llega al servidor.** El servidor corre dentro de Docker, así que la
variable tiene que entrar en el contenedor. Se hace con la opción `--env-file` de
`docker run`, en el registro del servidor (parte 2):

- `--env-file` va antes del nombre de la imagen porque es una opción de
  `docker run`, no del programa que se ejecuta dentro.
- La ruta es completa para no depender de la carpeta desde la que se lance el servidor.
- Docker toma el valor literal: sin comillas ni espacios alrededor del `=`.

**El cuidado con la clave en la URL.** En Pixabay la clave **viaja dentro de la
URL** (`?key=...`), y las excepciones de `urllib` guardan la URL completa:

- Si la variable no existe, o sigue con el valor de ejemplo `pega_aqui_tu_clave`,
  la herramienta lo dice claramente y no hace ninguna petición.
- Los errores se describen solo por su código (400: clave no válida, 429: límite
  alcanzado) y se lanzan **fuera** del `except`, para que la excepción original
  (con la URL) no quede enganchada al error que llega a Claude.
- Nunca se muestra ni se registra una URL completa de la API. La herramienta no
  escribe en `registro.log`.
- La caché se guarda con una huella (`sha256`) de los parámetros **sin la clave**.
- Comprobación hecha tras la prueba real: buscar la clave en `data/cache/` sin
  mostrarla (`grep -rqF`) no da ningún resultado.

### Condiciones de uso

**Pixabay (fuente actual).** Consultado en pixabay.com/api/docs y
pixabay.com/service/license-summary:

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

**Pexels (fuente prevista; ahora sin claves nuevas).** Consultado en la
documentación de la API (pexels.com/api/documentation) y la licencia
(pexels.com/license):

- **Licencia**: uso gratuito, se puede modificar y usar en redes sociales. La
  atribución **no es obligatoria** (*"Attribution is not required"*).
- **Guías de la API**: piden mostrar *"a prominent link to Pexels"* cuando se
  hacen peticiones y *"Always credit our photographers when possible"*.
- **Prohibido**: mostrar a personas identificables de forma ofensiva, sugerir
  que respaldan algo, vender copias sin modificar, redistribuir en otra web de
  stock, usar el contenido como marca y la copia *"bulk, large-scale or systematic"*.
- **Límite**: 200 peticiones por hora y 20 000 al mes.

**Qué hacemos para cumplirlas.** En el índice queda el autor y la url de cada
clip, con su licencia y la fecha. Los créditos en la descripción del short no son
obligatorios en ninguna de las dos, pero se agradecen: pendiente ponerlos.

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
Da los clips del tema con su duración y cuántas veces se han usado (en cuántos
shorts y en cuántos cortes, mirando los `cortes.txt` de `shorts/` y los
`cortes_auto.txt` de `data/shorts/`), si llega en cada caso, el estado y, si
falta material, cuántos clips más hacen falta. Para eso añade clips imaginarios
de la duración mediana del tema hasta que la simulación llega.

Ejemplo con los 4 caballos y un short de 46 s: 30 cortes cortos, 17 medios o 12
largos; en cada clip caben ⌊(duración + 0,5) / (corte + 0,5)⌋ cortes. Con 4
clips caben 21, 13 y 9 (no llega); con 5, 27, 16 y 11 (no llega); con 6 clips de
11,7 s, 33, 19 y 13: suficiente, así que faltaban 2.

Regla en `CLAUDE.md`: antes de preparar un short, usar `evaluar_material` y
descargar con `buscar_clips` solo los clips que falten.

### Selección de clips en el vigilante
La lógica común está en `scripts/material.py`, que usan el vigilante y el
servidor (por eso tampoco tiene `print()`). Si la receta no dice qué clips
usar, el vigilante, con la duración real del short (parte 5):

1. Ordena los clips del tema de menos a más usados, al azar entre empatados.
2. Coge los mínimos que den *suficiente* (nunca menos de 6). Si ni con todos
   llega, usa todos y lo anota en el registro con un `AVISO`.
3. Escribe la lista en la receta: al rehacer el short se usan los mismos clips.

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
`buscar_clips` usa `etiquetas_generales`: una o dos categorías más amplias que
el tema, en singular y sin tildes (caballo → `animal`). Si el tema ya existe y no
se indican, reutiliza las que comparten todos sus clips; si es nuevo, son
obligatorias. El código comprueba las tildes y el número, pero no el singular
(no se puede saber de forma fiable: "mar" o "pais" no son plurales), eso lo pide
la descripción de la herramienta.

Cambios en el índice (con permiso): todos los pulpos con `pulpo;animal;mar`, y
los caballos con `animal` más una descriptiva según su imagen (`noche`, `nieve`,
`granja` y `campo`). También se registró la música y los efectos nuevos de la
biblioteca, corrigiendo erratas (parte de la tabla de problemas).

---

## Parte 5: la skill `guion-short` y la ficha del short

### Qué es una skill
Una skill es un conjunto de instrucciones que Claude Code carga cuando hacen falta.
Según la documentación oficial (code.claude.com/docs/en/skills):

- Las de proyecto van en `.claude/skills/<nombre>/SKILL.md` y se suben a Git.
- `SKILL.md` tiene una cabecera YAML (`name`, `description`...) y las instrucciones
  en Markdown. Claude decide usarla comparando lo que le pido con la `description`;
  también se puede llamar con `/guion-short caballo`.
- Conviene que `SKILL.md` no pase de 500 líneas: el material de consulta va en
  archivos aparte de la misma carpeta, que se leen solo cuando hacen falta.
- `` !`comando` `` inyecta datos al cargarla. Si el comando falla, la skill no se
  carga, por eso todos llevan `|| true`.
- Las skills se cargan al empezar la sesión: si se crea o se cambia una, hay que
  reiniciar Claude Code.

### Qué hace
`.claude/skills/guion-short/SKILL.md`, con `ejemplo-001-pulpo.md` como referencia de tono:

1. **Guion**: gancho (máximo 12 palabras), dato, giro y remate; 100-120 palabras;
   **énfasis** en negrita y `(pausa)` entre paréntesis; una técnica de interacción
   (pregunta de respuesta fácil, de opinión ligera, bucle, promesa del siguiente
   dato o reto inicial) distinta de la del short anterior; cada dato confirmado en
   dos fuentes fiables, sin mitos, con las fuentes al final. Me lo enseña y espera
   mi visto bueno.
2. **Ficha**: reserva el siguiente número y crea `shorts/NNN-tema/guion.md` (guion,
   técnica, palabras, duración estimada, música, efectos y fuentes) y `config.json`
   (solo lo que cambia: música y efectos). Música por estado de ánimo, distinta de
   la del short anterior y más larga que el short. Efectos:
   mín(3, redondeo(duración / 13,5)), ninguno en los primeros 8 s; los que tienen
   que sonar en una palabra concreta, anclados a ella (parte 6).
3. **Material**: `evaluar_material` con la duración estimada; si falta, me pide
   permiso para `buscar_clips`.
4. **Cierre**: me dice con qué nombre guardar la grabación (`NNN-tema.wav`) y
   dónde dejarla.

Al cargarse ve la velocidad de lectura, la técnica y la música de cada short, el
último número usado y la música y los efectos del índice.
`shorts/001-pulpo/guion.md` se creó a partir de la transcripción para que la
rotación de técnicas tenga historial.

### Receta reservada
Antes, una receta que ya existía se usaba tal cual, y `preparar_short` siempre cogía
el siguiente número. Con una receta creada antes de grabar habría dos problemas:
`preparar_short` le daría otro número, y el vigilante no aplicaría la plantilla
(se perdería, por ejemplo, `voz.inicio: "auto"`). Ahora:

- Una receta es **reservada** si tiene `guion.md` y su `config.json` no tiene
  `audio_original`.
- `preparar_short` usa la reservada del tema (si hay varias, pide cuál con `short`).
- El vigilante la pone **encima de la plantilla** al llegar la grabación.

### Estimación de duración y velocidad de lectura
La duración real la marca siempre la grabación (voz detectada + cola). Antes de
grabar solo se puede estimar:

**duración estimada = palabras / velocidad de lectura + cola**

- `config/lectura.json` guarda la velocidad y las muestras de cada short. Empezó
  en 2,54 palabras/s (108 palabras en 42,55 s del 001-pulpo). Con el 002-caballo
  (115 palabras en 41,6 s, 2,76 palabras/s) pasó a 2,65.
- Al terminar un short, el vigilante añade su muestra (palabras transcritas y
  segundos de `voz.wav`, pausas incluidas) y la velocidad pasa a ser la **mediana de
  las 5 últimas**: se adapta a cómo grabo ahora y una grabación rara no la desvía.
  Si repito un short, su muestra se sustituye en vez de duplicarse.
- La cola es `final.cola` de `config/por_defecto.json`: 1 s al principio de la
  fase y 2,5 s desde la parte 6.
- `crear()` acepta una función `despues_de_voz` que se llama con la duración real
  antes de transcribir. El vigilante la usa para elegir los clips con esa duración
  (antes se elegían con el audio sin recortar) o, si la receta ya los tiene,
  comprobarlos. Si no alcanzan, lo anota en el registro antes de renderizar.
- `efectos.inicio_min` (antes un 3 fijo en `cortes.py`) permite que la skill pida
  8 s sin efectos al principio. Con el valor por defecto (3) los efectos salen
  idénticos (`md5`).

Pruebas (en una copia temporal, sin renderizar): `preparar_short` usa la receta
reservada `002-caballo` aunque el siguiente número libre era el 3; el vigilante
recupera la plantilla y conserva la música y los efectos de la receta; `crear()`
llama a la función justo después de la voz (43,55 s con 001-pulpo).

---

## Parte 6: primer short con la skill (002-caballo) y arreglos de mezcla

El 002-caballo es el primer short hecho de principio a fin con la skill: guion con
reto inicial y dos datos verificados (duerme de pie pero sueña tumbado; casi no
puede vomitar), receta reservada, 2 clips descargados (`caballo_05` y
`caballo_06`) y una grabación de 115 palabras en 41,6 s.

Al revisarlo salieron tres fallos. La regla desde ahora: **cada corrección se
arregla en el código o en los valores por defecto, no solo en la receta**, y se
apunta aquí, en `CLAUDE.md` y en la skill.

| Lo que se notaba | Causa medida | Arreglo |
|---|---|---|
| La música acababa de golpe y el final quedaba mudo | El audio duraba 41,6 s y el vídeo 44,1 s: `sidechaincompress` (el *ducking*) termina con su entrada más corta, la voz, y se llevaba la música | `apad` alarga la voz con silencio hasta el final (`montaje.py`). Ahora audio y vídeo duran lo mismo y el fundido se oye entero |
| El efecto de error no se oía | Los efectos vienen con niveles muy distintos: `error_01` tiene el pico en -21 dB y `whoosh_01` en -0,1 dB, y a todos se les aplicaba el mismo 0,35 | Cada efecto se iguala a `efectos.pico` (-3 dB) antes de aplicar `efectos.volumen` (0,5). `error_01` sube 18 dB |
| Música algo alta | `musica.volumen` 0,35 | 0,25 por defecto |

También cambian por defecto el fundido de salida (de 1,6 a 3 s) y la cola (de 1 a
2,5 s), para que la música se apague con calma después de la última palabra.

### Efectos anclados a palabras
El efecto de error tenía que sonar al decir "vomitar". Con un segundo fijo
(`momento`) se descuadraría al volver a grabar, así que en `efectos.lista` un efecto
puede llevar `"palabra": "vomitar"` (y `"vez": 2` si la palabra se repite): empieza
justo al terminar esa palabra en la transcripción. Lo hace `anclar_a_palabras()` en
`crear_short.py`, y la skill ya lo propone para los efectos que dependen del texto.

### El vigilante y el código nuevo
El vigilante carga el código al arrancar. El primer render del 002 lo hizo uno
arrancado el día anterior, sin los cambios de la parte 5. **Después de cambiar
código hay que reiniciarlo.** Ahora corre en segundo plano:

```bash
docker run -d --rm --name vigilante -v "$PWD:/proyecto" -e HF_HOME=/proyecto/data/modelos \
  shorts-whisper python /proyecto/scripts/vigilar_bandeja.py --plantilla curiosidades
docker logs -f vigilante                       # ver lo que hace
docker kill --signal=SIGINT vigilante          # pararlo como con Ctrl+C
```

`docker stop` no sirve para pararlo limpio: envía SIGTERM, y Python como proceso
principal del contenedor no reacciona hasta que Docker lo mata a los 10 s.

---

## Problemas y soluciones

| Síntoma | Causa | Solución | Prevención |
|---------|-------|----------|------------|
| Una grabación archivada podía desaparecer y un audio vacío frenaba la bandeja | El vigilante movía encima del archivo existente y esperaba a los vacíos en cada vuelta | Nombre con fecha y hora si ya existe; los vacíos se saltan y se anotan una vez | Probar el vigilante con casos raros (ver `docs/07`) |
| No se puede conseguir clave de Pexels | Pexels ha pausado la emisión de claves de su API | Usar la API de Pixabay | Una función por fuente: cambiar de fuente no obliga a rehacer la herramienta |
| La clave podría salir en un mensaje de error | Pixabay la pide dentro de la URL y las excepciones de `urllib` guardan la URL | Mensajes solo con el código de error, lanzados fuera del `except` | Probar los errores con una clave falsa y buscarla en el texto |
| `buscar_clips` no aparecía en Claude Code | El servidor se había arrancado antes de añadir la herramienta y sin `--env-file` | Volver a registrarlo y reiniciar Claude Code | Reiniciar Claude Code tras cambiar el servidor o su registro |
| Un script de prueba no aparecía dentro del contenedor | Colima solo comparte la carpeta de usuario, no `/private/tmp` | Pasar el script por la entrada estándar (`docker run -i ... python - < script.py`) | |
| Dos archivos de música no coincidían con su línea del índice | Erratas: `realajada_01.mp3` en el nombre del archivo y `alegria_01_mp3` en el índice; además, una licencia mal escrita, un espacio de más, una etiqueta vacía y URLs repetidas o incompletas | Renombrar el archivo y corregir las líneas, con permiso | Validar el índice contra la carpeta (columnas, licencias, URLs, archivos sin línea) |
| Con 1,6 veces la duración del short se repetían planos | Cada corte gasta 0,5 s de margen y se pierde el final de cada clip | Simular el reparto real con cortes mínimos, medios y máximos | Comprobar los números de partida con una simulación |
| La primera simulación daba peor resultado del real | Usaba cortes de 1,48 s, por debajo de `corte_min` | Calcular los escenarios respetando `corte_min` y `corte_max` | Simular con los mismos límites que el código real |
| El servidor no podía usar `asignar_clips` | Imprimía avisos con `print()`, que rompe la comunicación MCP | Separar `repartir()`, que devuelve los avisos | `md5` para comprobar que la refactorización no cambia el resultado |
| Una receta creada antes de grabar perdía la plantilla y `preparar_short` le daba otro número | Una receta existente se usaba tal cual y el número siempre era el siguiente libre | Recetas *reservadas*: se ponen encima de la plantilla y `preparar_short` usa su número | Probar los cambios del vigilante en una copia temporal |
| Los clips se elegían con una duración que no era la real | Se medía el audio sin recortar, antes del paso `voz` | `despues_de_voz` en `crear()`, con la duración real | |
| El primer guion se pasaba de largo (138 palabras, unos 55 s) | Demasiado detalle en el dato y el giro | Recortarlo a 115 palabras antes de enseñarlo | La skill cuenta las palabras y estima la duración |
| El vigilante no usaba el código nuevo | Python carga el código al arrancar; llevaba en marcha desde el día anterior | Pararlo con SIGINT y arrancarlo de nuevo en segundo plano | Reiniciar el vigilante tras cambiar código |
| El final del vídeo quedaba mudo | `sidechaincompress` acaba con la voz y cortaba la música | `apad` alarga la voz hasta el final | Comparar la duración de las pistas de audio y vídeo con `ffprobe` |
| Un efecto no se oía | Los archivos de efectos tienen niveles de pico muy distintos | Igualar el pico de cada efecto antes de mezclar | Medir con `volumedetect` los archivos nuevos |
| Un efecto tenía que sonar en una palabra concreta | Los efectos automáticos caen en finales de frase al azar, y un segundo fijo se descuadra al regrabar | Efectos anclados a palabras en `efectos.lista` | La skill los propone cuando un efecto depende del texto |
| Al rehacer un short se perdió el vídeo anterior en revisión | El vídeo nuevo sustituye al de `data/revision/` sin avisar | Pendiente | |
| [Añade aquí otros problemas] | | | |

## Herramientas aprendidas

| Herramienta | Para qué |
|-------------|----------|
| `brew install --cask claude-code`, `brew upgrade claude-code` | Instalar y actualizar Claude Code |
| `claude`, `claude doctor` | Abrir una sesión en el proyecto y revisar la instalación |
| `Shift+Tab`, `/plan` | Cambiar el modo de permisos y pedir un plan antes de tocar nada |
| `claude mcp add` / `remove` / `get`, `/mcp` | Registrar el servidor MCP y ver su estado |
| Skills (`.claude/skills/`) | Instrucciones reutilizables, como `/guion-short tema` |
| `urllib.request`, `urllib.parse.urlencode` | Peticiones HTTP solo con la biblioteca estándar |
| `hashlib.sha256` | Huella de un texto: nombre de archivo para la caché |
| `docker run --env-file` | Pasar variables de entorno (claves) desde un archivo |
| `docker run -d --name`, `docker logs -f`, `docker kill --signal=SIGINT` | Servicio en segundo plano: arrancarlo, ver sus mensajes y pararlo limpio |
| `git check-ignore -v` | Comprobar qué regla de `.gitignore` ignora un archivo |
| `grep -rqF` | Buscar un texto sin mostrarlo (solo dice si está) |
| `open -e` | Abrir un archivo con TextEdit desde la terminal |
| `ffmpeg -af volumedetect` | Medir el volumen medio y el pico de un audio |
| `ffprobe -show_entries stream=codec_type,duration` | Comparar la duración de las pistas de audio y vídeo |
| `apad=whole_dur=` | Alargar un audio con silencio hasta una duración |

## Mis conclusiones
- [Añade aquí qué te ha parecido trabajar con Claude Code en modo manual]
- [Añade aquí qué te ha parecido dejar que Claude use la fábrica con herramientas]
- [Añade aquí qué has aprendido sobre guardar claves y secretos]
- [Añade aquí qué opinas de depender de una API externa (como el cierre de claves de Pexels)]
- [Añade aquí qué te ha aportado la skill para escribir los guiones]
- [Añade aquí lo que tú sientas que has aprendido]

## Pendiente
- No sobrescribir el vídeo de `data/revision/` al rehacer un short (guardar el nuevo con fecha y hora).
- Que un `riser` termine en la pausa en vez de estar centrado en ella (sube hasta el final).
- Poner los créditos ("Vídeos: <autor> en Pixabay") en la descripción de cada short.
- Añadir Pexels como segunda fuente cuando vuelva a dar claves.
- Aviso: `musica/relajada_02.mp3` dura 47,9 s (medido con `ffprobe`), menos de
  los 50 s recomendados. Solo sirve para shorts de unos 45 s como mucho.
- La URL de `misterio_02.mp3` en el índice es la de una búsqueda: no se encontró la original.
- [Añade aquí otros pendientes]
