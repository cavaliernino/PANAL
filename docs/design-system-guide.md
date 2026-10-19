# Cómo usar el sistema de diseño ACHEZ

Guía práctica para agregar o tocar una página en `web/`. El *por qué* de
cada token y componente vive en [`design-system.md`](design-system.md) —
este documento no lo repite, solo dice cómo usarlo. Si cambias un valor,
cámbialo ahí y en el código a la vez; si inventas un color o un patrón
nuevo, pregúntate primero si ya existe uno en `panal.css` que sirva.

---

## 1. Arrancar una página nueva

Copia este bloque `<head>` (ajusta título, descripción y `theme-color` si
cambia) y pégalo antes de tu propio `<style>`:

```html
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>PANAL · …</title>
<meta name="description" content="…">
<meta name="theme-color" content="#0A2E38">
<link rel="manifest" href="manifest.json">
<link rel="icon" href="icons/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&family=Nunito+Sans:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400&display=swap">
<link rel="stylesheet" href="panal.css">
<style>
  /* Tokens y componentes: panal.css. Aquí solo lo propio de esta vista. */
</style>
</head>
```

Reglas de ese bloque:

- **`panal.css` se enlaza antes de tu `<style>`.** Tu bloque pisa cualquier
  regla suya con la misma especificidad — es la forma prevista de ajustar
  algo puntual (ver `.panel{width:230px}` en `national.html`), no un bug a
  evitar.
