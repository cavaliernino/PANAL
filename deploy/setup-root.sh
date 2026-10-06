#!/bin/bash
# La parte de root del deploy en fuego:
#
#   ssh -t fuego sudo bash /var/www/panal.ninobozzi.cl/deploy/setup-root.sh
#
# Crea el directorio, emite los certificados y activa el vhost. Todo lo demás
# (clonar, venv, cron) lo hace el usuario nino sin sudo — ver deploy/README.md.
#
# Es idempotente: correrlo dos veces no rompe nada. Si `nginx -t` falla, saca
# el vhost nuevo, repone el que había y no recarga, para no tumbar los otros
# sitios del servidor.

set -euo pipefail

DOMAIN=panalforestal.cl
# La dirección hasta el 6-oct-2026. Ahora solo redirige, pero conserva su
# certificado: la app instalada con ese nombre necesita HTTPS para recibir el
# sw.js que la retira (ver la conf).
OLD=panal.ninobozzi.cl
# El clon se quedó en la ruta del nombre anterior: moverlo obliga a rehacer
# el venv y el cron, y la ruta no la ve nadie.
DIR=/var/www/$OLD
OWNER=nino
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF_SRC="$HERE/nginx/$DOMAIN.conf"
AVAIL=/etc/nginx/sites-available/$DOMAIN
ENABLED=/etc/nginx/sites-enabled/$DOMAIN
# El vhost de antes del cambio de nombre. Se desactiva pero no se borra:
# es la vuelta atrás.
OLD_AVAIL=/etc/nginx/sites-available/$OLD
OLD_ENABLED=/etc/nginx/sites-enabled/$OLD

[ "$(id -u)" -eq 0 ] || { echo "correr con sudo" >&2; exit 1; }
[ -f "$CONF_SRC" ] || { echo "falta $CONF_SRC" >&2; exit 1; }

echo "1/4 directorio $DIR (dueño $OWNER)"
install -d -o "$OWNER" -g "$OWNER" -m 755 "$DIR"

echo "2/4 DNS"
# Antes de certbot: Let's Encrypt limita los intentos fallidos por hora.
for h in "$DOMAIN" "www.$DOMAIN" "$OLD"; do
    getent hosts "$h" >/dev/null \
        || { echo "$h todavía no resuelve: falta el DNS (ver deploy/README.md)" >&2; exit 1; }
done

echo "3/4 certificados"
# El vhost por defecto ya sirve /.well-known/acme-challenge/ desde
# /var/www/html para cualquier host sin vhost propio, así que el certificado
# se puede emitir antes de que exista el nuestro.
certbot certonly --webroot -w /var/www/html \
    --cert-name "$DOMAIN" -d "$DOMAIN" -d "www.$DOMAIN" \
    --non-interactive --agree-tos --keep-until-expiring \
    --deploy-hook "systemctl reload nginx"
certbot certonly --webroot -w /var/www/html -d "$OLD" \
    --non-interactive --agree-tos --keep-until-expiring \
    --deploy-hook "systemctl reload nginx"

echo "4/4 vhost nginx"
cp "$CONF_SRC" "$AVAIL"
ln -sf "$AVAIL" "$ENABLED"
# La conf nueva ya atiende el nombre anterior; con las dos activas chocan
# los server_name y el map.
had_old=0
if [ -L "$OLD_ENABLED" ] || [ -e "$OLD_ENABLED" ]; then
    rm -f "$OLD_ENABLED"
    had_old=1
fi
if ! nginx -t; then
    rm -f "$ENABLED"
    [ "$had_old" -eq 0 ] || ln -s "$OLD_AVAIL" "$OLD_ENABLED"
    echo "nginx -t falló: vhost nuevo desactivado, el anterior repuesto, nginx NO recargado" >&2
    exit 1
fi
systemctl reload nginx

echo "listo: https://$DOMAIN (vacío hasta que nino clone el repo en $DIR)"
