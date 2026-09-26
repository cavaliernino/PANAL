# Estado del proyecto

Dónde estamos, qué está bloqueado y qué se olvida si nadie lo anota.

Este documento existe para que el estado no viva en la memoria de nadie. Si
pasan tres semanas sin tocar el repo, esto es lo primero que hay que leer.

**Última actualización:** 2026-09-26

---

## En una línea

Fases 0 y 1 cerradas. Fase 2 construida entera y **validada a medias**: la
mitad de amenaza da 3,83× el azar, la mitad de consecuencia no tiene forma de
validarse sin datos de CONAF.

---

## Lo que corre solo ahora mismo

| qué | dónde | cada cuánto |
|---|---|---|
| Snapshot nacional de detección | cron del sistema | 10 min |
| Log del cron | `data/cron_national.log` | se trunca a 1 MB |

```bash
tail -20 /Users/nino/Dev/PANAL/data/cron_national.log   # ¿sigue vivo?
crontab -l                                              # ¿sigue instalado?
```

El servidor web **no** corre solo. Para las reuniones:

```bash
cd /Users/nino/Dev/PANAL
nohup python3 -m http.server 8000 --directory web > /tmp/panal_web.log 2>&1 &
```

---

## Bloqueado, esperando a terceros

Todo esto está en [`alianzas.md`](alianzas.md) con el detalle de qué pedir y
por qué. Resumen de qué destraba cada cosa:

| pedido | destraba |
|---|---|
| Registros de daño feb-2024 | cerrar Fase 2 — validar la mitad de consecuencia |
| Catastro vegetacional CONAF | Fase 4 completa — sin tipo de combustible no corre C2F+K |
| Acceso a torres de vigía | capa de detección T1, la más rápida que existe |
| Waze vía organismo público | tráfico en vivo durante evacuaciones |

**Nada de esto cuesta dinero.** Las cuatro cosas ya existen; el problema es
que no hay vía automatizable.

---

## Vence o se pudre

| qué | cuándo | consecuencia si se pasa |
|---|---|---|
| **Token de GitHub** | ~22-oct-2026 | no se puede pushear; hay que regenerarlo con `Contents: Read and write` |
| Máscara de anomalías industriales | cada temporada | las faenas abren y cierran; una máscara vieja falla en ambas direcciones |
| Cartografía censal | Censo 2026-27 | — |
| Combustible Sentinel-2 | cada temporada seca | una escena de julio describe un paisaje que no existe en enero |

Regenerar la máscara:

```bash
cd ingest && set -a && . ../.env && set +a
../.venv/bin/python scripts/build_anomaly_mask.py --months 12
```

---

## Decisiones tomadas que conviene no re-discutir

Están argumentadas en los módulos y el roadmap. Acá solo el veredicto, para
no volver a abrir cada una:

- **No se reescribió el historial de git** para borrar la API key de 2020. Se
  revocó, que es el arreglo real. El historial es el registro.
- **El boundary provisional se queda.** La capa "oficial" del INE en ArcGIS
  pone Rapa Nui e Isla Juan Fernández como *insertos cartográficos* al lado
  del continente. Hay un test que impide adoptarla por error.
- **La máscara industrial marca, nunca borra.** Un incendio real puede
  empezar en una faena.
- **PANAL no emite alertas de evacuación.** Eso es SENAPRED vía SAE. El canal
  de Fase 5 lo convierte en diseño en vez de limitación.
- **Negro = área quemada**, nunca evacuación. En operaciones forestales "el
  negro" es zona de seguridad.
- **Sin observación ≠ sin peligro.** Aplica a celdas sin detección, a
  combustible no observado, a caminos no mapeados y a barridos omitidos. Si
  aparece un caso nuevo, la regla ya está decidida.
- **La amenaza no tiene parámetros libres.** 115 celdas de un evento; con
  perillas uno se ajusta al incendio y cree que funciona.

---

## Lo que sé que está mal y no arreglé

- **GLO-30 es modelo de superficie, no terreno.** Mitigado con suavizado 3×3,
  pero para Fase 4 hace falta FABDEM — Cell2Fire necesita pendiente real.
- **La búsqueda de escenas Sentinel-2 ordena por nubes, no por cobertura.**
  Deja 9,6% de celdas sin combustible en Valparaíso. Esas quedan sin ranking,
  que es correcto, pero la selección se puede mejorar.
- **El bbox de una región con islas es enorme.** Valparaíso llega a Rapa Nui
  (-109°), así que búsquedas por bbox barren el Pacífico. Mitigado donde
  importa, no en general.
- **La consecuencia carga los pesos mayores y cero evidencia.**

---

## Si retomás esto después de un mes

1. `tail -20 data/cron_national.log` — ¿la cadena sigue viva?
2. `git log --oneline -10` — qué pasó al final
3. Leer este archivo y [`alianzas.md`](alianzas.md)
4. `cd ingest && ../.venv/bin/python -m pytest tests -q` — 74 tests
5. `cd engine && ../.venv/bin/python -m pytest tests -q` — 16 tests

Si algún test falla, empezá por ahí: están escritos para fijar decisiones, no
solo para pasar.

---

## Contexto que no hay que olvidar

**SENAPRED ya tiene un visor público** — [Visor Chile
Preparado](https://www.visorchilepreparado.cl). No es competencia: su capa de
incendio es recurrencia histórica 2020-2024, PANAL mide condición actual.
Correlación de rangos 0,145. Detalle y encuadre para la reunión en
[`alianzas.md`](alianzas.md).

Sus 22 capas son ArcGIS público en `services5.arcgis.com/i7S5PSnIJAUcWvSE`.
Dos sin consumir todavía y que deberíamos:

- `Amenaza_por_Incendio_Forestal_2024` — recurrencia; el "historial de
  incendios" que el roadmap listaba para Fase 2 y nunca construí
- `Servicios_2024` capa BOMBEROS — cuarteles; tiempo de respuesta es un
  término de consecuencia que falta

---

## Lo siguiente, según qué llegue primero

| si llega | se construye |
|---|---|
| Datos de daño | validar consecuencia → **cierra Fase 2** |
| Catastro CONAF | tipo de combustible → **arranca Fase 4** |
| Acceso a torres | consola de despacho → **arranca Fase 3** |
| Nada todavía | desplegar en GitHub Pages; extender el índice al resto del país |
