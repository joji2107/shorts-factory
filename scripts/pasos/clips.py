"""Clips de la biblioteca: vídeos (data/biblioteca/video/<clip>.mp4) y fotos
(data/biblioteca/imagen/<clip>.jpg).

Una foto se trata como un "vídeo virtual" de video.imagen.segundos: un movimiento lento
y continuo sobre toda la foto (efecto Ken Burns). Un corte "foto inicio largo" toma ese
tramo del movimiento, igual que en un vídeo. Así el reparto, desplazar(), los [plano] y
las hojas de fotogramas funcionan sin cambios, y dos cortes de la misma foto enseñan
partes distintas.

Movimiento, según la forma de la foto:
- más ancha que 3:4: desplazamiento lateral (crop con la posición en función de n, el
  número de fotograma), como mucho un ancho de pantalla en todo el vídeo virtual;
- vertical o casi cuadrada: zoom suave de 1,00 a 1,12 hacia el centro (zoompan).
La velocidad (video.imagen.velocidad, o la de la foto en video.imagen.por_foto) multiplica
el recorrido y el zoom, no la duración: con 2 la foto se mueve el doble en los mismos
segundos, y el material que da (para el reparto y evaluar_material) no cambia. El
desplazamiento no puede pasar del borde de la foto: en una foto poco ancha, la velocidad
real se queda por debajo de la pedida.
Se calcula a 2160x3840 y se reduce a 1080x1920: así el movimiento lento no tiembla
(crop y zoompan redondean a píxeles enteros). El sentido (izquierda o derecha, acercar
o alejar) sale del nombre del archivo, así que dos renders dan el mismo vídeo.
"""
import hashlib
import json

from .utilidades import duracion, ejecutar

FPS = 30
ZOOM = 0.12              # el zoom pasa de 1,00 a 1 + ZOOM a lo largo del vídeo virtual
PANEO_MAX = 1.0          # recorrido máximo del desplazamiento, en anchos de pantalla
FORMA_PANEO = 3 / 4      # fotos más anchas que esto se desplazan; las demás, zoom
NEGRO = "negro"          # clip especial: pantalla en negro ([plano negro 0 2]), sin archivo
# Formatos que se aceptan tal cual (017: una grabación de pantalla .mov y fotos .webp): así no
# hace falta convertirlos, que sería escribir copias nuevas en la biblioteca
EXT_VIDEO = (".mp4", ".mov")
EXT_FOTO = (".jpg", ".jpeg", ".png", ".webp")


def ruta_clip(biblioteca, clip):
    """El archivo de un clip: el vídeo si está, si no la foto. biblioteca es
    data/biblioteca/video; las fotos están en data/biblioteca/imagen. El clip "negro" no
    tiene archivo: devuelve una ruta que no existe y generar_fondo lo dibuja."""
    if clip == NEGRO:
        return biblioteca / NEGRO
    for extension in EXT_VIDEO:
        if (biblioteca / f"{clip}{extension}").is_file():
            return biblioteca / f"{clip}{extension}"
    for extension in EXT_FOTO:
        if (biblioteca.parent / "imagen" / f"{clip}{extension}").is_file():
            return biblioteca.parent / "imagen" / f"{clip}{extension}"
    raise RuntimeError(f"El clip {clip} no está en data/biblioteca/video ni en data/biblioteca/imagen")


def es_foto(ruta):
    return ruta.suffix.lower() in EXT_FOTO


def existe_clip(biblioteca, clip):
    """True si el clip tiene archivo (vídeo o foto, en cualquiera de los formatos aceptados)."""
    try:
        return clip == NEGRO or ruta_clip(biblioteca, clip).is_file()
    except RuntimeError:
        return False


def duracion_clip(biblioteca, clip, segundos_imagen):
    """Segundos de un clip: los del vídeo, o los del vídeo virtual de una foto."""
    if clip == NEGRO:
        return 3600.0
    ruta = ruta_clip(biblioteca, clip)
    return float(segundos_imagen) if es_foto(ruta) else duracion(ruta)


def medidas(foto):
    """Ancho y alto de una foto, en píxeles."""
    resultado = ejecutar(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "stream=width,height", "-of", "csv=p=0", foto])
    ancho, alto = resultado.stdout.strip().split(",")[:2]
    return int(ancho), int(alto)


def velocidad_foto(foto, imagen):
    """La velocidad de una foto: la suya en video.imagen.por_foto, o la general."""
    return float(imagen.get("por_foto", {}).get(foto.stem, imagen.get("velocidad", 1.0)))


