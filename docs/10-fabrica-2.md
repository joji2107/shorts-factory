# Fase 10: Fábrica 2.0

> Estado: terminada.

## Objetivo
Una nueva versión de la fábrica con otra forma de contar y de montar los shorts:
narrativa de promesa y recompensa, ritmo variable con clips protagonistas, respiros
(momentos sin voz en los que hablan la imagen y la música) y música que llega a su
momento fuerte en la revelación final. Todo es opcional y depende de la versión de la
receta, para que los shorts anteriores se sigan reproduciendo igual.

| Parte | Qué se hizo | Commit |
|---|---|---|
| 1 | Versiones de la fábrica: `config/versiones/`, `promover_version.py`, versión en métricas | `ef0d3e4` |
| 2 | Marcas del guion (`marcas.py`) y paso `respiros` | `a62f00f` |
| 3 | Ritmo variable y planos protagonistas (`cortes.py`, `material.py`) | `66f357d` |
| 4 | Música con energía: `musica.json`, inicio automático y subida en los respiros | `5cb861f` |
| 5 | Skill `guion-short` (sección Fábrica 2.0), `hoja_fotogramas.py` y `evaluar_material` con versión | `9e31343` |
| 6 | Prueba completa (011-volcan) y 2.0 como versión por defecto | `a194a80`, `4f803ec` |
| 7 | Scripts `arrancar.sh` y `apagar.sh` | `f6b85db` |

---

## Parte 1: versiones de la fábrica

### Qué hace
Cada receta guarda con qué versión de la fábrica se hizo (`"version_fabrica"` en su
`config.json`). La configuración se fusiona en tres capas:

1. `config/por_defecto.json`: todos los valores (y la versión por defecto).
2. `config/versiones/<versión>.json`: lo que cambia en esa versión, **congelado**.
3. La receta.

`1.0.json` apaga lo nuevo (`respiros.activo`, `video.ritmo.activo`, `musica.inicio: 0`)
y `2.0.json` lo enciende. Si mañana cambian los valores por defecto, un short de la 1.0
sigue viendo los de la 1.0.

Mientras dura la prueba, la versión por defecto es 1.0 y solo las recetas que dicen
`"2.0"` usan lo nuevo. Cuando la 2.0 esté probada:

```bash
docker run --rm -t -v "$PWD:/proyecto" shorts-whisper python /proyecto/scripts/promover_version.py 2.0 --simular
docker run --rm -t -v "$PWD:/proyecto" shorts-whisper python /proyecto/scripts/promover_version.py 2.0
```

El script fija a la versión de antes todas las recetas que no dicen la suya (también
las reservadas: su guion se escribió con la estructura antigua) y cambia la versión por
defecto. Añade una sola línea a cada receta (no reescribe el archivo, porque 001 y 002
tienen otro formato) y repetirlo no cambia nada.

`metricas.csv` guarda también la versión, `analizar_metricas.py` agrupa por ella y
`listar_shorts` la enseña, para poder comparar la 1.0 y la 2.0 con datos.

### Comprobación
- La configuración fusionada de los 12 shorts es idéntica a la de antes (sin contar las
  claves nuevas), y también después de promover (probado en una copia).
- La segunda ejecución de `promover_version.py` dice «Nada que cambiar».

---

## Parte 2: marcas del guion y respiros

### Marcas
Van entre corchetes en el `## Guion`, **antes de la palabra** en la que actúan, y no se
leen en voz alta:

- `[respiro 3]`: 3 s de silencio en ese hueco (sin número, `respiros.segundos`: 2,5 s).
- `[plano volcan_03 12.5 6]`: clip protagonista (se usa en la parte 3).

`scripts/pasos/marcas.py` cuenta cuántas palabras dichas hay antes de cada marca y
busca esa posición en la transcripción con la alineación de los subtítulos (`alinear`).
Si Whisper oyó mal la palabra de después, usa la siguiente a la de antes.

