# Fase 10: Fábrica 2.0

> Estado: en curso.

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
| 3 | Ritmo variable y planos protagonistas (`cortes.py`, `material.py`) | |

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

## Qué he aprendido
[completa con lo que has aprendido en esta fase]
