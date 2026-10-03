# Estado del proyecto

Dónde estamos, qué está bloqueado y qué se olvida si nadie lo anota.

Este documento existe para que el estado no viva en la memoria de nadie. Si
pasan tres semanas sin tocar el repo, esto es lo primero que hay que leer.

**Última actualización:** 2026-10-02

---

## En una línea

Fases 0 y 1 cerradas. Fase 2 construida entera y **validada a medias**: la
mitad de amenaza da 3,83× el azar, la mitad de consecuencia no tiene forma de
validarse sin datos de CONAF. Sin fecha de reunión todavía, así que se avanza
en lo que no depende de nadie: deploy, PWA y medir la brújula del teléfono.

---

## Lo que corre solo ahora mismo

**Público en https://panal.ninobozzi.cl** desde el 2-oct, servido desde
`fuego` (VPS Linode, por Tailscale). Detalle en
[`deploy/README.md`](../deploy/README.md).

| qué | dónde | cada cuánto |
|---|---|---|
| Snapshot nacional, el que se publica | cron de `nino` en `fuego` | 10 min |
| Snapshot nacional, copia local | cron del Mac | 10 min |
| Certificado TLS | certbot en `fuego`, recarga nginx solo | ~60 días |

```bash
ssh fuego tail -8 /var/www/panal.ninobozzi.cl/data/cron_national.log  # ¿sigue vivo?
ssh fuego git -C /var/www/panal.ninobozzi.cl pull --ff-only           # publicar lo pusheado
```

El cron del Mac ya no publica nada: solo mantiene fresca la copia local
para desarrollar. Se puede sacar.

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
- **La búsqueda de escenas Sentinel-2 ordena por nubes, no por cobertura.**
  Deja 9,6% de celdas sin combustible en Valparaíso. Esas quedan sin ranking,
  que es correcto, pero la selección se puede mejorar.
- **El bbox de una región con islas es enorme.** Valparaíso llega a Rapa Nui
  (-109°), así que búsquedas por bbox barren el Pacífico. Mitigado donde
  importa, no en general.
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
   Cifras regeneradas (63 celdas, 12.591 personas) y amenaza revalidada en
   3,83×. **Falta probarla en un teléfono de verdad**: Android de Nino e
   iPhone de Tami — instalar, abrir sin señal, "Cerca de mí".
3. **App Android nativa**: el código de 2020 a `docs/legacy`, proyecto nuevo,
   y lo primero que hace es **medir el error de brújula** contra puntos
   conocidos. El cruce de marcaciones depende de ese número y nadie lo ha
   medido. Teléfono de prueba Android; un iPhone disponible para la PWA.
