# Fase 7: Automatización con Python

> Estado: fase terminada. Un audio soltado en `data/bandeja/` se convierte en un
> short completo en unos 5 minutos, sin intervención.

## Objetivo
Convertir todo lo que hacía a mano (voz, transcripción, subtítulos, cortes,
mezcla y render) en un programa que funcione solo, que sea flexible y que no
se vuelva rígido cuando tenga ideas nuevas.

```
data/bandeja/002-tema.wav
   ↓  el vigilante lo detecta y comprueba que se ha copiado entero
data/archivo/                    ← el audio original se guarda aquí
shorts/002-tema/config.json      ← la receta se crea sola desde una plantilla
   ↓  crear_short: voz → transcripción → subtítulos → fondo → render
data/revision/002-tema.mp4       ← listo para revisar (yo decido si pasa a listos/)
data/errores/                    ← si algo falla: el audio y un .log del error
data/registro.log                ← todo lo que pasa, con fecha y hora
```

---

## Principios de diseño (para que no sea rígido)

1. **Los valores van fuera del código**, en archivos de configuración.
2. **Configuración por capas**: `config/por_defecto.json` → plantilla
   (`config/plantillas/curiosidades.json`) → receta de cada short
   (`shorts/<nombre>/config.json`), que solo contiene lo que cambia.
   La función `fusionar()` las combina; las listas se sustituyen enteras.
3. **Piezas separadas**: un módulo por paso en `scripts/pasos/`.
4. **Dependencias**: cada paso declara de qué depende y solo se rehace si
   falta su resultado, si lo pido con `--rehacer` o si se rehízo algo de lo
   que depende (la misma idea que `make`).
5. **Git con ramas**: toda la fase se hizo en la rama `fase-7`, y se unió a
   `main` al terminar.
6. **La receta es una copia**: al crear un short, la plantilla se copia en su
   receta. Si cambio la plantilla, los shorts antiguos se siguen pudiendo
   reproducir igual. Contrapartida: para que un short vea los cambios de la
   plantilla, hay que borrar su receta.

## Estructura

```
config/
├── por_defecto.json          # Valores de todos los shorts
└── plantillas/
    └── curiosidades.json     # Música, efectos e inicio automático
scripts/
├── crear_short.py            # Director: función crear() y comando
├── vigilar_bandeja.py        # Vigilante de la carpeta bandeja
└── pasos/
    ├── utilidades.py         # ejecutar() y duracion()
    ├── voz.py                # Paso: voz (detección del inicio, cadena)
    ├── transcripcion.py      # Paso: faster-whisper palabra a palabra
    ├── subtitulos.py         # Paso: subtítulos ASS de pocas palabras
    ├── cortes.py             # Cortes automáticos y elección de efectos
    └── montaje.py            # Fondo de vídeo y render final
shorts/<nombre>/              # Recetas (van a Git)
data/shorts/<nombre>/         # Resultados (no van a Git)
```

## Uso

Vigilante (lo normal):
```bash
docker run --rm -t -v "$PWD:/proyecto" -e HF_HOME=/proyecto/data/modelos \
  shorts-whisper python /proyecto/scripts/vigilar_bandeja.py
```
El nombre del audio decide el short y el tema: `002-caballo.wav` crea el
short `002-caballo` con los vídeos del índice que llevan la etiqueta `caballo`.

Un short concreto, o rehacer un paso:
```bash
docker run --rm -t -v "$PWD:/proyecto" -e HF_HOME=/proyecto/data/modelos \
  shorts-whisper python /proyecto/scripts/crear_short.py 001-pulpo --rehacer subtitulos
```

- `-v "$PWD:/proyecto"`: el proyecto entero dentro del contenedor.
- `-e HF_HOME=...`: sustituye la variable de entorno de la imagen para que los
  modelos de Whisper se encuentren en su nueva ruta.

---

## Las seis partes

### 1. Orquestador y configuración
`crear_short.py` carga la configuración por capas y ejecuta los pasos.
`subprocess.run` lanza los mismos comandos de FFmpeg que antes escribía a mano.
Comprobación: la voz producida por el script tenía **la misma huella `md5`**
que la que hice a mano.

### 2. Fondo, mezcla y render
El fondo sale de la lista de cortes (`cortes.txt`). El grafo de la mezcla lo
genera el script a partir de la configuración. Comprobación: el fondo tenía
**la misma huella `md5`** que el de mi bucle manual.

### 3. Cortes automáticos en las pausas
Si la receta no tiene `cortes.txt`, el script genera `cortes_auto.txt` a partir
de las palabras de la transcripción.

- **Versión 1** (descartada): cortaba en la primera pausa válida. Problemas:
  cortes a mitad de frase, pausas importantes saltadas, último corte de 5,7 s
  y un plano repetido.
