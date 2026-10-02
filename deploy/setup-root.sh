#!/bin/bash
# La parte de root del deploy en fuego. Se corre una sola vez:
#
#   ssh -t fuego sudo bash ~/panal-setup/setup-root.sh
#
# Crea el directorio, emite el certificado y activa el vhost. Todo lo demás
# (clonar, venv, cron) lo hace el usuario nino sin sudo — ver deploy/README.md.
#
# Es idempotente: correrlo dos veces no rompe nada. Si `nginx -t` falla, saca
# el vhost nuevo y no recarga, para no tumbar los otros sitios del servidor.

set -euo pipefail

DOMAIN=panal.ninobozzi.cl
DIR=/var/www/$DOMAIN
OWNER=nino
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF_SRC="$HERE/nginx/$DOMAIN.conf"
AVAIL=/etc/nginx/sites-available/$DOMAIN
ENABLED=/etc/nginx/sites-enabled/$DOMAIN

[ "$(id -u)" -eq 0 ] || { echo "correr con sudo" >&2; exit 1; }
[ -f "$CONF_SRC" ] || { echo "falta $CONF_SRC" >&2; exit 1; }

echo "1/3 directorio $DIR (dueño $OWNER)"
install -d -o "$OWNER" -g "$OWNER" -m 755 "$DIR"

echo "2/3 certificado para $DOMAIN"
# El vhost por defecto ya sirve /.well-known/acme-challenge/ desde
# /var/www/html para cualquier host sin vhost propio, así que el certificado
# se puede emitir antes de que exista el nuestro.
certbot certonly --webroot -w /var/www/html -d "$DOMAIN" \
    --non-interactive --agree-tos --keep-until-expiring \
    --deploy-hook "systemctl reload nginx"

echo "3/3 vhost nginx"
cp "$CONF_SRC" "$AVAIL"
ln -sf "$AVAIL" "$ENABLED"
if ! nginx -t; then
    rm -f "$ENABLED"
    echo "nginx -t falló: vhost desactivado, nginx NO recargado" >&2
    exit 1
fi
systemctl reload nginx

echo "listo: https://$DOMAIN (vacío hasta que nino clone el repo en $DIR)"
