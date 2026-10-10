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

## Short 014-mediterraneo: marcas de agua, música igualada y subtítulos

Continuación de 010 (por qué el Mediterráneo está tan caliente). Empieza con un clip de TikTok
nuevo (`lluvia-cataluna-007`, un rayo sobre Barcelona) y usa clips de lluvia de 010. El primer
render tuvo varios fallos que se arreglaron en el sistema, no solo en la receta:

- **No empezaba con el rayo**: la primera palabra estaba en el 0,46 s y el plano en el 0,36;
  la regla que lo adelanta al 0 necesitaba empezar antes en el clip, y el plano ya empezaba en
  su segundo 0. Ahora, en ese caso, el plano se alarga por delante.
- **Marcas de agua de TikTok sin tapar**: en 010 se desenfocaron a mano sobre el vídeo final,
  calculando cuándo se veía cada clip. Ahora las cajas de cada clip están en
  `biblioteca/marcas.json` (en fracciones del fotograma del clip y con los segundos del clip en
  que se ven) y `generar_fondo` las desenfoca al cortar el clip, con los bordes difuminados.
  Salen tapadas en cualquier short y en cualquier momento. TikTok salta la marca de sitio hacia
  el segundo 5 (de la izquierda, a media altura, a abajo a la derecha): en el salto se
  desenfocan las dos unas décimas.
- **Música demasiado alta**: el render ponía todas las canciones al mismo volumen (0,25), pero
  vienen grabadas de -19 a -6 LUFS. `ciencia_01` (-9) sonaba unos 6 dB por encima de la de 010.
  Ahora `musica.sonoridad` lleva la mediana de la canción a un valor fijo antes del volumen
  (-16 en la plantilla, solo en recetas nuevas; las antiguas salen igual). Se cambió además a
  una canción más seria (`misterio_02`, a -17).
- **Efectos parecidos y seguidos**: un riser al terminar «¿Por qué?» y un whoosh al terminar
  «bañera», con el respiro en medio. Se dejaron solo dos y distintos: `whoosh_01` en el paso de
  la lluvia a la playa y `whoosh_02` entrando en el respiro (como en 013).
- **Costa con edificios**: tres clips de pueblos de Liguria y Amalfi (y uno de Barcelona desde
  el aire) no quedaban bien; se marcaron como `descartado` y se bajaron dos de mar sin edificios.
- **Subtítulos**: «el mar te pareció» salió «el martes pareció» (una palabra oída por dos del
  guion que, juntas, suenan igual: ahora se corrige); «siete por ciento» contaba «ciento» como
  parte del número (700) y cambiaba un «7 %» bien oído dejando el «%» suelto; y el «%» caía en
  el subtítulo siguiente («CARGAR UN 7» / «% MÁS DE»): ahora va pegado a su cifra.
- **`revisar_publicacion.py`**: no encontraba `lluvia_cataluña-003` en el índice. macOS escribe
  la «ñ» de los nombres de archivo como «n» + tilde aparte (NFD), y el guion como una sola letra
  (NFC): se ven iguales pero no lo son. Ahora se comparan normalizados. Además daba por buenas
  las licencias desconocidas («falta», los clips de TikTok): ahora las avisa.

**Comprobación**: 004-elefante sigue dando la misma lista de cortes con semilla (`0228c49c…`) y
el mismo fondo (`d9c21707…`); la configuración fusionada solo cambia por `musica.sonoridad: null`.

## Short 015-mono_aullador: sonido original, negro, zoom hacia un punto y carrusel

Short con material propio grabado en Costa Rica, con un montaje pedido al detalle: empieza con
3 s del aullador con su sonido, carrusel rápido de otros animales, 6 s de la manada a todo
volumen, «El mono aullador» con la pantalla en negro, la foto del aullador dormido con un zoom
lento hacia él y un bonk, la explicación y 7 s finales del aullador. La fábrica no sabía hacer
casi nada de eso, así que se añadió:

- **`[sonido clip desde largo]`**: el clip con su audio. Funciona como un respiro (se inserta
  ese silencio en la voz, así que subtítulos, cortes y efectos se desplazan solos), pero el
  hueco lo ocupa su clip y el render pone su audio, igualado a `sonidos.sonoridad` (la manada
  venía a -30 LUFS), con la música apagada. Puede ir al principio o al final del guion.
- **`negro`**: un clip sin archivo que `generar_fondo` dibuja.
- **`video.imagen.acercar`**: la foto se acerca hacia un punto, no al centro.
- **Efectos `al_empezar`**: el bonk suena cuando entra la foto, no al acabar la palabra.
- **Carrusel**: un plano corto (3 s o menos) puede recortarse hasta 0,5 s si se pisa con el
  siguiente; antes, por debajo de 2 s era error.
