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
| 2 y 3 | Índice con licencia y atribución, fotos en el índice, `generico`, fuente Wikimedia Commons (`scripts/fuentes/`), ventana de progreso, arreglos de voz, planos y números (short 012) | `0d451a9` |
| — | Orden de recursos (vídeo antes que foto) y Git solo con el sistema | `5b56c84` |
| 3b, 4 y 5 | Fuente NASA, publicación sin créditos (`revisar_publicacion.py`), skill con temas y material primero, `shorts/ideas.md` | |

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

## Publicación sin créditos

Decisión del usuario: los créditos ya no se escriben en `publicacion.md`; el autor y la
licencia de cada archivo se quedan solo en `biblioteca/indice.csv`, en local. Como **CC BY obliga
a citar al autor allí donde se publica**, a partir de ahora solo se usa material que no lo
exige: Pixabay, Pexels, dominio público, CC0 y la NASA (pide reconocerla, pero no lo exige).
- Commons acepta solo dominio público y CC0 (las 34 fotos CC BY de Perpiñán quedan fuera).
- `creditos.py` pasa a ser `revisar_publicacion.py`: no escribe nada; comprueba que ningún
  archivo del short exija atribución y mide los textos. 012 da error: usa 9 fotos CC BY.

## Fuente NASA (`scripts/fuentes/nasa.py`)

Sin clave. Busca vídeos y fotos a la vez (`media_type=video,image`) de 12 en 12, porque cada
resultado necesita dos consultas más: el manifiesto (`/asset`) y `metadata.json` (ancho, alto
y duración, para ordenar por prioridad sin descargar). Rechaza lo de terceros (©, courtesy,
SpaceX, ESA...). Problemas: un original de 6,3 GB (se usa `~large`), y rutas con espacios
(«SLS Roll Out Beauty Shot») que Python no quería pedir: se codifican; una miniatura que falla
ya no tumba el servidor.

## Skill e ideas

- **Skill**: sección «0. Tema y material» (temas por defecto, actualidad, neutralidad en temas
  políticos, primero el material auténtico, superlativos verificados) y fórmulas de título.
- **`shorts/ideas.md`** (local): 15 temas con el material legal comprobado mirando miniaturas.
  Lección: en Pixabay el filtro solo exige la primera palabra en las etiquetas, y «palm»,
  «sphere» o «three» devolvían palmeras, bolas de cristal y velas; el recuento no basta.
- **Marca `[generico]`**: el plan la proponía, pero en 012 bastó con `[plano]` y la etiqueta
  `generico` del índice (que la saca del relleno automático). Se queda una sola marca.

## Short 013-crawler: flecha, cartelas de la NASA y efectos que no tumban el short

- **Tema**: la pista de esquí cubierta de Shanghái (L+SNOW) no tenía ni un vídeo legal del sitio, así
  que, como dice la skill, se cambió de tema: el crawler-transporter (la NASA, mucho vídeo).
- **Flecha** (`[flecha x y]`): una flecha roja pequeña que apunta a algo del clip, con su sonido
  (`ding_01`). Las coordenadas son del clip y se pasan a la pantalla vertical según el encuadre
  (`en_pantalla()`); se dibuja con `geq` y se superpone antes de los subtítulos con un rebote.
  El primer dibujo salía casi sin borde: el borde era más pequeño que la parte roja.
- **`video.saltar`**: los vídeos de la NASA empiezan con una cartela azul de 5-10 s; la receta dice
  cuántos segundos no usar de cada clip para el relleno.
- **Efecto sin su palabra**: si Whisper escribe la palabra de otra forma, el efecto se salta con
  un aviso en vez de parar todo el short.
- **Hojas de clips largos**: con vídeos de 5 minutos, una hoja de un fotograma por segundo sería
  enorme; se miró uno cada 5 s y después los tramos elegidos segundo a segundo.

## 013 con planos verticales y relleno sin repeticiones

- **Vertical**: la NASA tenía un vídeo vertical (1080x1920) de la luna llena detrás del cohete de
  Artemis II en la plataforma (febrero de 2026) y fotos verticales del crawler CT-2 (enero de 2026).
  Entraron como planos en «la vuelta a la Luna», «Pesa unas tres mil toneladas» y «Siete
  kilómetros…»; las fotos, con Ken Burns.
- **Relleno repetido**: el relleno no podía usar los clips protagonistas, y con los dos clips que
  quedaban (uno de 6 s útiles) repitió el mismo tramo 5 veces. Ahora un protagonista también entra
  en el relleno, pero solo en su tramo libre más largo (`ventana_libre()`), así que su plano bueno
  no se repite. `saltando()` acepta esas ventanas (sin ellas, todo sale como antes).

## Qué he aprendido
[completa con lo que has aprendido en esta fase]
