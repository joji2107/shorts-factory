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

from .utilidades import duracion, ejecutar

FPS = 30
ZOOM = 0.12              # el zoom pasa de 1,00 a 1 + ZOOM a lo largo del vídeo virtual
PANEO_MAX = 1.0          # recorrido máximo del desplazamiento, en anchos de pantalla
FORMA_PANEO = 3 / 4      # fotos más anchas que esto se desplazan; las demás, zoom


def ruta_clip(biblioteca, clip):
    """El archivo de un clip: el vídeo si está, si no la foto. biblioteca es
    data/biblioteca/video; las fotos están en data/biblioteca/imagen."""
    video = biblioteca / f"{clip}.mp4"
    if video.is_file():
        return video
    foto = biblioteca.parent / "imagen" / f"{clip}.jpg"
    if foto.is_file():
        return foto
    raise RuntimeError(f"El clip {clip} no está en data/biblioteca/video ni en data/biblioteca/imagen")


def es_foto(ruta):
    return ruta.suffix.lower() == ".jpg"


def duracion_clip(biblioteca, clip, segundos_imagen):
    """Segundos de un clip: los del vídeo, o los del vídeo virtual de una foto."""
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
    p va de 0 a 1 a lo largo de imagen["segundos"]."""
    ancho, alto = medidas(foto)
    sentido = int(hashlib.md5(foto.stem.encode()).hexdigest(), 16) % 2
    total = max(1, round(imagen["segundos"] * FPS))
    velocidad = velocidad_foto(foto, imagen)

    def avance(fotograma):
        """p con la variable de FFmpeg que cuenta fotogramas (n en crop, on en zoompan)."""
        p = f"min(1,({round(inicio * FPS)}+{fotograma})/{total})"
        return p if sentido else f"(1-{p})"

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