def filtro_foto(foto, inicio, imagen):
    """Filtro de FFmpeg que convierte la foto (entrada con -loop 1) en el tramo del vídeo
    virtual que empieza en 'inicio'. imagen es video.imagen de la configuración. El avance
    p va de 0 a 1 a lo largo de imagen["segundos"].
    Con video.imagen.acercar {foto: [x, y]} (015: el aullador dormido), la foto siempre se
    acerca, hacia ese punto (de 0 a 1, desde arriba a la izquierda), aunque sea ancha."""
    ancho, alto = medidas(foto)
    sentido = int(hashlib.md5(foto.stem.encode()).hexdigest(), 16) % 2
    total = max(1, round(imagen["segundos"] * FPS))
    velocidad = velocidad_foto(foto, imagen)
    punto = imagen.get("acercar", {}).get(foto.stem)

    def avance(fotograma):
        """p con la variable de FFmpeg que cuenta fotogramas (n en crop, on en zoompan)."""
        p = f"min(1,({round(inicio * FPS)}+{fotograma})/{total})"
        return p if sentido else f"(1-{p})"

    if punto:
        # La ventana de 2160x3840 se centra en el punto (sin salirse de la foto) y el zoom
        # va hacia donde queda el punto dentro de ella
        x, y = punto
        escala = max(2160 / ancho, 3840 / alto)
        w, h = ancho * escala, alto * escala
        cx = min(max(0.0, x * w - 1080), w - 2160)
        cy = min(max(0.0, y * h - 1920), h - 3840)
        qx, qy = (x * w - cx) / 2160, (y * h - cy) / 3840
        p = f"min(1,({round(inicio * FPS)}+on)/{total})"
        return (f"scale={round(w / 2) * 2}:{round(h / 2) * 2},crop=2160:3840:{cx:.0f}:{cy:.0f},"
                f"zoompan=z='1+{ZOOM * velocidad:g}*{p}':"
                f"x='max(0,min(iw-iw/zoom,{qx:.4f}*iw-iw/zoom/2))':"
                f"y='max(0,min(ih-ih/zoom,{qy:.4f}*ih-ih/zoom/2))':"
                "d=1:s=2160x3840:fps=30,"
                "scale=1080:1920,setsar=1,format=yuv420p")
    if ancho / alto > FORMA_PANEO:
        # Desplazamiento: la foto a 3840 de alto y una ventana de 2160 que la recorre
        # (centrado si la foto es muy ancha: como mucho PANEO_MAX pantallas de recorrido)
        ancho_escalado = max(2160, round(ancho * 3840 / alto / 2) * 2)
        recorrido = min(ancho_escalado - 2160, round(PANEO_MAX * velocidad * 2160))
        margen = (ancho_escalado - 2160 - recorrido) / 2
        return (f"scale={ancho_escalado}:3840,"
                f"crop=2160:3840:x='{margen:.1f}+{recorrido}*{avance('n')}':y=0,"
                "scale=1080:1920,fps=30,setsar=1,format=yuv420p")
    # Zoom: la foto cubre 2160x3840 y zoompan acerca (o aleja) hacia el centro
    return ("scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
            f"zoompan=z='1+{ZOOM * velocidad:g}*{avance('on')}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':"
            "d=1:s=2160x3840:fps=30,"
            "scale=1080:1920,setsar=1,format=yuv420p")


def marcas_de_agua(raiz):
    """biblioteca/marcas.json ({} si no existe): las marcas de agua de cada clip, para
    desenfocarlas. {clip: [{"caja": [x, y, ancho, alto], "desde": s, "hasta": s}]}, con la
    caja en fracciones del fotograma del clip (de 0 a 1, desde arriba a la izquierda) y los
    segundos del clip en que se ve ("hasta" puede faltar: hasta el final). Es local, como
    musica.json: los clips de TikTok (010, 014) llevan su marca, que salta de sitio."""
    ruta = raiz / "biblioteca" / "marcas.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def filtro_marcas(cajas, inicio, largo):
    """Parte de filtro (antes del encuadre) que desenfoca las marcas de agua que se ven en el
    corte [inicio, inicio + largo] del clip, con los bordes difuminados para que el parche
    no se note. "" si no hay ninguna. Con -ss antes de -i, t empieza en 0 en 'inicio'."""
    partes, n = [], 0
    for marca in cajas:
        desde = marca.get("desde", 0) - inicio
        hasta = (marca["hasta"] - inicio) if marca.get("hasta") is not None else largo + 1
        if hasta <= 0 or desde >= largo:
            continue
        x, y, ancho, alto = marca["caja"]
        # Alfa que sube de 0 a 255 en los bordes de la caja, como mucho 12 px o un cuarto de su
        # lado (comillas: la expresión lleva comas). Hacia el borde de la imagen no se difumina:
        # en 017 el logo estaba pegado al borde de un vídeo de 320 px y el parche, de 35 px, era
        # transparente justo ahí
        lejos = "100000"
        distancias = [lejos if x <= 0.001 else "X", lejos if x + ancho >= 0.999 else "W-1-X",
                      lejos if y <= 0.001 else "Y", lejos if y + alto >= 0.999 else "H-1-Y"]
        alfa = (f"255*min(1,min(min({distancias[0]},{distancias[1]}),min({distancias[2]},{distancias[3]}))"
                "/max(1,min(12,min(W,H)/4)))")
        partes.append(
            f"[v{n}]split[base{n}][m{n}];"
            f"[m{n}]crop=iw*{ancho}:ih*{alto}:iw*{x}:ih*{y},gblur=sigma=16,format=yuva420p,"
            f"geq=lum='p(X,Y)':cb='cb(X,Y)':cr='cr(X,Y)':a='{alfa}'[b{n}];"
            f"[base{n}][b{n}]overlay=main_w*{x}:main_h*{y}:enable='between(t,{max(0, desde):.3f},{hasta:.3f})'"
            f"[v{n + 1}];")
        n += 1
    if not partes:
        return ""
    return "null[v0];" + "".join(partes) + f"[v{n}]"


def en_pantalla(x, y, ancho, alto, encuadre):
    """Dónde cae en la pantalla vertical (1080x1920) el punto (x, y) de un clip de ancho x alto
    (x e y de 0 a 1, desde arriba a la izquierda), según el encuadre de montaje.py:
    - "desenfocado": el clip a 1080 de ancho, centrado en vertical (el fondo desenfocado no cuenta);
    - "relleno": el clip agrandado hasta cubrir la pantalla y recortado por el centro."""
    if encuadre == "desenfocado":
        alto_pantalla = 1080 * alto / ancho
        return x * 1080, (1920 - alto_pantalla) / 2 + y * alto_pantalla
    escala = max(1080 / ancho, 1920 / alto)
    return x * ancho * escala - (ancho * escala - 1080) / 2, y * alto * escala - (alto * escala - 1920) / 2
