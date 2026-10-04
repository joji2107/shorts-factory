#!/bin/bash
# Apaga el sistema al terminar el día: comprueba que no queda trabajo a medias, para el
# vigilante con SIGINT y apaga Colima. Se puede ejecutar varias veces.
#
# Uso: ./apagar.sh
# (REGISTRO=<archivo> ./apagar.sh lee otro registro: sirve para probar la comprobación)

set -u                      # error si se usa una variable sin definir (sin -e: las
                            # comprobaciones que fallan a propósito las decide el script)
cd "$(dirname "$0")" || exit 1   # la raíz del proyecto, se lance desde donde se lance

REGISTRO="${REGISTRO:-data/registro.log}"

vigilante_en_marcha() {
    [ -n "$(docker ps -q --filter 'name=^vigilante$' 2>/dev/null)" ]
}

aviso_git() {
    # Solo avisa: apagar no pierde los cambios, pero conviene saberlo
    cambios=$(git status --short)
    if [ -n "$cambios" ]; then
        echo "AVISO: tienes $(echo "$cambios" | wc -l | tr -d ' ') archivo(s) sin guardar en Git" \
             "(rama $(git branch --show-current)):"
        echo "$cambios" | sed 's/^/  /'
    fi
}

# 1. ¿Hay algo que apagar?
if ! colima status >/dev/null 2>&1; then
    echo "Colima ya está parado: no hay nada que apagar."
    aviso_git
    exit 0
fi

# 2. La bandeja tiene que estar vacía (mismas extensiones que el vigilante; también los
#    archivos de 0 bytes, que esperan a tener contenido)
pendientes=$(find data/bandeja -maxdepth 1 -type f \( -iname '*.wav' -o -iname '*.mp3' -o -iname '*.m4a' \
             -o -iname '*.aif' -o -iname '*.aiff' \) 2>/dev/null)
if [ -n "$pendientes" ]; then
    echo "NO SE APAGA: hay audios en la bandeja esperando al vigilante:"
    echo "$pendientes" | sed 's/^/  /'
    echo "Espera a que los procese o sácalos de data/bandeja/ y vuelve a ejecutar ./apagar.sh"
    exit 1
fi

# 3. Ningún short procesándose: el último "INICIO <short>" del registro sin su "OK" o "ERROR"
#    (un SIGINT a mitad de un short lo cortaría y la grabación se quedaría en archivo/)
if vigilante_en_marcha && [ -f "$REGISTRO" ]; then
    en_marcha=$(awk '
        $3 == "INICIO"                 { nombre = $4; hora = $2; abierto = 1; next }
        $3 == "OK" || $3 == "ERROR"    { x = $4; sub(/:$/, "", x); if (x == nombre) abierto = 0 }
        END                            { if (abierto) print nombre " " hora }
    ' "$REGISTRO")
    if [ -n "$en_marcha" ]; then
        set -- $en_marcha
        echo "NO SE APAGA: $1 se está procesando desde las $2."
        echo "Espera a que acabe (docker logs -f vigilante) y vuelve a ejecutar ./apagar.sh"
        exit 1
    fi
fi

# 4. Aviso de Git (no bloquea)
aviso_git

# 5. Parar el vigilante con SIGINT, como Ctrl+C (docker stop no sirve: Python ignora SIGTERM
#    y Docker lo mataría a los 10 s)
if vigilante_en_marcha; then
    echo "Vigilante: parando..."
    docker kill --signal=SIGINT vigilante >/dev/null
    for _ in $(seq 30); do
        vigilante_en_marcha || break
        sleep 1
    done
    if vigilante_en_marcha; then
        echo "ERROR: el vigilante sigue en marcha después de 30 s; no se apaga Colima."
        echo "Mira qué hace con: docker logs --tail 20 vigilante"
        exit 1
    fi
    echo "Vigilante: parado. Última línea del registro:"
    [ -f "$REGISTRO" ] && tail -n 1 "$REGISTRO" | sed 's/^/  /'
else
    echo "Vigilante: no estaba en marcha"
fi

# 6. Apagar Colima (también para el servidor MCP de Claude Code, si está abierto)
echo "Colima: apagando..."
colima stop || { echo "ERROR: Colima no se ha parado"; exit 1; }
echo
echo "Todo apagado. Si Claude Code sigue abierto, el servidor 'fabrica' se ha desconectado:"
echo "al volver, ./arrancar.sh y /mcp para reconectarlo."