- **Nunca copies un token o un componente dentro de tu `<style>`.** Si
  necesitas un color que no está en `:root`, es señal de que falta un
  token en `panal.css`, no de que debas poner el literal en tu página — así
  empezaron las cinco inconsistencias del [§9 de
  design-system.md](design-system.md#9-inconsistencias-encontradas).
- Si la página pinta un mapa, agrega MapLibre (y deck.gl + h3-js solo si
  necesitas `H3HexagonLayer` a escala nacional — ver
  [`web/README.md`](../web/README.md#why-deck.gl-here-and-not-in-the-replay)
  antes de sumar esa dependencia) y `panal.js` al final, antes de tu
  `<script>` propio.
- `lang="es"`: toda la interfaz está en español; la documentación de
  ingeniería (este archivo incluido) queda en inglés — son públicos
  distintos.

---

## 2. El esqueleto de página: header, nav, panel

Toda página con mapa comparte esta estructura. Cabecera superpuesta y
panel flotante, los dos con `position:absolute` sobre el `#map`:

```html
<div id="map"></div>

<header>
  <div>
    <div class="logo"><img src="icons/achez.svg" alt="" width="30" height="36">
      <span><b>PANAL</b></span></div>
    <nav class="nav">
      <a href="national.html" aria-current="page">Detección</a>
      <a href="wui.html">Exposición</a>
      <a href="index.html">Replays</a>
    </nav>
    <div class="ttl">Título de la vista</div>
    <div class="sub">Subtítulo, una línea</div>
  </div>
  <div class="chips">
    <span class="chip" id="c-age">—</span>
    <span class="chip act" id="c-style">mapa: oscuro</span>
  </div>
</header>

<div class="panel" id="panel">
  <button class="grip" id="grip" aria-label="Abrir o cerrar el panel"></button>
  <!-- contenido del panel, ver §3 -->
</div>

<div class="loading" id="loading">Cargando…</div>
```

Puntos que no son opcionales:

- **El logo completo va siempre**, isotipo + ACHEZ + bajada, arriba a la
  izquierda, nunca centrado ni separado de la bajada. Es el único logo que
  existe — no se recolorea.
- **`.nav a[aria-current="page"]`** marca la página activa (fondo
  `--accent`); ponlo en el link de la página donde estás, no lo dejes en
  todas.
- **`.grip` solo importa en móvil** (≤640px): es el asa que abre/cierra la
  hoja inferior. Inclúyelo siempre aunque en escritorio no se vea — es lo
  que hace que `.panel` sea panel lateral arriba de 640px y hoja inferior
  abajo, sin que escribas una media query propia.
- **`--peek`** (cuánto de la hoja queda a la vista cerrada en móvil) se fija
  por página según lo que tiene que caber ahí sin abrir:
  `.panel{--peek:142px}` si el título y un selector deben verse cerrados;
  el default de `panal.css` es 112px. Mide lo que realmente necesitas
  visible, no copies un número de otra página.
- **`.loading`** cubre toda la pantalla hasta que haya datos; quítalo (o
  dale `hidden`) recién cuando el mapa esté listo para pintar — nunca antes,
  porque un mapa en blanco se lee como "no hay incendios" (regla del README
  de `web/`: *la ausencia de datos y un pipeline roto nunca deben verse
  igual*).

---

## 3. Patrones comunes dentro del panel

Copia el que necesites; todos están en `panal.css`, ninguno necesita CSS
propio.

**Cifra principal + desglose** — todo total va acompañado de sus partes,
nunca solo:

```html
<div class="big"><span id="s-count">—</span><small>focos detectados</small></div>
<div class="kv"><span>FRP total</span><b id="s-frp">—</b></div>
```

**Antetítulo de sección** (mayúsculas, tracking ancho, color `--accent`):

```html
<h4>Capas</h4>
```

**Fila de interruptor:**

```html
<label class="row"><input type="checkbox" id="t-goes" checked>
  GOES <i id="n-goes">0</i></label>
```

**Control de rango con etiquetas:**

```html
<input type="range" id="age" min="0" max="4" step="1" value="4">
<div class="ramp-lbl"><span>6 h</span><span id="age-lbl">7 d</span></div>
```

**Control segmentado** (pastilla con fondo hundido, opción activa rellena):

```html
<div class="seg">
  <button aria-pressed="true">Amenaza</button>
  <button aria-pressed="false">Consecuencia <small class="unval">no validado</small></button>
</div>
```

**Rampa de color + leyenda** — el `background` de cada `<i>` lo defines tú;
usa los tokens de intensidad de fuego (`--fire-low|mid|high|max`) solo si
estás codificando intensidad de fuego, nunca otra magnitud (ver
[§4 de design-system.md](design-system.md#4-rampas-de-datos)):

```html
<div class="ramp">
  <i style="background:var(--fire-low)"></i>
  <i style="background:var(--fire-mid)"></i>
  <i style="background:var(--fire-high)"></i>
  <i style="background:var(--fire-max)"></i>
</div>
<div class="ramp-lbl"><span>baja</span><span>media</span><span>alta</span><span>muy alta</span></div>
```

**Chip de estado**, con las variantes de frescura de dato:

```html
<span class="chip fresh"><b>vivo</b></span>
<span class="chip stale">hace 42 min</span>
<button class="chip act" id="c-reload">recargar</button>
```

**Tarjeta de detalle** (al hacer click en una celda, por ejemplo):

```html
<div class="card" hidden>
  <button class="x" aria-label="Cerrar">×</button>
  <div class="where">Comuna, región</div>
  <div class="row"><span>FRP</span><b>420 MW</b></div>
  <span class="lvl mid">media</span>
</div>
```

**Aviso calmo** (verde, estado sin incidentes) **vs. aviso de no validado**
(ámbar) — nunca en un tooltip, siempre visible sin interactuar:

```html
<div class="quiet"><b>Sin focos activos.</b> Último barrido hace 4 min.</div>

<div class="research"><b>Investigación, no un producto de riesgo.</b>
  El índice despeja el azar en dos incendios de seis probados.</div>
```

**Divulgación progresiva** para detalle que no todos necesitan leer:

```html
<details>
  <summary>Cómo se calcula</summary>
  <p>…</p>
</details>
```

**Botón primario** (circular, acción que hace algo) y **botón secundario**
en pill (ej. "Cerca de mí"):

```html
<button class="play">▶</button>
<button class="locate">Cerca de mí</button>
```

---

## 4. Checklist antes de abrir el PR

- [ ] `panal.css` enlazado antes de tu `<style>`; ningún token ni
      componente copiado dentro de él.
- [ ] Logo completo en la cabecera, sin recolorear ni separar la bajada.
- [ ] `.nav a[aria-current="page"]` apunta a tu página.
- [ ] Si hay dato en vivo: el chip de edad existe y tiene su variante
      `.stale`; ningún número que cambie en vivo olvida
      `font-variant-numeric: tabular-nums` (clase `.num`/`.tabular`, o la
      propiedad directa).
- [ ] Si hay una cifra total, va con sus componentes en `.kv` al lado.
- [ ] Si agregas una rampa o escala de color nueva: ¿es realmente un
      fenómeno nuevo, o cabe en intensidad de fuego / exposición WUI /
      confianza ya existentes? Si es nueva, no toca ningún matiz ya
      reservado (negro = cicatriz de quemado, siempre) y queda documentada
      en `design-system.md` §4.
- [ ] Si hay algo no validado o con alcance limitado: vive en `.research` o
      `.unvalbox` dentro del panel, no en un tooltip.
- [ ] Probado en ancho ≤640px: el panel se comporta como hoja inferior, el
      `--peek` deja ver lo que esa página necesita cerrada.
- [ ] `prefers-reduced-motion: reduce` respetado (gratis si usaste `.panel`
      tal cual; solo revisa si agregaste una transición propia).

---

## 5. Cuándo *no* usar algo de aquí

- Si tu página no tiene mapa ni el patrón panel/hoja-inferior, igual usa
  los tokens de color y tipografía — pero no fuerces `.panel` o `.chips`
  donde no aplican.
- Si necesitas un color que no está en `:root`: no inventes un literal en
  tu `<style>`. Añádelo como token en `panal.css`, con su razón, y úsalo
  desde ahí — aunque lo use una sola página por ahora. Así se evita que
  vuelva a pasar lo del [§9 de design-system.md](design-system.md#9-inconsistencias-encontradas).
- Si crees que te falta un componente (no una variante de uno que ya
  existe): revisa primero la [tabla de componentes](design-system.md#7-componentes)
  de `design-system.md` — puede que ya exista con otro nombre que no
  reconociste.
