# deploy — PANAL en fuego

**https://panalforestal.cl**, servido desde `fuego`, el VPS de Linode que
también aloja bozzi.cl, humanalegal.cl, 33bit.cl y el webmail. Se entra por
Tailscale: `ssh fuego`. Hasta el 6-oct-2026 vivía en panal.ninobozzi.cl, que
ahora redirige (ver [Dominio](#dominio)).

Es un sitio estático. No hay build: nginx sirve `web/` directo desde un
clon del repo, y el cron del usuario `nino` reescribe
`web/data/national.json` cada 10 minutos.

```
/var/www/panal.ninobozzi.cl/         clon del repo, dueño nino (ruta del nombre anterior)
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
scp deploy/nginx/panalforestal.cl.conf fuego:panal-setup/nginx/

ssh -t fuego sudo bash panal-setup/setup-root.sh   # dir, certificados, vhost
ssh fuego bash panal-setup/setup-user.sh           # clon, venv, cron
```

`setup-root.sh` corre `nginx -t` antes de recargar y, si falla, desactiva el
vhost nuevo en vez de dejar a nginx con una configuración rota — en ese
servidor viven otros sitios. Antes de certbot revisa que los tres nombres
resuelvan: sin DNS no sigue.

La copia en `~/panal-setup` sirve solo para la primera vez, cuando todavía
no hay clon; después se borra. **De ahí en adelante los scripts se corren
desde el clon**, que es el que se actualiza con `git pull` — correr una
copia vieja reinstala un cron viejo sin avisar (pasó el 2-oct):

```bash
ssh fuego bash /var/www/panal.ninobozzi.cl/deploy/setup-user.sh
```

## Actualizar

```bash
ssh fuego git -C /var/www/panal.ninobozzi.cl pull --ff-only
```

Nada más: no hay build ni servicio que reiniciar. Si el cambio toca el
horario del cron, correr además `setup-user.sh` desde el clon.

Si el cambio toca `deploy/nginx/` o `deploy/setup-root.sh`, correr además
la parte de root desde el clon:

```bash
ssh -t fuego sudo bash /var/www/panal.ninobozzi.cl/deploy/setup-root.sh
```

## Revisar que siga vivo

```bash
ssh fuego tail -8 /var/www/panal.ninobozzi.cl/data/cron_national.log
curl -s https://panalforestal.cl/data/national.json | head -c 120
```

## Dominio

`panalforestal.cl` está en NIC Chile, con los DNS delegados a Linode
(`ns1.linode.com` … `ns5.linode.com`), igual que bozzi.cl y los demás
dominios de fuego. Los registros, en la zona de Linode:

| nombre | tipo | valor |
|---|---|---|
| `panalforestal.cl` | A | 45.56.125.15 |
| `panalforestal.cl` | AAAA | 2600:3c00::f03c:91ff:fe33:3da3 |
| `www` | A / AAAA | los mismos |

El AAAA importa: Let's Encrypt valida por IPv6 si hay registro, y uno que
apunte a otro lado hace fallar el certificado aunque el A esté bien.

**panal.ninobozzi.cl** (la dirección del 2 al 6-oct) responde todo con un
301 a la misma ruta en panalforestal.cl, salvo `/sw.js`. Ese entrega
[`sw-retired.js`](sw-retired.js), que retira la app instalada con el nombre
anterior: sin él, su service worker seguiría mostrando el último dato que
tuvo, para siempre — el porqué está en la conf. Quien la tenga instalada la
verá abrirse en panalforestal.cl y tendrá que instalarla de nuevo desde ahí.

Las visitas al nombre anterior quedan en un log aparte. Cuando deje de
recibir algo más que bots, se puede apagar:

```bash
ssh -t fuego "sudo grep -v -i bot /var/log/nginx/panal-old.access.log | tail"
```

Volver atrás: el vhost anterior quedó en `sites-available`, desactivado.

```bash
ssh -t fuego 'sudo ln -s /etc/nginx/sites-available/panal.ninobozzi.cl /etc/nginx/sites-enabled/ \
  && sudo rm /etc/nginx/sites-enabled/panalforestal.cl \
  && sudo nginx -t && sudo systemctl reload nginx'
```

## Memoria

`fuego` tiene 3,8 GB, con la swap llena por fail2ban y Suricata. Antes del
deploy el build nacional llegaba a 1,5 GB de pico; ahora son ~270 MB (ver
los commits `fix(goes)` y `fix(viirs)`). Si vuelve a crecer, medirlo con:

```bash
/usr/bin/time -v .venv/bin/python ingest/scripts/build_national.py -o /tmp/n.json 2>&1 | grep Maximum
```
