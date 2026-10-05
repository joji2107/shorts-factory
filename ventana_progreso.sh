#!/bin/bash
# Ventana de progreso: vigila data/estado/progreso.json (lo escribe el vigilante) y, en el Mac:
# - al empezar un short, abre la página de progreso (data/estado/progreso.html);
# - si falla, avisa con una notificación (la página dice qué ha pasado y qué hacer);
# - cuando está listo, abre el vídeo.
# El vigilante corre en Docker y no puede abrir ventanas en el Mac: por eso hace falta este
# script. Lo arranca arrancar.sh en segundo plano y lo para apagar.sh.
#
# Uso: ./ventana_progreso.sh   (normalmente no hace falta: lo lanza arrancar.sh)

set -u
cd "$(dirname "$0")" || exit 1

ESTADO=data/estado/progreso.json
PAGINA=data/estado/progreso.html

leer() {    # un campo del JSON (plutil viene con macOS y entiende JSON)
    plutil -extract "$1" raw -o - "$ESTADO" 2>/dev/null
}

avisar() {  # notificación de macOS
    osascript -e "display notification \"$1\" with title \"Fábrica de shorts\" sound name \"$2\"" >/dev/null 2>&1
}

# Lo que hay al arrancar ya es viejo: solo se reacciona a cambios desde ahora
anterior=""
[ -f "$ESTADO" ] && anterior="$(leer short)|$(leer inicio)|$(leer estado)"

while true; do
    if [ -f "$ESTADO" ]; then
        actual="$(leer short)|$(leer inicio)|$(leer estado)"
        if [ "$actual" != "$anterior" ]; then
            short=$(leer short)
            case "$(leer estado)" in
                procesando)
                    # Solo al empezar un short (no en cada paso)
                    [ "${actual%|*}" != "${anterior%|*}" ] && open "$PAGINA"
                    ;;
                listo)
                    avisar "$short está listo" "Glass"
                    open "$(leer video)"
                    ;;
                error)
                    avisar "Ha fallado $short: mira la ventana de progreso" "Basso"
                    open "$PAGINA"
                    ;;
            esac
            anterior=$actual
        fi
    fi
    sleep 2
done