- **Hoja para leer**: `[sonido]` sale en gris, como un respiro.
- **Prueba sin grabación**: antes de grabar se simuló la transcripción con las palabras del
  guion (una cada 0,37 s) para ver la lista de cortes. Salieron dos fallos: el carrusel daba
  error (de ahí el recorte hasta 0,5 s) y la foto del aullador dormido duraba 2,6 s en vez de
  unos 5 (el plano siguiente se movió).
- **Fotos de Commons más pequeñas**: las dos del aullador anunciaban 3840 px y llegaron de 2048
  (pendiente de revisar en `fuentes/commons.py`).

- **Fallo con la grabación real**: «hay uno» se dijo en 0,3 s y al plano del murciélago solo
  le quedaba un tercio de segundo: «Se pisan…» y el short paró. Ahora, cuando dos planos de
  carrusel están demasiado juntos, el segundo entra un poco más tarde (y desde más adelante
  en su clip) para que el primero dure al menos 0,5 s. Además había 1,2 s de silencio entre
  el aullido inicial y la primera palabra (lo que se grabó antes de hablar): con un [sonido]
  al principio, ese silencio se quita y la voz entra 0,3 s después del clip.

**Comprobación**: 004-elefante, misma lista de cortes con semilla y mismo fondo (md5).

## Short 016-internet_muerto: texto de portada y música sincronizada a una palabra

- **Rigor en un tema delicado**: la teoría (foro anónimo, 2021: internet «murió» en 2016 y alguien
  lo controla) se separa de los datos. Todas las cifras de tráfico salen de empresas que venden
  protección contra bots (Imperva, Cloudflare) y dependen de qué se mide: en 2025, el 53 % de las
  peticiones de páginas fueron de bots, pero solo el 30 % de todas las peticiones. Ya en 2016
  Imperva daba un 52 %. Por eso el guion dice «visitas a páginas web» y aclara que son programas,
  no gente falsa hablando contigo.
- **Texto de portada**: la promesa en grande desde el primer fotograma, para quien ve el vídeo sin
  sonido (`subtitulos.portada`), en los subtítulos `.ass` con su propio estilo.
- **Música sincronizada**: `techno_02` es «plana» para el análisis (sin subida fuerte), pero rompe
  en su segundo 21,8. Con `musica.sincronizar`, ese segundo cae al empezar «foro», justo cuando
  empieza la teoría, lea como lea el locutor.

## Short 017-elecciones: clip propio .mov, fotos .webp y un logo pegado al borde

- **Imparcialidad**: el motivo de las elecciones va como hechos (qué decretos se rechazaron y
  quién votó en contra) y la postura del Gobierno con sus palabras. Se descartaron dos datos en
  los que los medios no coincidían («el octavo adelanto desde 1978»: unos cuentan siete, otros
  ocho o nueve; «casi ocho meses antes»: unos dicen siete). El dato curioso no culpa a nadie:
  Juan Carlos I vivió 11 elecciones generales en casi 39 años; Felipe VI, 6 en 12.
- **Formatos**: el usuario trajo una grabación de pantalla `.mov` y fotos `.webp`. Convertirlas
  habría sido escribir copias en la biblioteca; ahora `ruta_clip()` acepta esos formatos.
- **Logo sin tapar**: en el clip de Sánchez (320x748), la caja del logo medía 35 px y estaba
  pegada al borde derecho. Los 12 px de difuminado del parche lo dejaban transparente justo ahí.
  Ahora el difuminado es de un cuarto de la caja como mucho y no se aplica hacia el borde de la
  imagen. Se vio ampliando el fotograma de la prueba antes de grabar.
- **Licencias**: las fotos y el clip son del usuario o descargados por él, con licencia «falta»;
  esta vez decidió no tenerlo en cuenta. `revisar_publicacion.py` lo avisa.

## Short 019-huracan_isaias: animaciones generadas por código

- **Qué**: un mapa animado de la trayectoria del huracán Isaias, usado en el guion como un clip
  protagonista más (`[plano huracan_isaias_mapa 0 8]`). Es el primer tipo de un sistema para
  pedir animaciones en otros shorts: una ficha JSON por animación en el short, un módulo por tipo
  en `scripts/animaciones/` y el lanzador `scripts/animar.py`.
- **Datos oficiales**: los shapefiles del Centro Nacional de Huracanes (NHC/NOAA, dominio
  público): la trayectoria real (`best_track`) y la previsión de cada aviso con su cono
  (`forecast/archive/al092026_5day_011.zip`). Verificado con los avisos 1 (formación el 6 de
  octubre en 22,1 N 95,6 O) y 11 (9 de octubre, 04:00 CDT = 11:00 en España, 26,4 N 88,0 O,
  categoría 2). Las tablas de puntos traen la latitud y la longitud redondeadas a grados enteros:
  hay que usar la geometría del shapefile.
