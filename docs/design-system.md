# Sistema de diseño

No existía hasta ahora: cada página de `web/` definía sus propios tokens en
un bloque `<style>` inline, y los cuatro bloques ya habían empezado a
divergir (ver [§6](#6-inconsistencias-encontradas)). Este documento es la
fuente de verdad; [`web/panal.css`](../web/panal.css) es su implementación
en código, al mismo nivel que [`web/panal.js`](../web/panal.js) resuelve lo
mismo para las reglas de color de los datos — por la misma razón que da su
cabecera: *una copia de la regla en una segunda página se desalinea en
cuanto se retoca cualquiera de las dos*.

Esto describe lo que el producto **ya es** — extraído de `national.html`,
`wui.html`, `index.html` y `brujula.html` — más las correcciones puntuales
donde esas cuatro páginas ya no estaban de acuerdo entre sí. No es una
propuesta de rediseño.

---

## 1. Marca

**PANAL** es panal de abejas. La grilla de datos es H3, la grilla
hexagonal de Uber. No es coincidencia que el nombre del proyecto de 2020 y
la estructura de datos elegida en 2026 compartan la misma figura — el
logo lo hace explícito.

`web/icons/icon.svg`: una loseta oscura (`--bg`) con tres hexágonos
concéntricos, alternando ámbar y oscuro — un anillo ámbar, un hueco oscuro
adentro, un hexágono ámbar pequeño en el centro. Es el corte transversal de
una celda de panal, y a la vez una referencia directa a cómo H3 anida
resoluciones: un hexágono contiene hexágonos.

El wordmark **PANAL** se escribe siempre igual: mayúsculas, `font-weight:
700`, `letter-spacing: .14em`, tamaño 13px, color `--accent`. Nunca en otro
color, nunca en minúsculas, nunca sin el tracking. Vive arriba a la
izquierda, seguido de los pills de navegación (`.nav`) — nunca centrado,
nunca solo.

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

Todas las páginas son de tema oscuro único (el mapa tiene basemap
claro/oscuro intercambiable; la interfaz alrededor, no).

| Token | Valor | Uso |
|---|---|---|
| `--bg` | `#0e1116` | Lienzo base, `theme-color` de la PWA |
| `--panel` | `#161b23` | Superficie de paneles, chips, controles |
| `--panel-2` | `#1d232d` | Superficie anidada dentro de un panel (hoy solo en `index.html`; se adopta como estándar) |
| `--line` | `#2a323f` | Bordes, separadores, `<hr>` |
| `--ink` | `#e8edf4` | Texto primario |
| `--ink-dim` | `#94a3b8` | Texto secundario, etiquetas, también el gris de "sin observar" en los mapas |
| `--ink-faint` | `#64748b` | Texto terciario, fuentes y notas al pie |
| `--accent` | `#f59e0b` | Color de marca; único acento interactivo (foco, slider, play, borde activo de nav) |
| `--ink-on-accent` | `#1a1205` | Texto/ícono sobre una superficie `--accent` (botón ▶ de los replays) |
| `--ok` | `#7dd3a0` | Estado "fresco" / saludable / dentro de lo esperado |
| `--warn` | `#fbbf24` | Alerta leve: "no validado", "stale", "research" — ver [§6](#6-inconsistencias-encontradas), antes `--unval` en una sola página |
| `--danger` | `#ef4444` | Error, umbral cruzado, "alto" — ver [§6](#6-inconsistencias-encontradas) sobre el segundo rojo que existía |

### 3.2 Escala de severidad cuantizada

La franja "Factor 30-30-30" de `index.html` codifica cuántos de los tres
criterios (temperatura, humedad, viento) se cumplen en cada tramo,
oscureciendo el ámbar hacia `--panel` en cuatro pasos — nunca cambia de
matiz, solo de cuánto se acerca al fondo:

| Criterios cumplidos | Color |
|---|---|
| 3 de 3 | `#f59e0b` (`--accent`) |
| 2 de 3 | `#78581a` |
| 1 de 3 | `#3b3527` |
| 0 de 3 | `#242b36` |

El mismo patrón sirve para cualquier indicador futuro de "cuántas
condiciones de riesgo coinciden": un solo matiz, cuatro profundidades.

### 3.3 Interruptor apagado/encendido

El punto `.dot` de cada criterio del Factor 30-30-30 usa un gris neutro
cuando está apagado, nunca `--line` ni `--ink-faint` directamente (ambos ya
tienen otro trabajo):

| Estado | Relleno | Anillo |
|---|---|---|
| Apagado | `#334155` | `#475569` |
| Encendido | `--accent` con resplandor `box-shadow: 0 0 6px rgba(245,158,11,.7)` | — |

---

## 4. Rampas de datos

Tres paletas, cada una reservada a su propio fenómeno. **No son
intercambiables** — mezclar una rampa en el dominio de otra es exactamente
el error que la regla del negro en [§2](#2-principios-de-diseño) previene.

### 4.1 Potencia radiativa del fuego (FRP) — ámbar/rojo

Definida y calibrada en `panal.js`, calibrada contra la mediana, p90 y
máximo observados en el replay de Viña 2024 (254, 1259 y 3195 MW). Escala
logarítmica con piso de 20 MW para no amontonar la mediana en los rojos:

```
0 MW ─ #fde68a ─ #fbbf24 ─ #f97316 ─ #ef4444 ─ #b91c1c ─ 3200+ MW
```

Es la única rampa que representa intensidad de fuego. Nunca se usa para
exposición, confianza, ni ningún otro eje.

### 4.2 Exposición WUI — violeta

Definida en `wui.html`, deliberadamente **fuera** de las otras dos
escalas del producto: no es la rampa de fuego (esto no es fuego, es
exposición construida) y no es el semáforo verde/amarillo/rojo de
SENAPRED (esto no es una alerta oficial). Cuatro clases por percentil
(`<50`, 50–75, 75–90, top 10%), más clara en el basemap oscuro y más
oscura en el claro para mantener el contraste invertido:

```
oscuro:  #4c1d95 ─ #6d28d9 ─ #a855f7 ─ #e879f9
claro:   #ddd6fe ─ #a78bfa ─ #7c3aed ─ #4c1d95
```

Las celdas censales dispersas (agregadas a resolución 5–8 en vez de
refinadas) se dibujan a menor alfa (`RES_ALPHA`: 1 en r9, 0.5 en r8, 0.3 en
r7–r5) y con contorno visible — la regla de [§2.4](#2-principios-de-diseño)
en código.

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

Una sola familia en toda la interfaz, sin webfont (cero latencia, cero
layout shift):

```css
font: 14px/1.45 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
```

Monoespaciada únicamente para lecturas instrumentales
(`brujula.html`, el HUD de la cámara): `ui-monospace, monospace`.

### Escala

| Tamaño | Uso |
|---|---|
| 9.5–10px | Micro: etiquetas de rampa, fuentes al pie |
| 10.5–11px | Chips, etiquetas uppercase de sección (siempre con `letter-spacing: .06–.14em`) |
| 12–12.5px | Cuerpo por defecto dentro de paneles |
| 13–14px | Texto base del documento, marca |
| 15px | Títulos de sección (`.ttl`) |
| 17–19px | Cifras secundarias |
| 24–30px | Cifra principal del panel (reloj, conteo) |

Regla fija: **todo número que cambia en vivo lleva
`font-variant-numeric: tabular-nums`**, para que el ancho no salte cuadro a
cuadro (relojes, conteos, FRP, slider de edad).

---

## 6. Espaciado y radios

No hay una grilla de 4px/8px declarada, pero los valores reales ya
convergen en una escala corta. Se adopta como está, en vez de forzar una
grilla nueva que obligaría a retocar las cuatro páginas:

**Radios:** `2–3px` swatches y rampas · `6–9px` controles pequeños ·
`10–12px` paneles y tarjetas · `14px` loseta del ícono · `16px` esquina
superior de la hoja inferior en móvil · `999px` pills, chips, botones
redondos.

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
`brujula.html`) enlazan [`web/panal.css`](../web/panal.css) antes de su
propio `<style>`, que ahora guarda solo lo específico de cada una: el mapa,
posiciones y anchos de panel, los controles instrumentales de
`brujula.html`, el sparkline y la línea de tiempo de `index.html`. Una regla
de `panal.css` se pisa en la página con la misma especificidad, porque el
`<style>` va después.

Resuelto al enlazarla:

- Las inconsistencias 1–4 de [§9](#9-inconsistencias-encontradas): `--unval`
  y el literal `#fbbf24` pasan a `--warn`; `--bad` (`#f87171`) y `--hot`
  pasan a `--danger` (`#ef4444`) — en `brujula.html` el rojo de error se
  oscurece un poco por esto; `#1a1205`/`#111` pasan a `--ink-on-accent`;
  la franja del Factor 30-30-30 lee `--sev-0…3` desde CSS en vez de
  literales en JS.
- `.sheet` → `.panel`, `.rlbl` → `.ramp-lbl`, `.badge` → `.chips`.
- `sw.js` cachea `panal.css` en el shell (versión `panal-v3`).

`brujula.html` es una página de documento, no de mapa: hereda tokens y
base, y deshace localmente los dos defaults de panel que no le aplican
(`.warn` como nota al pie y el borde superior de `<details>`).