- **Versión 2**: en cada tramo (entre `corte_min` y `corte_max` segundos) elige
  la **mejor** pausa: la más larga, con +1 punto si cierra una frase (`.?!`) y
  +0,3 si es una coma. Sin pausas, corta entre dos palabras, nunca a mitad de
  una. Los clips van por turnos, sin repetir plano mientras quede material.
- Los cortes se redondean a **fotogramas** y FFmpeg corta con `-frames:v`,
  para que no se acumule desfase entre vídeo y voz.
- Valores: `corte_min` 1,5 s, `corte_max` 4 s, margen entre usos de un clip 0,5 s.

### 4. Efectos automáticos
Se eligen entre los cortes que caen en un final de frase, por puntuación,
separados al menos 8 s y lejos del inicio y el final. Con mi guion del pulpo
eligió los mismos momentos que yo había elegido a mano.

### 5. Volumen final
- **Primer intento**: `loudnorm` en dos pasadas (medir y aplicar en modo
  lineal). Falló con datos reales: si la ganancia necesaria hacía pasar el
  pico del límite, `loudnorm` volvía al modo dinámico.
- **Solución final** (la de masterización): mezclar → medir → aplicar la
  ganancia exacta que falta → limitador con el techo 1 dB por debajo del pico
  permitido → medir el archivo terminado.
- Resultado típico: a unas décimas de -14 LUFS, pico por debajo de -2 dBTP.

### 6. Carpeta bandeja
`vigilar_bandeja.py` revisa la bandeja cada 5 s, espera a que el archivo deje
de crecer (para no empezar con una copia a medias), prepara la receta desde la
plantilla, elige los clips por etiqueta del `indice.csv` y llama a `crear()`.
Un audio nuevo **siempre rehace todo desde la voz**.

**Inicio automático de la voz** (`"inicio": "auto"`): `silencedetect` busca el
silencio del principio y del final. Valores elegidos tras medir mi grabación:
umbral **-40 dB** (con -45 contaba la respiración como voz) y margen de
**0,15 s** antes del primer sonido. Limitación: si la respiración va pegada a
la primera palabra (menos de 0,5 s), no se pueden separar.

Primera prueba completa: **5,1 minutos** desde soltar el audio hasta tener el
vídeo en `data/revision/`.

---

## Problemas y soluciones

| Síntoma | Causa | Solución | Prevención |
|---------|-------|----------|------------|
| `IndentationError: unexpected indent` | Espacios de más al pegar código en nano | Reescribir el archivo entero | `compileall` tras editar |
| La terminal muestra `heredoc>` | El texto pegado se cortó y la shell esperaba `EOF` | `Ctrl + C` (no escribir `EOF`: guardaría el archivo cortado) | Descargar archivos completos en vez de pegarlos |
| `JSONDecodeError ... line 44 column 3` | Una llave `},` sobrante del bloque antiguo | Archivo completo validado | `python -m json.tool` |
| Mezcla 3 dB más baja de lo esperado | Pasar a mono **después** de normalizar: dos canales iguales suenan 3 dB más que uno | `aformat=channel_layouts=mono` al principio de la cadena | Medir cada etapa por separado |
| Volumen final en modo dinámico | El limitador fijo solo dejaba subir 2 dB | Ganancia calculada + limitador | Probar con varios casos, no solo uno |
| `'NoneType' object has no attribute 'strip'` | Al índice le faltaba la columna `fuente` | `sed` para insertarla | El vigilante comprueba las columnas y dice qué línea falla |
| Aviso "el fondo dura menos que la voz" | Diferencia de milésimas por el redondeo a fotogramas | Tolerancia de 0,05 s | |
| Inicio con demasiado espacio | Umbral de -45 dB: contaba la respiración | Umbral y margen configurables | Medir con un bucle de umbrales |
| Una grabación archivada podía desaparecer | Un audio nuevo con el mismo nombre se movía encima del de `data/archivo/` | El nuevo se guarda con la fecha y la hora en el nombre | Nunca mover un archivo sin comprobar antes si el destino existe |
| Un archivo vacío frenaba la bandeja sin dejar rastro | `esta_completo()` esperaba 3 s en cada vuelta y lo descartaba en silencio | Saltarlo sin esperar y anotarlo una vez en el registro | Probar el vigilante con casos raros (vacíos, nombres repetidos) |
| [Añade aquí otros problemas] | | | |

Al editar código y datos: `git diff` antes de guardar enseña exactamente qué
ha cambiado, y `git show` permite ver la línea que rompía un archivo.

---

## Herramientas aprendidas