- **Mapa**: Natural Earth 50m (dominio público). Proyección Mercator hecha a mano: para un mapa
  regional no hace falta cartopy, que arrastra GEOS y PROJ.
- **Imagen aparte** (`Dockerfile.mapas`, matplotlib + pyshp): el vigilante y `shorts-whisper` no
  cambian. Con 8 GB de RAM, el truco es el *blitting*: el mapa base se dibuja una vez y en cada
  fotograma solo se pintan las piezas que se mueven; los fotogramas van a FFmpeg por una
  tubería, sin PNG en disco. Tarda unos 5 s.
- **Dónde vive**: en `data/animaciones/`, no en `data/biblioteca/` (ahí solo entra lo que trae
  `buscar_clips`). En el índice, tipo `animacion`: como no es `video` ni `imagen`, no entra en el
  relleno. `ruta_clip()` la busca después de vídeos y fotos; comprobado que ninguno de los 196
  clips del índice cambia de ruta.
- **Problemas**: las etiquetas se pisaban (Houston con Nueva Orleans, Atlanta con «PREVISIÓN») y
  «categoría 2 · 175 km/h» se salía por la derecha; el recuadro de «PREVISIÓN» salía antes que su
  texto. Y un corte de 8 s de una animación de 8 s daba 239 fotogramas: el filtro `fps=30` del
  montaje pierde el último de un vídeo cortado hasta su final. Solución: 0,5 s de colchón quieto.
- **Créditos**: los shorts siguen sin créditos; las fuentes quedan en el índice, en pantalla
  («Fuente: NHC/NOAA · Mapa: Natural Earth») y en las fuentes de la publicación.

## Short 020-puente_oresund: un perfil animado como revelación

- **Material**: del puente real solo hay fotos con licencia sin atribución (8, de Commons, en
  dominio público y CC0; la búsqueda por categoría no daba nada y sí la de texto). Ningún vídeo:
  en Commons son CC BY o BY-SA y Pixabay no tiene ninguno con la etiqueta. Para que el short no
  sea solo de fotos: un vídeo genérico (un avión despegando, solo en «estorbarían a los aviones»)
  y una animación como plano de la revelación.
- **Animación `perfil_enlace`**: el enlace de lado, con las distancias a escala (puente, isla y
  túnel, y las torres donde están: 3.739 m de acceso y 490 m de vano) y las alturas exageradas.
  El coche se hunde bajo el agua porque el agua se dibuja encima de él, semitransparente.
- **Problemas**: la primera versión salía pequeña y con las etiquetas pisadas; se agrandó la
  escala vertical sin bajar el túnel a la zona de los subtítulos y las etiquetas largas pasaron a
  dos líneas. El avión cruzaba por delante de las torres, como si chocara: ahora baja por el lado
  del aeropuerto. `animar.py` escribía en el índice la fuente del huracán para cualquier
  animación: ahora cada módulo devuelve la suya.

## Short 021-voto_correo: una animación larga de servicio público

- **Rigor**: cada paso sale de la LOREG en el BOE (arts. 72, 73 y 88, descargada y leída en local
  porque la web cortaba el texto), de la instrucción 5/2023 de la Junta Electoral Central y de
  Correos. Lo que no estaba claro se quedó fuera: los plazos (los medios no coinciden en el
  último día) y la app MiDNI (un medio la daba por válida, pero la JEC la suspendió el 26 de
  marzo de 2026 y no consta que lo haya levantado). Los casos reales, sin partidos ni nombres:
  Melilla 2008 (condena firme del Supremo, 2021) y Melilla 2023 (en instrucción), y cómo se
  detectó el de 2023: solicitudes anómalas (casi el 20 % del censo) y robos a carteros.
- **Animación `recorrido_pasos`** (45 s, la protagonista): seis tarjetas con su control, el
  resumen y los casos. Para que cada paso salga cuando se dice, cada tramo de 5 s va anclado a
  su frase con un `[plano]` de 3 s («corto»: se puede acortar) y la receta sube
  `relleno_min` a 1,8 s, así los huecos alargan la tarjeta en vez de meter otro vídeo.
- **Material**: lo electoral de Pixabay es de otros países (EE. UU., Francia, India) y no se
  usa en un vídeo sobre España; el relleno son vídeos de España de la biblioteca y una mano
  escribiendo, puestos a mano en la receta.

## Qué he aprendido
[completa con lo que has aprendido en esta fase]
