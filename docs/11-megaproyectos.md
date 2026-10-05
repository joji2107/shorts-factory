# Fase 11: Megaproyectos y nuevas fuentes

> Estado: en curso.

## Objetivo
Cambiar la línea temática del canal a **megaproyectos, ingeniería imposible, construcciones,
vehículos y lugares extremos o extraños**. En estos temas no basta con material genérico:
hace falta material **auténtico del objeto concreto** (el viaducto de Millau, no un puente
cualquiera) y con licencia válida. Para conseguirlo se añaden dos fuentes (Wikimedia Commons y
la biblioteca de la NASA), cada una en su módulo, y la posibilidad de usar **fotos** como clips,
porque Commons tiene muchas más fotos que vídeos.

| Parte | Qué se hizo | Commit |
|---|---|---|
| 1 | Fotos como clips (Ken Burns): `pasos/clips.py` | `c374c9a` |
| 2 y 3 | Índice con licencia y atribución, fotos en el índice, `generico`, fuente Wikimedia Commons (`scripts/fuentes/`), ventana de progreso, arreglos de voz, planos y números (short 012) | |
| — | Orden de recursos (vídeo antes que foto) y Git solo con el sistema | |

---

## Parte 1: fotos como clips (efecto Ken Burns)

**Idea**: una foto es un «vídeo virtual» de `video.imagen.segundos` (8 s): un movimiento lento y
continuo sobre toda la foto. Un corte `foto inicio largo` de la lista de cortes toma ese tramo
del movimiento, igual que en un vídeo. Así no cambia nada del resto: el reparto, `desplazar()`,
los `[plano foto desde largo]` y las hojas de fotogramas funcionan igual, y dos cortes de la
misma foto enseñan partes distintas.

- **`scripts/pasos/clips.py`** (nuevo): `ruta_clip()` busca `data/biblioteca/video/<clip>.mp4`
  y, si no está, `data/biblioteca/imagen/<clip>.jpg`; `duracion_clip()` da la duración del
  vídeo o la del vídeo virtual; `filtro_foto()` hace el movimiento. Sustituye las rutas
  `f"{clip}.mp4"` que había repartidas por `cortes.py`, `montaje.py`, `material.py`,
  `hoja_fotogramas.py` y `creditos.py`.
- **Movimiento**: si la foto es más ancha que 3:4, se desplaza de lado (como mucho un ancho de
  pantalla en los 8 s, unos 135 px/s); si es vertical o casi cuadrada, zoom de 1,00 a 1,12
  hacia el centro. El sentido sale del nombre del archivo, así que el resultado se repite.
- **Velocidad**: `video.imagen.velocidad` (1 por defecto) para todo el short, o una por foto en
  `video.imagen.por_foto` (`{"millau_03": 2}`). Multiplica el recorrido y el zoom, **no** la
  duración: con 2 la foto se mueve el doble en los mismos 8 s, así que el material que da (para
  el reparto y `evaluar_material`) no cambia. El desplazamiento no pasa del borde de la foto: en
  una foto poco ancha, la velocidad real se queda por debajo de la pedida.
- **Sin temblor**: `crop` y `zoompan` redondean la posición a píxeles enteros, y en un
  movimiento lento eso se nota como saltitos. Se calcula a 2160x3840 y se reduce a 1080x1920.
- **Sin estado**: la posición se calcula con el número de fotograma (`n` en `crop`, `on` en
  `zoompan`) desplazado `inicio·30`, no sumando un poco en cada fotograma. Por eso un corte
  puede empezar en cualquier punto del vídeo virtual.
- **Problema**: en la hoja de fotogramas de una foto salían 12 segundos de un vídeo de 8. El
  `-frames:v` que limitaba la entrada lo anulaba el `-frames:v 1` de la salida (el mosaico), y
  con `-loop 1` la foto se repite sin fin. Solución: `-t 8` **antes** de `-i`, que limita la
  entrada.

**Comprobaciones**:
- 004-elefante (método de la fase 10, parte 6): la lista de cortes con semilla (`0228c49c…`) y
  `fondo.mp4` (`d9c21707…`) salen idénticos. La configuración fusionada solo cambia por la
  clave nueva `video.imagen.segundos`.
- Prueba en `data/pruebas/kenburns/` con dos fotos sintéticas (horizontal y vertical) y tres
  cortes: dos renders con el mismo md5, 270 fotogramas exactos y el tercer corte de la misma
  foto continúa el recorrido (`a535950b…` con el recorrido de 1,5 pantallas del principio;
  `27e77b3d…` con el de 1 pantalla, que es el que queda). Después, con fotogramas reales de La Palma.