### Por qué los inserta el sistema y no se graban
Se valoraron dos opciones: hacer la pausa al grabar o insertarla después. Se eligió
insertarla:
- dura exactamente lo que dice el guion, y se cambia sin volver a grabar;
- es silencio digital (−91 dB): una pausa grabada tiene el ruido de la sala, que la
  cadena de voz sube;
- Whisper tiende a inventarse texto en los silencios largos;
- la velocidad de lectura no se falsea (se mide con `palabras.json`, sin respiros).

### El paso `respiros`
Va después de la transcripción y solo se ejecuta con `respiros.activo` (versión 2.0).
Corta `voz.wav` por número de muestra en el centro de cada hueco, mete el silencio y
escribe `voz_respiros.wav`, `palabras_respiros.json` (tiempos desplazados) y
`respiros.json` (dónde cae cada respiro en el vídeo final). Subtítulos, cortes, efectos
anclados y render leen esos archivos, así que todo se desplaza solo.

Sin respiros activos el paso se salta y no cuenta como rehecho: los pasos siguientes
usan `voz.wav` y `palabras.json` como siempre. Si se cambia un `[respiro]` del guion,
`--rehacer respiros` (el paso no vigila `guion.md`, igual que con las negritas).

### Comprobación
- Subtítulos de los 10 shorts generados con el `subtitulos.py` de antes y el de ahora:
  idénticos.
- Short de prueba 902-respiros (la voz de 008 con `[respiro 3]` y `[respiro]`): la voz
  tiene exactamente 264 000 muestras más (5,5 s a 48 kHz), los huecos miden −91 dB,
  «Y TODAVÍA HAY» pasa de 22,04 s a 25,04 s y el efecto anclado a «más», de 22,8 s a 25,8 s.

---

## Parte 3: ritmo variable y planos protagonistas

### Qué hace
Con `video.ritmo.activo` (versión 2.0), `cortes.py` monta la lista de cortes en tres pasos:

1. **Tramos fijos.** Cada `[plano clip desde largo]` empieza 0,1 s antes de su palabra
   (o con el respiro que tiene justo delante) y dura `largo` aunque pase de `corte_max`
   (hasta `plano_max`, 9 s). Cada respiro sin protagonista es un tramo de un solo plano.
2. **Relleno.** Los huecos entre tramos fijos se cortan con el mismo `puntos_de_corte()`
   de siempre, pero entre `relleno_min` y `relleno_max` (1-2,2 s). Un hueco más corto que
   `relleno_min` alarga el tramo anterior en vez de dejar un fogonazo.
3. **Reparto.** `repartir()` reparte solo el relleno, con los clips de la receta menos los
   protagonistas; los protagonistas no pasan por `desplazar()`, porque su segundo de
   inicio lo eligió la skill mirando los fotogramas.

El contraste entre los cortes rápidos y los planos largos es lo que da ritmo.

Los errores dicen qué marca falla: un plano que se sale del clip, que dura más que
`plano_max` o que se pisa con otro tramo.

El vigilante descuenta el tiempo de los planos y elige el relleno sin los protagonistas;
`material.py` simula el reparto con los cortes de relleno.

### Comprobación
- Listas de cortes de los 9 shorts con clips automáticos, generadas con el `cortes.py` de
  antes y el de ahora con la misma semilla de azar: idénticas.
- 902-respiros con `[plano orionidas_06 10 6]` y `[plano orionidas_04 30 7]` tras el
  `[respiro 3]`: el primero va de 11,63 a 17,63 s, el segundo empieza con el respiro
  (21,97 s), el último respiro es un solo plano de 2,5 s y el resto, 18 cortes de 1,1 a
  2,2 s. Los cortes suman 41,433 s, lo mismo que el vídeo.

---

## Parte 4: música con energía

