# Imagen base: Ubuntu 24.04
FROM ubuntu:24.04

# Instalar FFmpeg y limpiar la caché de apt para que la imagen pese menos
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg  fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Carpeta de trabajo dentro del contenedor
WORKDIR /data

# Comando por defecto al arrancar: una terminal bash
CMD ["bash"]
