# Estado del proyecto

Dónde estamos, qué está bloqueado y qué se olvida si nadie lo anota.

Este documento existe para que el estado no viva en la memoria de nadie. Si
pasan tres semanas sin tocar el repo, esto es lo primero que hay que leer.

**Última actualización:** 2026-10-05

---

## En una línea

Fases 0 y 1 cerradas. Fase 2 construida entera y **validada a medias, y
menos de lo que se creía**: contra seis incendios, la amenaza supera 1,5×
en dos (Valparaíso 2019 y 2024), queda débil en dos (Biobío 2023 y 2026) y
sin habilidad en dos (Viña 2022, Quilpué 2021). Le falta tipo de
combustible: WorldCover no sirvió como sustituto (pre-registro, 5-oct), así
que queda el Catastro de CONAF. La consecuencia sigue sin forma de
validarse sin datos de CONAF.

---

## Lo que corre solo ahora mismo

**Público en https://panal.ninobozzi.cl** desde el 2-oct, servido desde
`fuego` (VPS Linode, por Tailscale). Detalle en
[`deploy/README.md`](../deploy/README.md).

| qué | dónde | cada cuánto |
|---|---|---|
| Snapshot nacional, el que se publica | cron de `nino` en `fuego` | 10 min |
| Certificado TLS | certbot en `fuego`, recarga nginx solo | ~60 días |
| Aviso si el cron falla o deja de correr | healthchecks.io, por correo a Nino | cada corrida hace ping |

```bash
ssh fuego tail -8 /var/www/panal.ninobozzi.cl/data/cron_national.log  # ¿sigue vivo?
ssh fuego git -C /var/www/panal.ninobozzi.cl pull --ff-only           # publicar lo pusheado
```

El aviso depende de que exista `~/.config/panal/healthcheck_url` en `fuego`
con la URL de ping; sin ese archivo el cron corre igual, pero en silencio.
Un barrido sin GOES ni VIIRS sale con código 2 y cuenta como falla.

El Mac ya no corre nada (cron retirado el 2-oct). Para desarrollar en
local, generar el snapshot a mano — ver [`web/README.md`](../web/README.md).

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
- **El snapshot nacional no se commitea.** Es dato vivo; se genera donde se
  sirve.
- **Se valida con combustible anterior al evento.** Con imágenes posteriores
  el índice ve el paisaje que dejó el incendio. `build_wui.py` registra la
  escena de cada celda y `validate_wui.py` avisa si es posterior.
- **El mapa de exposición es público, marcado como investigación.** El
  5-oct salió de la navegación porque contra seis incendios la amenaza
  acierta con claridad en dos; ese mismo día Nino lo devolvió. Queda con un
  aviso arriba ("en investigación — no es un producto de riesgo") y la
  lista de los seis incendios.