### Energía de cada canción
`scripts/analizar_musica.py` (en Docker; `--todas` para repetir las ya analizadas) mide
cada canción con `ebur128` (sonoridad de corto plazo, ventana de 3 s), la resume en un
valor por segundo y busca su **momento fuerte**: el segundo en que más sube la media de
los 6 s siguientes sobre la de los 6 s anteriores (la entrada del estribillo o del
*drop*). Lo que viene tiene que quedar al menos 0,5 dB sobre la mediana de la canción y
no se busca en los 10 primeros segundos (la intro). Si la mayor subida no llega a 3 dB,
la canción es **plana**.

Se guarda en `biblioteca/musica.json` (va a Git; una línea por canción): duración,
mediana, momento fuerte, subida, dB sobre la mediana, si es plana y la curva por
segundo. No va en `indice.csv` porque el índice es de licencias, con 8 columnas fijas, y
la curva es una lista.

**Problema:** la primera versión pedía que el tramo fuerte quedara 2 dB sobre la mediana.
`misterio_03` es fuerte casi todo el rato (mediana alta) y su mejor momento, la vuelta
tras un valle de −20 dB en el segundo 127 (+8,6 dB), se descartaba; ganaba el 46.
**Solución:** lo que se nota es el contraste con lo que sonaba justo antes, así que la
mediana solo sirve para descartar subidas desde el silencio (0,5 dB), y plana se decide
por la subida.

Resultado con las 11 canciones: solo `misterio_03` (8,6 dB) y `alegria_03` (5,2 dB) pasan
de 5 dB; 5 tienen subidas suaves (3-4,4 dB) y 4 son planas.

### En el render
- `musica.inicio: "auto"` (versión 2.0): la canción empieza en `momento fuerte −
  revelación`, siendo la revelación el último respiro. Si el momento fuerte llega antes que
  la revelación, desde 0; si la canción se acabaría antes que el vídeo, se adelanta lo
  justo (`inicio_musica()`, con aviso). Sin respiros, sin analizar o plana: desde 0, con aviso.
- En cada respiro la voz calla, así que el *ducking* se suelta solo, y además la música
  sube `respiros.subida_musica_db` (5 dB) con un `volume` por fotograma: empieza a subir al
  callarse la voz y termina de bajar justo cuando vuelve (rampas de 0,5 s). Sin respiros,
  el grafo es el de siempre.
- **Problema:** en 902-respiros, con la revelación a 36,56 s, `misterio_03` empieza en
  90,44 s y la revelación suena en pleno momento fuerte (−17,5 LUFS solo con música, la
  voz va a −13/−15). Pero el primer respiro caía en el valle de antes del *drop* y sonaba
  a −28 LUFS: un silencio muerto. Mover la canción rompería la sincronía, así que el
  render avisa (`respiros_flojos()`) cuando un respiro cae 6 dB o más por debajo de la
  mediana de la canción, para moverlo o quitarlo en el guion.

### Comprobación
- `construir_grafo_audio()` de antes y de ahora con la música de los 9 shorts, con y sin
  efectos: 40 de 40 grafos idénticos.
- Sonoridad momentánea del vídeo de 902 medida segundo a segundo (arriba).

---

## Parte 5: la skill y las herramientas para elegir protagonistas

- **Skill `guion-short`**: sección nueva «Fábrica 2.0», que se usa si la versión por
  defecto es 2.0 o se pide. Estructura promesa → escalones → revelación → cierre que
  enlaza con la promesa, 90-110 palabras, las marcas `[respiro]` y `[plano]`, cómo elegir
  protagonistas y música (no plana, subida de 5 dB o más, momento fuerte después de la
  revelación y ningún respiro en un valle). Al cargarse lee la versión por defecto y la
  tabla de energía de `musica.json`, y escribe `version_fabrica` en las recetas nuevas (las
  antiguas la recibieron en la parte 6, con `promover_version.py`).
- **`scripts/hoja_fotogramas.py <clips o tema>`**: un fotograma por segundo en mosaico,
  con el segundo escrito, en `data/cache/fotogramas/<clip>.jpg`. Sirve para elegir el
  clip y el `desde` de cada plano mirando qué pasa en cada momento.
