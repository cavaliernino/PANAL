#!/bin/bash
# La parte sin sudo del deploy en fuego, como el usuario nino. Después de
# setup-root.sh:
#
#   ssh fuego bash ~/panal-setup/setup-user.sh
#
# Clona el repo, arma un venv solo con lo que usa el build nacional, genera
# el primer snapshot e instala el cron. Idempotente.

set -euo pipefail

DIR=/var/www/panal.ninobozzi.cl
REPO=https://github.com/cavaliernino/PANAL.git
# Un minuto después de :x0, no en :x0 — NOAA publica cada barrido 6-10 s
# después. Ver el comentario de cron_national.sh.
CRON="1-59/10 * * * * $DIR/ingest/scripts/cron_national.sh"

[ -w "$DIR" ] || { echo "$DIR no existe o no es escribible: correr setup-root.sh primero" >&2; exit 1; }

echo "1/4 repo"
if [ -d "$DIR/.git" ]; then
    git -C "$DIR" pull --ff-only
else
    git clone "$REPO" "$DIR"
fi

echo "2/4 venv"
# Solo lo que importa build_national.py. El resto de ingest (rasterio, censo,
# OSM) no corre acá, y el disco de este servidor no sobra.
[ -x "$DIR/.venv/bin/python" ] || python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install -q --upgrade pip
"$DIR/.venv/bin/pip" install -q "numpy>=1.26" "pandas>=2.2" "netCDF4>=1.7" "h3>=4.1"

echo "3/4 primer snapshot"
"$DIR/ingest/scripts/cron_national.sh"
tail -6 "$DIR/data/cron_national.log"
[ -s "$DIR/web/data/national.json" ] || { echo "no se generó national.json" >&2; exit 1; }

echo "4/4 cron"
MARK="# PANAL — snapshot nacional, cadencia de GOES"
# Reemplaza la línea si ya estaba; deja intacto el resto del crontab.
{ crontab -l 2>/dev/null | grep -vF "$DIR/ingest/scripts/cron_national.sh" \
                         | grep -vxF "$MARK" || true
  echo "$MARK"
  echo "$CRON"
} | crontab -
crontab -l | grep -F "$DIR"
echo "listo"