| Herramienta | Para qué |
|-------------|----------|
| `git switch -c`, `git branch`, `git merge` | Ramas: trabajar sin tocar `main` y unir al final |
| `git log --stat`, `git show`, `git diff` | Ver qué cambió, en qué commit y en qué línea |
| `cat > archivo << 'EOF'` | *Heredoc*: escribir un archivo tal cual desde la terminal |
| `python -m compileall -q` | Comprobar la sintaxis de todos los scripts |
| `python -m json.tool` | Comprobar que un JSON es válido |
| `md5` | Huella de un archivo: comprobar si dos son idénticos |
| `sed -i '' 's/viejo/nuevo/'` | Sustituir texto sin abrir un editor (en Mac, `-i ''`) |
| `sed -E` con `([0-9]{4})` y `\1` | Expresiones regulares: reordenar partes de un texto |
| `sed -n '20,35p'` | Ver un rango de líneas |
| `awk -F, '{print NR, NF}'` | Contar columnas de cada línea |
| `grep -n`, `grep -m1 -o` | Buscar con número de línea / solo la primera coincidencia |
| `ls -t`, `ls -l`, `head -n` | Archivos por fecha, detalles, primeras líneas |
| `docker run -e VAR=valor` | Sustituir una variable de entorno de la imagen |

## Qué he aprendido
- Que un script flexible depende del diseño: configuración fuera del código,
  piezas separadas y dependencias claras.
- Que una solución que funciona en una prueba puede fallar con datos reales,
  y por eso hay que probar varios casos.
- Que medir cada etapa por separado destapa errores que el resultado final
  esconde (los 3 dB de la voz llevaban ahí desde la Fase 4).
- [Añade aquí lo que tú sientas que has aprendido]

## Gestión del almacenamiento

Cada short dejaba varias copias del mismo material: 16 cortes sueltos, el
fondo con los cortes unidos, la mezcla, y el vídeo final duplicado en
`data/shorts/` y en `data/revision/`.

Criterio: conservar las **fuentes originales** y lo que es caro de
regenerar; borrar lo que se puede rehacer en poco tiempo.

| Archivo | Qué pasa ahora |
|---------|----------------|
| `cortes/` | Se borra en cuanto se une en `fondo.mp4` |
| `fondo.mp4`, `mezcla.wav` | El vigilante los borra al terminar el short |
| `final.mp4` | El vigilante lo mueve a `revision/` (sin duplicar) |
| `voz.wav` y los archivos de texto | Se conservan: permiten retocar sin volver a transcribir |
| `data/archivo/` (grabaciones originales) | Se conserva siempre: es lo único insustituible |

Contrapartida: retocar un short terminado obliga a regenerar el fondo
(unos 2 o 3 minutos más).

Limpieza de lo acumulado en las fases anteriores (`data/trabajo` 322 MB y
`data/salida` 283 MB). Después, `data/` ocupa [completa con el resultado
de `du`]. Lo más pesado son los modelos de Whisper (1,9 GB), que se conservan.

Comandos: `du -sh data/* | sort -h` para ver qué ocupa más, y `rm -rf` para
borrar (es permanente: comprobar antes con `ls`).

## Robustez del vigilante

Dos casos raros que el vigilante no trataba bien:

- **Nombre repetido**: si soltaba otra vez `002-caballo.wav`, `shutil.move`
  lo movía encima de la grabación que ya estaba en `data/archivo/` y la
  original se perdía. Ahora, si el destino ya existe, el nuevo se guarda
  como `002-caballo_AAAAMMDD-HHMM.wav` y se anota en el registro. El short
  sigue llamándose `002-caballo` y se rehace con la grabación nueva.
- **Archivo vacío** (0 bytes): nunca se procesaba, pero en cada vuelta
  `esta_completo()` esperaba 3 s para nada y no se anotaba en ningún sitio.
  Ahora se salta sin esperar y aparece una sola línea `VACÍO` en
  `data/registro.log`. Si después recibe contenido, se procesa con normalidad.

Además se corrigió la descripción del script: el vídeo terminado se **mueve**
a `data/revision/` (no se copia), como se explica en "Gestión del
almacenamiento".

## Pendiente
- Margen inicial configurable para los efectos (ninguno en los primeros
  segundos del gancho).
- Afinar el volumen final tras el limitador (queda unas décimas por debajo).
- Acelerar el render (unos 100 s para 43 s de vídeo).
- Lanzar el vigilante en segundo plano para no ocupar una pestaña.
- Fase 8: servidor MCP, Claude Code, búsqueda de clips con la API de Pexels y
  el guion diario.

## Resuelto después de cerrar la fase
- Limpieza automática de los archivos temporales (ver "Gestión del
  almacenamiento").
- El vigilante ya no sobrescribe grabaciones archivadas e ignora los
  archivos vacíos (ver "Robustez del vigilante").
