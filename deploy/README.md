# deploy — PANAL en fuego

**https://panal.ninobozzi.cl**, servido desde `fuego`, el VPS de Linode que
también aloja bozzi.cl, humanalegal.cl, 33bit.cl y el webmail. Se entra por
Tailscale: `ssh fuego`.

Es un sitio estático. No hay build: nginx sirve `web/` directo desde un
clon del repo, y el cron del usuario `nino` reescribe
`web/data/national.json` cada 10 minutos.

```
/var/www/panal.ninobozzi.cl/         clon del repo, dueño nino
  web/                               lo único que nginx sirve
  web/data/national.json             lo escribe el cron, no está en git
  .venv/                             numpy, pandas, netCDF4, h3 — nada más
  data/cron_national.log             log del cron, se trunca a 1 MB
```

## Por qué un VPS y no GitHub Pages

- **El cron corre al lado de lo que se sirve.** En Pages el snapshot
  tendría que llegar por commits cada 10 minutos, o por una Action.
- **La Fase 3 necesita servidor de todas formas.** Los reportes que suben
  los teléfonos tienen que llegar a algún lado, y Pages no recibe nada.

## Instalación (una vez)

Dos partes, porque sudo pide contraseña y no se puede automatizar:

```bash
# desde el Mac
ssh fuego mkdir -p panal-setup/nginx
scp deploy/setup-root.sh deploy/setup-user.sh fuego:panal-setup/
scp deploy/nginx/panal.ninobozzi.cl.conf fuego:panal-setup/nginx/

ssh -t fuego sudo bash panal-setup/setup-root.sh   # dir, certificado, vhost
ssh fuego bash panal-setup/setup-user.sh           # clon, venv, cron
```

`setup-root.sh` corre `nginx -t` antes de recargar y, si falla, desactiva el
vhost nuevo en vez de dejar a nginx con una configuración rota — en ese
servidor viven otros sitios.

## Actualizar

```bash
ssh fuego git -C /var/www/panal.ninobozzi.cl pull --ff-only
```

Nada más: no hay build ni servicio que reiniciar.

## Revisar que siga vivo

```bash
ssh fuego tail -8 /var/www/panal.ninobozzi.cl/data/cron_national.log
curl -s https://panal.ninobozzi.cl/data/national.json | head -c 120
```

## Memoria

`fuego` tiene 3,8 GB, con la swap llena por fail2ban y Suricata. Antes del
deploy el build nacional llegaba a 1,5 GB de pico; ahora son ~270 MB (ver
los commits `fix(goes)` y `fix(viirs)`). Si vuelve a crecer, medirlo con:

```bash
/usr/bin/time -v .venv/bin/python ingest/scripts/build_national.py -o /tmp/n.json 2>&1 | grep Maximum
```
