# Sistema de diseño — ACHEZ

La interfaz de `web/` sigue el sistema de diseño **ACHEZ** (lienzo "ACHEZ
Design System" en Claude): la marca de producto de la plataforma, *powered
by PANAL*. Este documento es su traducción a la web; el lienzo manda en
color, tipografía, logo y componentes, y este documento agrega lo que el
lienzo no cubre (mapas, rampas de datos, la hoja inferior, la confianza).
[`web/panal.css`](../web/panal.css) es su implementación en código, al
mismo nivel que [`web/panal.js`](../web/panal.js) resuelve lo mismo para
las reglas de color de los datos — por la misma razón que da su cabecera:
*una copia de la regla en una segunda página se desalinea en cuanto se
retoca cualquiera de las dos*.

Antes de ACHEZ cada página definía sus propios tokens en un `<style>`
inline, y las cuatro ya habían divergido (ver
[§9](#9-inconsistencias-encontradas)).

---

## 1. Marca

**ACHEZ** es el producto; **PANAL** es el motor de datos debajo, y por eso
el logo lleva la bajada *POWERED BY PANAL*. El nombre del repositorio, del
dominio (`panalforestal.cl`) y de la PWA sigue siendo PANAL.

`web/icons/achez.svg` es el isotipo: una llama doble, naranja (degradado
`#F4C160` → `#D96704`) y celeste (`#64D9F2` → `#03738C`). Se usa el archivo
tal cual — sin cambiar proporciones, colores ni degradados.

El logo completo (`.logo`) es isotipo + **ACHEZ** en Plus Jakarta Sans
Regular blanco + **POWERED BY PANAL** en Poppins Regular `#64D9F2`, con la
bajada a 0,35× el tamaño de ACHEZ. Va solo sobre fondos oscuros, arriba a
la izquierda, seguido de los pills de navegación (`.nav`) — nunca centrado,
nunca solo. En la cabecera: isotipo de 36px de alto, ACHEZ a 22px.

El favicon (`icons/icon.svg`) es el isotipo solo, sobre fondo
transparente. Los íconos de la PWA (`icon-192.png`, `icon-512.png`,
`maskable-512.png`, `apple-touch-icon.png`) lo ponen sobre una loseta
Petróleo 900, porque los lanzadores necesitan una forma opaca y completa.
Todos los genera `icons/make_icons.py` a partir de `achez.svg`.

---

## 2. Principios de diseño

Son las "ground rules" del [`README`](../README.md) raíz, traducidas a
reglas visuales, más las que ya vive codificadas como comentarios en
`panal.js`:

1. **Mostrar el desfase.** Ninguna vista con datos en vivo omite la edad
   del dato. Por eso existe el chip `.chip.stale` — nunca se oculta cuánto
   tiempo tiene lo que se está mirando.
2. **Mostrar el desglose.** Un número solo no es accionable: todo panel
   que muestra un total (`.big`, `.clock`) lo acompaña de filas `.kv` con
   los componentes.
3. **Mostrar la incertidumbre, nunca silenciarla.** La opacidad tiene un
   piso (0.3): un dato de baja confianza nunca se desvanece hasta
   desaparecer, porque "incierto" no puede volverse visualmente
   "ausente". Los niveles débiles reciben además un segundo canal —
   contorno punteado o atenuado — porque la opacidad sola falla WCAG y
   cambia de lectura entre mapa claro y oscuro.
4. **Nunca inventar granularidad.** La resolución H3 que se dibuja depende
   del zoom y de qué resolución mide realmente el sensor en ese punto
   (`resForZoom` en `panal.js`); nunca se refina un dato tosco para que se
   vea preciso. En `wui.html`, las celdas censales dispersas (resolución
   5–8) se dibujan más tenues que las de resolución 9 exactamente para que
   el área nunca lea como población.
5. **Validar antes de publicar, y mostrarlo si no está validado.** De ahí
   el banner `.research` en ámbar en `wui.html` — "research, not a risk
   product" — con el detalle completo visible sin interacción, no en un
   tooltip.
6. **Cero datos personales.** No hay cuentas, no hay avatares, no hay
   nada en la interfaz que identifique a una persona. "Cerca de mí" usa
   geolocalización del navegador sin enviarla a ningún lado.

Y la regla propia de la codificación visual de datos, que aplica a
cualquier capa nueva que se agregue:

> **El color codifica magnitud. La opacidad codifica confianza. Nunca al
> revés, y nunca una sola de las dos para ambas cosas.** El negro puro
> (`#000`) está reservado exclusivamente para la cicatriz de quemado —
> ninguna otra capa lo usa, para que "quemado" nunca se confunda con
> "sin datos" o con un fondo de mapa oscuro.

---

## 3. Color

### 3.1 Tokens de interfaz

Petróleo y fuego. Todas las páginas son de tema oscuro único (el mapa tiene
basemap claro/oscuro intercambiable; la interfaz alrededor, no). El lienzo
ACHEZ también define neutros claros (Blanco, Niebla `#F2F4F5`, Ceniza
`#C9D1D4`, Humo `#4F6067`) para pantallas claras; la web todavía no tiene
ninguna.

| Token | Valor | ACHEZ | Uso |
|---|---|---|---|
| `--bg` | `#0A2E38` | Petróleo 900 | Lienzo base, `theme-color` de la PWA |
| `--panel` | `#0E3F4D` | Petróleo 800 | Superficie de paneles, chips, controles |
| `--panel-2` | `#155566` | Petróleo 600 | Tarjetas dentro de un panel, opción activa |
| `--line` | `#2A6A7C` | — | Bordes, separadores, asa de la hoja |
| `--glass` / `--glass-bg` | Petróleo 800 / 900 al 94 % | — | Paneles y cabecera sobre el mapa |
| `--ink` | `#FFFFFF` | Blanco | Texto primario (11,4:1 sobre panel) |
| `--ink-dim` | `#D5E6EC` | — | Texto secundario, etiquetas |
| `--ink-faint` | `#9FC9D6` | — | Texto terciario, notas (4,7:1 sobre Petróleo 600) |
| `--accent` | `#F59A55` | Fuego 400 | Destacados sobre oscuro: foco, nav activa, antetítulos, sliders (5,2:1) |
| `--action` | `#B9500C` | Fuego 600 | Botón que hace algo, con texto blanco (5:1) |
| `--ink-on-accent` | `#0A2E38` | Petróleo 900 | Texto sobre `--accent` |
| `--brand-sky` | `#64D9F2` | — | Solo la bajada del logo |
| `--ok` | `#7dd3a0` | — | "Fresco": ACHEZ no tiene verde y "fresco" no puede ser fuego |
| `--warn` | `#FBC98E` | Fuego 200 | Avisos: "no validado", "stale", "research" |
| `--danger` | `#EE7A2A` | Fuego 500 | Como relleno. Como texto pequeño sobre panel no llega a 4,5:1: ahí va `--accent` en negrita |

### 3.2 Escala de severidad cuantizada

La franja "Factor 30-30-30" de `index.html` codifica cuántos de los tres
criterios (temperatura, humedad, viento) se cumplen en cada tramo,
mezclando Fuego 400 hacia `--panel` en cuatro pasos — nunca cambia de
matiz, solo de cuánto se acerca al fondo. `index.html` lee estos valores de
CSS, no los repite en JS:

| Criterios cumplidos | Token | Color |
|---|---|---|
| 3 de 3 | `--sev-3` | `#F59A55` (`--accent`) |
| 2 de 3 | `--sev-2` | `#766851` |
| 1 de 3 | `--sev-1` | `#354E4E` |
| 0 de 3 | `--sev-0` | `#1A444D` |

### 3.3 Interruptor apagado/encendido

| Estado | Relleno | Anillo |
|---|---|---|
| Apagado | `--off-fill` `#1A444D` | `--off-ring` `#3E7F91` |
| Encendido | `--accent` con resplandor `box-shadow: 0 0 6px rgba(245,154,85,.7)` | — |

### 3.4 Mapa base oscuro

El basemap "oscuro" es dark-matter de CARTO reteñido en el navegador
(`basemap()` en `panal.js`): cada gris se lleva a la escala Petróleo–Cielo
según su luminosidad, así se conserva la jerarquía del estilo (tierra <
calles < etiquetas) y solo cambia el matiz. La tierra queda en `--bg`, el
agua un poco más oscura (`#062029`), las calles cerca de `--line`, las
etiquetas casi blancas. Nada queda en negro. Si el estilo no se puede
descargar, se usa dark-matter tal cual. "Claro" y "callejero" no se tocan.

---

## 4. Rampas de datos

Tres paletas, cada una reservada a su propio fenómeno. **No son
intercambiables** — mezclar una rampa en el dominio de otra es exactamente
el error que la regla del negro en [§2](#2-principios-de-diseño) previene.

### 4.1 Intensidad del fuego — acentos ACHEZ, del amarillo al rojo

En `panal.js` (`FRP_LEVELS`, `frpRGB`, `frpLabel`) y en `panal.css`
(`--fire-low|mid|high|max`); la usan Replays y Detección. Cuatro niveles
con nombre, no una rampa continua: el nivel siempre se escribe (leyendas,
tooltips, `.lvl`), el color nunca va solo.

| Nivel | FRP por celda | Color |
|---|---|---|
| baja | < 250 MW | `#F0C328`, amarillo del isotipo |
| media | 250–650 MW | `#F28705` |
| alta | 650–1250 MW | `#F33204` |
| muy alta | ≥ 1250 MW | `#A70604`, rojo del componente "Polygon" |

Los cortes salen del replay de Viña 2024 (mediana 254 MW, p75 656, p90
1259, máximo 3195): "baja" es la mitad inferior de lo que produce un
incendio real, "media" hasta su p75, "alta" hasta su p90, "muy alta" el
décimo superior. Reemplaza a la rampa logarítmica continua de cinco pasos
que había antes; se pierde gradación dentro de cada nivel a cambio de una
escala que el lector aprende una vez para toda la app.

Es la única escala que representa intensidad de fuego. La exposición WUI
(§4.2) comparte los cálidos, pero empieza en celeste y está en otra página
con su propia leyenda. El lienzo define además escalas de agua, humedad y
viento, que la web todavía no dibuja.

### 4.2 Exposición WUI — de celeste a rojo, hexágono "Polygon"

Definida en `wui.html`. Cinco clases por percentil (`<25`, 25–50, 50–75,
75–90, top 10%), del celeste al rojo: el extremo celeste es lo menos
expuesto, el rojo lo que tiene más combustible junto a viviendas.

```
#64D9F2 ─ #F0C328 ─ #F28705 ─ #F33204 ─ #A70604
```

Celeste de la marca, amarillo del isotipo, dos naranjos y el rojo del
componente "Polygon". El orden se lee por significado (frío → caliente), no
por luminosidad, así que es el mismo en todos los basemaps. Es una escala
distinta de la intensidad del fuego (§4.1), aunque comparta matices
cálidos: cada leyenda dice qué mide.

El percentil es sobre todas las celdas de la región, no solo las
habitadas, así que entre las que se dibujan el celeste es raro (≈ 5 % en
Valparaíso). Que sea la clase más baja no la vuelve "segura": el índice no
está validado (§2.5), y la leyenda nunca la llama así.

Cada celda sigue el componente "Polygon" del Figma de Space Apps 2023:
relleno al 70 %, borde interior sólido del mismo color (≈ un décimo del
hexágono; en el mapa, ancho fijo de r9 con tope de 4px) y fusión *screen*
sobre el basemap oscuro (en los claros, *screen* lavaría todo y no se usa).
Seleccionada, el segundo estado del componente: relleno más oscuro y borde
más claro y grueso; la celda sale de la capa base para que el *screen* no
la aclare.

No usa negro.

Las celdas censales dispersas (agregadas a resolución 5–8 en vez de
refinadas) se dibujan a menor alfa (`RES_ALPHA`: 1 en r9, 0.5 en r8, 0.3 en
r7–r5), con borde fino y atenuado — la regla de
[§2.4](#2-principios-de-diseño) en código: el área nunca lee como
población. "Sin combustible observado" usa Humo `#4F6067`, un neutro
oscuro fuera de la escala: no es riesgo bajo, es no medido.

### 4.3 Confianza — opacidad, nunca color

```
good / saturated        0.85
high_probability        0.60
medium_probability       0.45
cloud_contaminated      0.35  + contorno atenuado
low_probability          0.30 (piso) + contorno punteado
```

El gris de "no observado" es `rgb(148,163,184)` — el mismo valor que
`--ink-dim` — a alfa reducida, para separar "no medido" de "medido en
cero".

---

## 5. Tipografía

Dos voces, desde Google Fonts (un `<link>` por página, `display=swap`):

| Familia | Token | Uso |
|---|---|---|
| Montserrat 700–800 | `--font-display` | Títulos (`.ttl`, en mayúsculas), antetítulos de sección (`h4`, 700, `letter-spacing: .14em`, en `--accent`), cifras grandes (`.big`, `.clock`), botones |
| Nunito Sans 400–700 | `--font-text` | Texto e interfaz |
| Plus Jakarta Sans 400, Poppins 400 | — | Solo el logo |

Sin conexión, todo cae a `system-ui`. Monoespaciada únicamente para
lecturas instrumentales (`brujula.html`, el HUD de la cámara):
`ui-monospace, monospace`.

### Escala

El lienzo ACHEZ está pensado para pantallas de app (cuerpo 16px). Los
paneles sobre el mapa son más densos y conservan la escala de antes:

| Tamaño | Uso |
|---|---|
| 9.5–10px | Micro: etiquetas de rampa, fuentes al pie |
| 10.5–11px | Chips, antetítulos uppercase |
| 12–12.5px | Cuerpo por defecto dentro de paneles |
| 13–15px | Texto base del documento, títulos de sección (`.ttl`) |
| 17–22px | Cifras secundarias, ACHEZ en el logo |
| 24–30px | Cifra principal del panel (reloj, conteo) |

Regla fija: **todo número que cambia en vivo lleva
`font-variant-numeric: tabular-nums`**, para que el ancho no salte cuadro a
cuadro (relojes, conteos, FRP, slider de edad).

---

## 6. Espaciado y radios

No hay una grilla de 4px/8px declarada, pero los valores reales ya
convergen en una escala corta. Se adopta como está, en vez de forzar una
grilla nueva que obligaría a retocar las cuatro páginas:

**Radios (ACHEZ):** `3px` swatches · `12px` campos y avisos · `16px`
paneles y tarjetas · `24px` esquina superior de la hoja inferior en móvil ·
`999px` botones, pills, chips, rampas y controles segmentados. Botones de
al menos 44px de alto donde se tocan con el dedo.

**Separaciones:** `4, 6, 7, 8, 9, 10, 12, 14px` — sin salto mayor a 2–4px
entre pasos consecutivos.

**Única breakpoint:** `640px`. Por debajo, el panel lateral se convierte en
hoja inferior (bottom sheet): oculta bajo el viewport salvo un asa (`.grip`)
visible, se expande con `transform: translateY(...)` y la clase `.open`.
Cuánto queda a la vista cerrada es `--peek` (112px por defecto; `wui.html`
lo sube a 142px porque ahí tienen que caber el título y el modo) — antes
era un número mágico distinto repetido en cada página.
Se usan los insets de área segura (`env(safe-area-inset-top|bottom)`) en
cabecera y hoja, para notch y home indicator del PWA instalado. Con
`prefers-reduced-motion: reduce`, la transición de la hoja se anula.

---

## 7. Componentes

| Componente | Clase | Dónde vive hoy |
|---|---|---|
| Wordmark + nav | `.brand`, `.nav a` | las 4 páginas |
| Chip de estado | `.chips` > `.chip`, con `.fresh`/`.stale`/`.act`; `button.chip` | las 3 páginas con mapa (`index.html` usaba `.badge` como contenedor, unificado) |
| Panel flotante / hoja inferior | `.panel` (+ `--peek`) | `national.html`, `wui.html` (antes `.sheet`, unificado) |
| Control segmentado | `.seg` | `wui.html` (cambiar entre amenaza/consecuencia) |
| Fila de interruptor | `label.row` | `national.html`, `index.html` |
| Rampa + etiquetas | `.ramp`, `.ramp-lbl` (antes también `.rlbl`, unificado) | las 3 páginas con mapa |
| Swatch + etiqueta discreta | `.lrow`, `.key` | leyendas de `national.html`, `index.html` |
| Tarjeta de detalle de celda | `.card` | `wui.html` |
| Aviso calmo (verde) | `.quiet` | `national.html` |
| Aviso de no-validado (ámbar) | `.research`, `.unvalbox` | `wui.html` |
| Divulgación progresiva | `<details><summary>` | `wui.html` |
| Botón primario circular | `button.play` | `index.html` |
| Botón secundario en pill | `.locate` | `wui.html` |
| Estado de carga | `.loading` | las 4 páginas |
| Nota de fuente | `.src`, `.warn` | las 4 páginas |

`web/panal.css` implementa estos como clases reutilizables sobre los
tokens de [§3](#3-color); los estilos propios de cada página (el mapa, los
controles instrumentales) siguen inline.

---

## 8. Voz y contenido

- Toda la interfaz está en español (`lang="es"`); la documentación de
  ingeniería queda en inglés — son públicos distintos y así se mantiene.
- Frases declarativas con números medidos en vez de adjetivos: "despeja el
  azar claramente en dos", "95.7%", "58 celdas, 10.660 personas". Cualquier
  copy nuevo sigue el mismo registro.
- Las limitaciones nunca van en un tooltip que hay que descubrir: viven en
  el panel principal, visibles sin interactuar (ver `.research`,
  `.unvalbox`, `.warn`).

---

## 9. Inconsistencias encontradas

Documentadas en vez de corregidas en silencio, porque resolverlas implica
tocar las páginas en producción:

1. **Dos rojos de "peligro" distintos.** `brujula.html` define
   `--bad: #f87171`; `index.html` define `--hot: #ef4444` para el mismo
   rol. Se adopta `#ef4444` como `--danger` porque ya es el escalón "alto"
   de la rampa FRP — el sistema no suma un rojo nuevo.
2. **Mismo color, dos nombres.** `--unval` (`#fbbf24` en `wui.html`) y el
   literal `#fbbf24` usado sin variable en `.chip.stale`/`.quiet.stale` de
   `national.html` y en `.warn` de `brujula.html` son el mismo color con
   roles idénticos. Se adopta `--warn`.
3. **`--panel-2` solo existe en `index.html`.** Las otras tres páginas no
   tienen una segunda superficie nombrada; se promueve al set común.
4. **Colores sin token.** `#1a1205` (texto sobre botón de acento) y la
   escala de severidad de [§3.2](#32-escala-de-severidad-cuantizada) viven
   como literales en CSS/JS, no en `:root`. Se nombran en `panal.css`.
5. **El mismo bloque de `<style>` se repite casi íntegro en las 4
   páginas**, con estas derivas como evidencia de que ya se desalineó.
   `panal.js` existe por esta razón exacta para las reglas de color de
   datos ("una copia... se desalinea en cuanto se retoca cualquiera de las
   dos"); el mismo argumento aplica a los tokens de interfaz.

---

## 10. Estado

Las cuatro páginas (`national.html`, `wui.html`, `index.html`,
`brujula.html`) cargan las fuentes de ACHEZ y enlazan
[`web/panal.css`](../web/panal.css) antes de su propio `<style>`, que guarda
solo lo específico de cada una: el mapa, posiciones y anchos de panel, los
controles instrumentales de `brujula.html`, el sparkline y la línea de
tiempo de `index.html`. Una regla de `panal.css` se pisa en la página con la
misma especificidad, porque el `<style>` va después.

- Cabecera con el logo ACHEZ completo en las cuatro páginas.
- Tokens Petróleo/Fuego, Montserrat + Nunito Sans, radios y botones píldora.
- Intensidad del fuego en tres niveles (§4.1), en mapas, leyendas y
  tooltips.
- `sw.js` cachea `panal.css` e `icons/achez.svg`; la CSP (en
  `deploy/nginx`, todavía *report-only*) admite `fonts.googleapis.com` y
  `fonts.gstatic.com`.

- Favicon e íconos de la PWA con el isotipo (§1).
- Mapa base oscuro en la paleta Petróleo (§3.4).

Pendiente: el `name` del manifiesto sigue siendo PANAL.
