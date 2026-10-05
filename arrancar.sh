#!/bin/bash
# Arranca el sistema para trabajar: Colima, el vigilante y un resumen del estado.
# Se puede ejecutar varias veces: lo que ya está en marcha no se toca.
#
# Uso: ./arrancar.sh

set -u                      # error si se usa una variable sin definir (sin -e: las
                            # comprobaciones que fallan a propósito las decide el script)
cd "$(dirname "$0")" || exit 1   # la raíz del proyecto, se lance desde donde se lance

REGISTRO="${REGISTRO:-data/registro.log}"

# 1. Colima (la máquina virtual donde corre Docker)
if colima status >/dev/null 2>&1; then
    echo "Colima: ya estaba en marcha"
else
    echo "Colima: arrancando (tarda unos segundos)..."
    colima start || { echo "ERROR: Colima no ha arrancado"; exit 1; }
fi

# 2. Docker responde
if ! docker info >/dev/null 2>&1; then
    echo "ERROR: Docker no responde aunque Colima está en marcha. Prueba 'colima restart'."
    exit 1
fi

# 3. La imagen del vigilante existe
if ! docker image inspect shorts-whisper >/dev/null 2>&1; then
    echo "ERROR: no está la imagen shorts-whisper. Créala con:"
    echo "  docker build -t shorts-ffmpeg ."
    echo "  docker build -f Dockerfile.whisper -t shorts-whisper ."
    exit 1
fi

# 4. El vigilante (contenedor "vigilante" en segundo plano)
if [ -n "$(docker ps -q --filter 'name=^vigilante$')" ]; then
    echo "Vigilante: ya estaba en marcha"
else
    # Un contenedor parado con ese nombre bloquearía el nombre (con --rm no debería quedar)
    if [ -n "$(docker ps -aq --filter 'name=^vigilante$')" ]; then
        docker rm vigilante >/dev/null
    fi
    echo "Vigilante: arrancando..."
    docker run -d --rm --name vigilante -v "$PWD:/proyecto" -e HF_HOME=/proyecto/data/modelos \
        shorts-whisper python /proyecto/scripts/vigilar_bandeja.py --plantilla curiosidades >/dev/null \
        || { echo "ERROR: el vigilante no ha arrancado"; exit 1; }
    sleep 2
    if [ -z "$(docker ps -q --filter 'name=^vigilante$')" ]; then
        echo "ERROR: el vigilante se ha parado nada más arrancar. Últimos mensajes:"
        docker logs vigilante 2>&1 | tail -n 20
        exit 1
    fi
fi

# 4b. Ventana de progreso (en el Mac): abre la página al dejar una grabación en la bandeja,
#     avisa si falla y abre el vídeo al terminar. Se guarda su número de proceso para pararla.
PID_VENTANA=data/estado/ventana.pid
if [ -f "$PID_VENTANA" ] && kill -0 "$(cat "$PID_VENTANA")" 2>/dev/null; then
    echo "Ventana de progreso: ya estaba en marcha"
else
    mkdir -p data/estado
    nohup ./ventana_progreso.sh >/dev/null 2>&1 &
    echo $! > "$PID_VENTANA"
    echo "Ventana de progreso: en marcha (se abre sola al dejar una grabación en la bandeja)"
fi

# 5. Estado
echo
echo "================ Estado ================"
colima list 2>/dev/null | sed -n '2p' | awk '{print "Colima:    " $2 " (" $4 " CPU, " $5 " de memoria)"}'
if [ -n "$(docker ps -q --filter 'name=^vigilante$')" ]; then
    echo "Vigilante: en marcha. Últimas líneas del registro:"
    [ -f "$REGISTRO" ] && tail -n 3 "$REGISTRO" | sed 's/^/  /'
else
    echo "Vigilante: PARADO"
fi
audios=$(find data/bandeja -maxdepth 1 -type f \( -iname '*.wav' -o -iname '*.mp3' -o -iname '*.m4a' \
         -o -iname '*.aif' -o -iname '*.aiff' \) 2>/dev/null | wc -l | tr -d ' ')
echo "Bandeja:   $audios audio(s) esperando"
echo "Git:       rama $(git branch --show-current)"
cambios=$(git status --short)
if [ -z "$cambios" ]; then
    echo "           sin cambios sin guardar"
else
    echo "           $(echo "$cambios" | wc -l | tr -d ' ') archivo(s) con cambios sin guardar:"
    echo "$cambios" | sed 's/^/             /'
fi
echo "========================================"

# 6. Recordatorio
echo
echo "Ahora abre Claude Code: claude"
echo "(comprueba que pone '⏸ manual mode on' y, con /mcp, que 'fabrica' está conectado)"