- **Moderación de reportes: puntaje automático, humano decide.** Detalle en
  [`crowdsourcing.md`](crowdsourcing.md#moderation-score-then-queue).

---

## Abierto, esperando decisión

- **Notificaciones "detección cerca de ti".** Técnicamente no dependen de
  nadie, pero rozan la regla de que PANAL no emite alertas. Nino lo está
  pensando; no se construye hasta que decida.

---

## Lo que sé que está mal y no arreglé

- **GLO-30 es modelo de superficie, no terreno.** Mitigado con suavizado 3×3,
  pero para Fase 4 hace falta FABDEM — Cell2Fire necesita pendiente real.
- **El combustible se lee en un solo píxel por celda**, de ~160 m en el
  centro, y entre escenas gana la más seca: el mínimo de varias lecturas
  ruidosas, sesgado hacia abajo. La búsqueda ya se arregló el 5-oct (antes
  tomaba las 40 escenas más nuevas y dejaba 9,6% de celdas sin combustible;
  ahora 0,2%); el muestreo todavía no.
- **El bbox de una región con islas es enorme.** Valparaíso llega a Rapa Nui
  (-109°). El combustible ya busca por cajas de 1°; `senapred.fetch` todavía
  usa el bbox entero.
- **La amenaza no generaliza.** Validada el 5-oct contra seis incendios
  con combustible anterior: Rocuant 2019 2,77×, Quilpué 2021 **0,00×**,
  Viña 2022 **0,67×**, Biobío 2023 1,49×, Viña 2024 3,91×, Ñuble–Biobío
  2026 **1,23×**. Falla donde el fuego corre por
  población densa (en Viña 2022 la interfaz tiene 241 viviendas por celda:
  las casas son el combustible) y por plantaciones (el término de sequedad
  NDMI lee el dosel verde como húmedo). Ninguna fórmula gana en los cuatro;
  lo que falta es **tipo de combustible**. ESA WorldCover se probó como
  sustituto con un pre-registro y dos incendios reservados, y no mejoró
  nada: [`preregistro-combustible.md`](preregistro-combustible.md).
- **Al sur de 50°S GLO-30 cambia el espaciado en longitud** (1,5″ y más) y
  `slope_degrees` supone 1″: la pendiente este-oeste saldría inflada. No
  afecta mientras el índice cubra solo Valparaíso.
- **La consecuencia carga los pesos mayores y cero evidencia.**
- **Un cúmulo VIIRS en Atacama que no es incendio ni faena.** Hacia
  -24,1, -68,77, a 3.000 m. Medido el 2-oct: NDVI 0,015–0,063 en sus 23
  celdas (suelo desnudo, combustible 0); las 80 detecciones de un año, todas
  en la pasada de las 18–19 UTC y ninguna de noche; 12 días en feb–mar y 3
  a fines de septiembre; ~5 MW. Firma de falso positivo térmico diurno, o
  de un proceso que solo opera de día. La máscara industrial no lo marca y
  hace bien: su regla es para fuentes persistentes. Hoy se ve como una
  detección más. Opciones, sin decidir: mostrar el NDVI de la celda en la
  ficha de cada detección, o una segunda clase "anomalía sin combustible",
  marcada y nunca borrada.

---

## Si retomás esto después de un mes

1. `ssh fuego tail -20 /var/www/panal.ninobozzi.cl/data/cron_national.log`
   — ¿la cadena sigue viva?
2. `git log --oneline -10` — qué pasó al final
3. Leer este archivo y [`alianzas.md`](alianzas.md)
4. `cd ingest && ../.venv/bin/python -m pytest tests -q` — 103 tests
5. `cd engine && ../.venv/bin/python -m pytest tests -q` — 21 tests

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
Dos ya se consumen, detrás de `build_wui.py --with-senapred`:

- `Amenaza_por_Incendio_Forestal_2024` — cuenta *incidentes* por km², no área
  quemada: mide dónde **empiezan** los incendios, no dónde corren. Se reporta
  como `ignition` y **nunca se mezcla con la amenaza** — combinarlas bajó el
  lift de 3,83× a 2,78×, y hay un test que impide hacerlo.
- `Servicios_2024` capa BOMBEROS — distancia al cuartel más cercano, dentro
  de consecuencia con peso 0,12.

Dos builds: sin la bandera es lo que PANAL puede publicar hoy sin pedirle
nada a nadie; con ella es lo que se les muestra. El permiso que se pide es
para uso público, no para el análisis.

---

## Lo siguiente, según qué llegue primero

| si llega | se construye |
|---|---|
| Datos de daño | validar consecuencia → **cierra Fase 2** |
| Catastro CONAF | tipo de combustible → **arranca Fase 4** |
| Acceso a torres | consola de despacho → **arranca Fase 3** |
| Nada todavía | ver abajo |

Sin reunión, el orden acordado el 2-oct:

1. ~~**Deploy** en el VPS propio~~ — hecho el 2-oct. Al abrirlo en un
   navegador apareció que la vista nacional **nunca había dibujado un
   hexágono** (faltaba h3-js); arreglado.
2. ~~**PWA y vista web del índice WUI**~~ — hecho el 2-oct:
   https://panal.ninobozzi.cl/wui.html, instalable desde el navegador.
   Regenerado el 5-oct tras corregir tres errores de medición (pendiente en
   bordes de tesela DEM, egreso que contaba vértices de forma, búsqueda de
   escenas): **58 celdas, 10.660 personas** (antes 63 y 12.591), amenaza
   **3,91×** con combustible de enero de 2024. **Falta probarla en un
   teléfono de verdad**: Android de Nino e iPhone de Tami — instalar, abrir
   sin señal, "Cerca de mí".
3. **Medir el error de brújula** antes de cualquier app nativa: el cruce de
   marcaciones depende de ese número y nadie lo ha medido. Desde el 5-oct
   hay una página para eso, https://panal.ninobozzi.cl/brujula.html (fuera
   de la navegación): apuntar la cámara a un faro o una torre conocida, a
   más de 1 km, y marcar. Trae nueve puntos de Viña y Valparaíso tomados de
   OSM, calcula el rumbo de la cámara con la orientación completa del
   teléfono (no con `alpha`, que es el borde de un teléfono acostado) y le
   suma la declinación (+0,71° E). Los datos quedan en el teléfono y se
   exportan como CSV. **Lo que se busca:** el sesgo, la dispersión sin él
   (p50 y p90), y cuánto empeora cerca de metal. Si la p90 pasa de ~5°, el
   cruce de dos marcaciones a 3 km ya tiene un error de cientos de metros, y
   la app nativa tendría que compensarlo o no vale la pena.

Acordado el 5-oct, además:

4. ~~**GOES con ventana de una hora**~~ — hecho el 5-oct. Cada celda trae
   su edad y en cuántos barridos apareció; si el último no la vio, se dibuja
   hueca. Los barridos se guardan en `data/cache/goes_recent/`, así que cada
   corrida baja solo el nuevo (166 MB de pico, como antes).
5. **Tipo de combustible**: ESA WorldCover probado y descartado el 5-oct
   con pre-registro. Queda el Catastro de CONAF. El muestreo (un píxel
   central, gana la más seca) sigue pendiente, pero con seis incendios en
   la mano ya no es lo que más pesa.
6. ~~**Validar con más incendios**~~ — hecho el 5-oct, y cambió el
   diagnóstico: funciona en 2 de 4. Las huellas quedan en
   `ingest/panal_ingest/reference/events/` y se re-validan con
   `validate_wui.py --event`.