- **`evaluar_material(..., version="2.0")`**: simula el reparto con los cortes de relleno
  (1-2,2 s en vez de 1,5-4 s). Como duración se le pasa voz + respiros − planos.

## Parte 6: prueba completa y la 2.0 por defecto

- **Prueba completa: 011-volcan**, el primer short 2.0 con material real (8 clips de la
  erupción de La Palma de 2021 y una costa de lava). Tres planos protagonistas, dos respiros
  (2 s y 3 s) y `alegria_03` empezando en su segundo 93,6 para que su momento fuerte (120 s)
  caiga en la revelación. Salió en 2,4 min y sin errores: 45,2 s.
- **Promoción**: `promover_version.py 2.0` fijó a la `1.0` las 11 recetas que no decían
  versión (001-010 y 900), creó el `config.json` de 901-prueba_voz (solo tenía el guion) y
  cambió la versión por defecto a `2.0`. La segunda ejecución dice «Nada que cambiar».
- **Skill**: la 2.0 es lo normal (plantillas de `guion.md` y `config.json` de la 2.0); la
  estructura clásica solo si se pide un short 1.0.

**Comprobación sin regresiones** (004-elefante). Rehacer el paso `fondo` no sirve para
comparar: vuelve a generar `cortes_auto.txt`, que tiene azar (`desplazar()` y el reparto
entre clips empatados), y además sobrescribe los archivos de un short publicado. Así que se
comparó, en una carpeta aparte, antes y después de promover:

| Qué | Antes | Después |
|---|---|---|
| `cargar_config()` fusionada | `8ba809f5…` | `8ba809f5…` |
| `crear_edl()` con `random.seed(2026)` | `0228c49c…` | `0228c49c…` |
| `fondo.mp4` con su `cortes_auto.txt` real | `d9c21707…` | `d9c21707…` |

El «antes» se ejecutó dos veces para comprobar que la prueba es repetible. Sin la línea
`"version_fabrica": "1.0"`, 004 heredaría la 2.0 (respiros, ritmo y música automática):
esa línea es lo que lo mantiene igual.

## Arrancar y apagar: `arrancar.sh` y `apagar.sh`

Dos scripts en la raíz (se ejecutan en el Mac, no en Docker) para el día a día:
- **`./arrancar.sh`**: `colima start` si `colima status` dice que no está en marcha, comprueba
  que Docker responde y que existe la imagen `shorts-whisper`, lanza el vigilante si no hay
  un contenedor `vigilante` corriendo y enseña el estado (Colima, vigilante con las 3 últimas
  líneas del registro, bandeja, rama y cambios sin guardar). Acaba recordando abrir Claude Code.
- **`./apagar.sh`**: se niega (código 1) si hay audios en la bandeja o un short procesándose,
  avisa de los cambios sin guardar en Git, para el vigilante con `docker kill
  --signal=SIGINT` (espera hasta 30 s a que salga) y hace `colima stop`.

**Por qué se niega con un short en marcha**: el vigilante solo atrapa `KeyboardInterrupt`
alrededor del bucle, y `procesar()` solo atrapa `Exception`, que no lo incluye. Un SIGINT a
mitad de un short lo corta: la grabación ya está en `data/archivo/` y el short queda a medias,
sin pasar a `errores/`. Para saber si hay uno en marcha, `awk` busca en el registro el último
`INICIO <short>` y mira si después está su `OK` o su `ERROR`.

Los dos se pueden repetir: con todo en marcha, `arrancar.sh` no relanza nada; con todo
apagado, `apagar.sh` dice «Colima ya está parado» y sale con 0. Probado: dos arranques
seguidos (desde `/tmp`), apagado con la bandeja ocupada y con un registro falso con un
`INICIO` abierto (se niega en los dos), y apagado real dos veces seguidas.

## Qué he aprendido
[completa con lo que has aprendido en esta fase]
