/* Shared encoding rules for every PANAL map.
 *
 * These live in one file on purpose. The fire scale's cut points come from
 * measured data, and a copy of them in a second page would drift the moment
 * either was retuned.
 *
 * The rules themselves are set in docs/roadmap.md:
 *   - colour carries intensity, opacity carries confidence
 *   - the weak tiers get a second visual channel, never opacity alone
 *   - opacity is floored, so uncertain never renders as absent
 *   - no black: that is reserved for the burn scar
 */

// Four levels in the ACHEZ accent colours, yellow to red
// (docs/design-system.md §4.1). The cut points come from per-cell FRP
// observed in the Viña 2024 replay — median 254 MW, p75 656, p90 1,259,
// max 3,195 — so "baja" is the lower half of what a real fire produces,
// "media" up to its p75, "alta" up to its p90 and "muy alta" the top tenth.
// A continuous ramp read finer, but the scale the reader learns across the
// app is these four words, and every legend writes them out.
const FRP_LEVELS = [
  [250, "baja", [240, 195, 40]],        // #F0C328, the isotipo's yellow
  [650, "media", [242, 135, 5]],        // #F28705
  [1250, "alta", [243, 50, 4]],         // #F33204
  [Infinity, "muy alta", [167, 6, 4]],  // #A70604, the "Polygon" red
];

function frpLevel(mw) {
  const v = Math.max(0, mw || 0);
  return FRP_LEVELS.find(([max]) => v < max);
}

/** FRP in MW to an [r,g,b] triple. */
function frpRGB(mw) {
  return frpLevel(mw)[2].slice();
}

/** FRP in MW to its level's word: "baja", "media", "alta" or "muy alta". */
function frpLabel(mw) {
  return frpLevel(mw)[1];
}

/** FRP in MW to a CSS colour. */
function frpColor(mw) {
  return "rgb(" + frpRGB(mw).join(",") + ")";
}

// Evidence tier to alpha. Floored at 0.3: below roughly a third the cell
// vanishes into the basemap and "uncertain" silently becomes "nothing here".
const OPACITY = {
  good: 0.85, saturated: 0.85, high_probability: 0.6,
  medium_probability: 0.45, cloud_contaminated: 0.35, low_probability: 0.3,
};

// The same tiers, in the words the page shows. The keys are the pipeline's
// vocabulary (GOES mask categories; VIIRS high/nominal/low maps onto the
// probability ones) and never reach the reader as-is.
const CONF_ES = {
  good: "detección de buena calidad", saturated: "saturada: fuego muy intenso",
  high_probability: "probabilidad alta", medium_probability: "probabilidad media",
  cloud_contaminated: "con nubes", low_probability: "probabilidad baja",
};

// Tiers that also get a dashed or dimmed outline, because opacity alone
// fails WCAG and reads differently on light and dark basemaps.
const WEAK = new Set(["low_probability", "cloud_contaminated"]);

// Keyless basemaps. The dark one is CARTO's dark-matter recoloured into the
// ACHEZ palette by basemap() below; the other two are used as published.
const STYLES = [
  ["oscuro", "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"],
  ["claro", "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"],
  ["callejero", "https://tiles.openfreemap.org/styles/liberty"],
];

// Dark-matter is greys. Each grey is moved onto the Petróleo–Cielo scale by
// its lightness, so the style's own hierarchy (land < roads < labels) holds
// and only the hue changes. Land lands on --bg, so the panels read as the
// same surface as the map. Nothing maps to black: that stays the burn
// scar's.
const PETROLEO_STOPS = [
  [0, [6, 34, 43]],        // below land: water
  [0.055, [10, 46, 56]],   // land, #0E0E0E in dark-matter → Petróleo 900
  [0.25, [42, 106, 124]],  // roads and borders → --line
  [0.5, [127, 195, 218]],  // Cielo 300
  [0.9, [234, 244, 247]],  // labels
  [1, [255, 255, 255]],
];
// Water is a little darker than land, as in dark-matter itself.
const PETROLEO_FIXED = { water: [6, 32, 41], waterway: [21, 85, 102] };

function parseColor(c) {
  if (c === "transparent") return null;
  let m = /^#([0-9a-f]{3,8})$/i.exec(c);
  if (m) {
    let h = m[1];
    if (h.length <= 4) h = [...h].map(x => x + x).join("");
    const n = [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16));
    return [...n, h.length === 8 ? parseInt(h.slice(6, 8), 16) / 255 : 1];
  }
  m = /^rgba?\(([^)]+)\)$/i.exec(c);
  if (m) {
    const v = m[1].split(",").map(Number);
    return [v[0], v[1], v[2], v.length > 3 ? v[3] : 1];
  }
  return null;
}

function petroleo(c) {
  const rgba = parseColor(c);
  if (!rgba) return c;
  const [r, g, b, a] = rgba;
  const l = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  let k = 1;
  while (k < PETROLEO_STOPS.length - 1 && l > PETROLEO_STOPS[k][0]) k++;
  const [la, ca] = PETROLEO_STOPS[k - 1], [lb, cb] = PETROLEO_STOPS[k];
  const u = Math.max(0, Math.min(1, (l - la) / (lb - la)));
  const out = ca.map((v, j) => Math.round(v + (cb[j] - v) * u));
  return `rgba(${out.join(",")},${a})`;
}

// Recolour every colour inside a paint value: plain strings, zoom stops and
// expressions alike.
function recolour(v, fixed) {
  if (typeof v === "string")
    return !parseColor(v) ? v : fixed ? `rgb(${fixed.join(",")})` : petroleo(v);
  if (Array.isArray(v)) return v.map(x => recolour(x, fixed));
  if (v && typeof v === "object")
    return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, recolour(x, fixed)]));
  return v;
}

let darkStyle = null;

/** The style for STYLES[k]: a URL, or for the dark one the recoloured
 *  style object. Falls back to the plain URL if it cannot be fetched. */
async function basemap(k) {
  const url = STYLES[k % STYLES.length][1];
  if (k % STYLES.length !== 0) return url;
  if (!darkStyle) {
    try {
      const style = await (await fetch(url)).json();
      for (const layer of style.layers) {
        const fixed = PETROLEO_FIXED[layer.id];
        for (const key of Object.keys(layer.paint || {}))
          if (key.endsWith("color"))
            layer.paint[key] = recolour(layer.paint[key], fixed);
      }
      darkStyle = style;
    } catch {
      return url;
    }
  }
  return JSON.parse(JSON.stringify(darkStyle));
}

/** Which H3 level to serve at a given zoom.
 *
 * Coarsening as the viewport widens is exact — aggregating up the H3
 * hierarchy conserves every value. The reverse, refining sensor data into
 * finer cells, is forbidden in the pipeline and must never be done here
 * either: a 2 km pixel drawn as 400 m cells invents precision.
 */
const ZOOM_BREAKS = [[9.5, 7], [7.5, 6], [0, 5]];

function resForZoom(z, available) {
  const have = new Set((available || [7, 6, 5]).map(Number));
  for (const [minZoom, r] of ZOOM_BREAKS)
    if (z >= minZoom && have.has(r)) return r;
  return Math.min(...have);
}

/** Human-readable age. */
function fmtAge(min) {
  if (min == null) return "—";
  if (min < 60) return `${Math.round(min)} min`;
  if (min < 60 * 48) return `${Math.round(min / 60)} h`;
  return `${Math.round(min / 1440)} d`;
}