- **Prueba de velocidades con una flecha roja** que señala la colada (`prueba_flecha_velocidades.mp4`):
  la misma foto a 0,5, 1 y 2, 5 s de cada una. La flecha se dibuja **sobre la foto, antes del
  movimiento**, así que acompaña a la lava. Dos renders, mismo md5 (`fa473026…`).
- **Problema con la flecha**: con `drawtext` y el carácter `⬇` salía un rombo con «?» (bytes
  UTF-8 rotos al pasar el carácter por varias capas de shell hasta FFmpeg; con `font=DejaVu Sans`
  a veces sí salía). Solución: dibujarla con geometría en el filtro `geq` (mango + punta
  triangular, con borde blanco) desde Python, pasando los argumentos como lista: no depende de
  fuentes ni de comillas. Dentro de un filtro, las comas separan filtros: la expresión de `geq`
  va entre comillas simples.

## Grabación en silencio (012-protestas_francia)

La primera grabación de 012 llegó en **silencio digital**: 45 s a -91 dB (la pista de GarageBand
no tenía entrada de micro). La fábrica falló al normalizar con un error que no decía nada
(`'NoneType' object has no attribute 'group'`: `ebur128` no da pico de un archivo mudo).
Ahora `comprobar_que_suena()` (en `pasos/voz.py`) mide el pico con `volumedetect` antes de
nada y, por debajo de -60 dB, para diciendo qué revisar en GarageBand.

## Short 012-protestas_francia: dos fallos más y una ventana de progreso

- **Planos que se pisan**: con el ritmo real de lectura, la foto de 2006 se comía 0,5 s de la
  siguiente y el montaje paraba. Ahora el primer plano se acorta solo (con aviso) si le quedan
  al menos 2 s; solo da error si no cabe.
- **Vídeo mudo al principio**: un clic de 0,25 s en el segundo 0,8 y luego 2,9 s de silencio.
  `detectar_voz` tomaba el clic por el principio de la voz y `quitar_ruidos` no lo quitaba (su
  límite era 0,15 s). Ahora un sonido de hasta 0,6 s seguido de 1 s de silencio también es ruido.
  Además había «tramos» de duración cero que partían ese silencio: se ignoran.
- **Ventana de progreso**: al dejar una grabación en la bandeja se abre una página con la barra
  y los pasos; si falla, notificación y el porqué con qué hacer; al terminar, se abre el vídeo.
  El vigilante escribe el estado (`scripts/progreso.py`) y un script del Mac
  (`ventana_progreso.sh`, que lanza `arrancar.sh`) abre la página y el vídeo, porque desde
  Docker no se pueden abrir ventanas en el Mac. El JSON se lee con `plutil`, que viene con macOS.

## 012: «75» en vez de «treinta y cinco» y un short solo de fotos

- **Número mal oído**: dije «clases de treinta y cinco» y Whisper escribió «clases 75». La
  corrección con el guion no lo veía (4 palabras contra 1). Ahora se compara el valor del número:
  `valor_numero()` traduce «treinta y cinco» a 35; si la cifra transcrita tiene otro valor, se pone
  el texto del guion. Si coincide («2006», «2000»), se deja la cifra (antes «400» pasaba a
  «cuatrocientos»; ahora se queda en cifra).
- **Solo fotos**: del tema solo había fotos de Commons y el short salió sin ningún vídeo. Se añadió
  vídeo real de contexto (París a vista de dron, un aula llena) como `generico`, solo en sus dos
  frases. El vigilante avisa si un short es todo fotos, y la skill lo pide desde el principio.
  Los vídeos de protestas de Pixabay eran de Escocia y de Rusia: usarlos habría sido presentar
  otras protestas como si fueran estas.

## Orden de recursos y Git solo con el sistema

- **Orden de los recursos**: vídeo vertical → vídeo horizontal → foto vertical → foto horizontal;
  se pasa al siguiente solo si no hay nada del anterior. `prioridad()` en `material.py` ordena el
  relleno que elige el vigilante (como coge los mínimos que bastan, las fotos solo entran si los
  vídeos no alcanzan) y `ver_candidatos` ordena igual. Lo real sigue yendo antes que la IA.
- **En Git solo el sistema**: código, configuración de la fábrica, skills, documentación y
  scripts. El contenido de los shorts (`shorts/`, salvo el texto de prueba `901-prueba_voz`;
  `biblioteca/indice.csv`, `biblioteca/musica.json` y `config/lectura.json`) pasa a `.gitignore`
  y se quita del repositorio con `git rm --cached`, que lo deja en el disco. El historial anterior
  sigue teniendo las versiones viejas. `lectura.py` ya no falla si `lectura.json` no existe.

## Qué he aprendido
[completa con lo que has aprendido en esta fase]
