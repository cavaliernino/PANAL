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

// Keyless basemaps: name, style URL, and whether it is dark enough that
// white outlines read on it. The dark one is CARTO's dark-matter recoloured
// into the ACHEZ palette by basemap() below; the satellite one is built by
// satellite(); the other two are used as published.
const STYLES = [
  ["oscuro", "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json", true],
  ["claro", "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json", false],
  ["callejero", "https://tiles.openfreemap.org/styles/liberty", false],
  ["satélite", null, true],
];
const SATELLITE = 3;

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

/** Dark-matter recoloured, fetched once; null if it cannot be fetched. */
async function darkMatter() {
  if (!darkStyle) {
    try {
      const style = await (await fetch(STYLES[0][1])).json();
      for (const layer of style.layers) {
        const fixed = PETROLEO_FIXED[layer.id];
        for (const key of Object.keys(layer.paint || {}))
          if (key.endsWith("color"))
            layer.paint[key] = recolour(layer.paint[key], fixed);
      }
      darkStyle = style;
    } catch {
      return null;
    }
  }
  return JSON.parse(JSON.stringify(darkStyle));
}

// Sentinel-2 cloudless, EOX's yearly mosaic: 10 m pixels, keyless, and
// dated. The date is why it is this one and not a sharper undated mosaic:
// a replay can show the vegetation that stood before the fire instead of
// its scar — the 2024 mosaic already carries Viña 2024's, the 2023 one
// does not. 2016 is the first mosaic, 2025 the newest published (EOX WMTS
// capabilities, checked 2026-10-19).
const S2_FIRST = 2016, S2_LAST = 2025;

/** The mosaic for a map about `when` (an ISO time): the newest from a year
 *  before it, so none of it can show the fire itself. Without `when`, the
 *  newest. Before 2017 there is none from before, and the first is used
 *  with `after` set. */
function s2Mosaic(when) {
  const y = when ? new Date(when).getUTCFullYear() - 1 : S2_LAST;
  return { year: Math.max(S2_FIRST, Math.min(S2_LAST, y)), after: y < S2_FIRST };
}

// Esri World Imagery, for the one map where detail matters more than the
// date: the exposure map is read cell by cell against the streets and the
// houses, and at 10 m Sentinel-2 shows neither. Vantor imagery at 31–34 cm
// in Viña and Valparaíso, 50 cm in Concepción and 34 cm in rural Biobío,
// all from 2026 (Esri's metadata, checked 2026-10-20). Each place is its
// own capture, so the map has no one date to name. Native to zoom 19 in
// the cities and 18 in the countryside; past that Esri serves a "Map data
// not yet available" tile, and blankTile=false makes it a 404 instead, so
// MapLibre keeps stretching the level above.
const ESRI_IMAGERY = {
  type: "raster", tileSize: 256, maxzoom: 19,
  tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}?blankTile=false"],
  attribution: "Source: Esri, Vantor, Earthstar Geographics, and the GIS User Community",
};

// Which picture the satellite basemap is: "s2", dated, by default; a page
// that sets "esri" gets the sharp one, with street names over it.
let satelliteImagery = "s2";

/** The satellite style: the picture, relief shading from the AWS terrain
 *  tiles, and dark-matter's place names when it can be fetched. */
async function satellite(when) {
  const { year } = s2Mosaic(when), sharp = satelliteImagery === "esri";
  const layer = year === 2016 ? "s2cloudless_3857" : `s2cloudless-${year}_3857`;
  const style = {
    version: 8,
    sources: {
      imagery: sharp ? ESRI_IMAGERY : {
        type: "raster", tileSize: 256, maxzoom: 14,
        tiles: [`https://tiles.maps.eox.at/wmts/1.0.0/${layer}/default/g/{z}/{y}/{x}.jpg`],
        attribution: `<a href="https://s2maps.eu">Sentinel-2 cloudless ${year}</a> by ` +
          `EOX IT Services GmbH (Contains modified Copernicus Sentinel data ${year})`,
      },
      relief: {
        type: "raster-dem", encoding: "terrarium", tileSize: 256, maxzoom: 15,
        tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
        attribution: '<a href="https://registry.opendata.aws/terrain-tiles/">Terrain Tiles</a>',
      },
    },
    layers: [
      { id: "background", type: "background", paint: { "background-color": "#0A2E38" } },
      { id: "imagery", type: "raster", source: "imagery" },
      // Shadows in Petróleo, not black: black is the burn scar's.
      { id: "relief", type: "hillshade", source: "relief", paint: {
        "hillshade-exaggeration": 0.35,
        "hillshade-shadow-color": "rgba(6,34,43,0.6)",
        "hillshade-highlight-color": "rgba(255,255,255,0.12)",
        "hillshade-accent-color": "rgba(6,34,43,0.25)",
      } },
    ],
  };
  const dark = await darkMatter();
  if (dark) {
    // Place names only: the roads, rivers and coast are in the picture. The
    // sharp picture also gets the street names, since telling one street
    // from the next is what it is for. One colour with a heavy halo,
    // because the picture under them is busy.
    Object.assign(style, { glyphs: dark.glyphs, sprite: dark.sprite });
    style.sources.carto = dark.sources.carto;
    const named = sharp ? ["place", "transportation_name"] : ["place"];
    for (const l of dark.layers)
      if (l.type === "symbol" && named.includes(l["source-layer"]))
        style.layers.push({ ...l, paint: { ...l.paint,
          "text-color": "#EAF4F7", "text-halo-color": "rgba(6,34,43,0.85)",
          "text-halo-width": 1.4 } });
  }
  return style;
}

/** The style for STYLES[k]: a URL, or a style object for the recoloured
 *  dark one and the satellite one. `when` dates the satellite mosaic. The
 *  dark one falls back to the plain URL if it cannot be fetched. */
async function basemap(k, when) {
  k %= STYLES.length;
  if (k === SATELLITE) return satellite(when);
  if (k !== 0) return STYLES[k][1];
  return (await darkMatter()) || STYLES[0][1];
}

// Taps on the chip can outrun the styles they ask for. Only the latest is
// drawn, and never as a diff: MapLibre diffs against a style URL by
// fetching it with no way to cancel, so a slow one landed after the next
// tap's map and replaced it — the chip said satélite over the street map.
let basemapSeq = 0;

/** Switch `map` to STYLES[k]; false if a later call superseded this one. */
async function setBasemap(map, k, when) {
  const seq = ++basemapSeq;
  const style = await basemap(k, when);
  if (seq !== basemapSeq) return false;
  map.setStyle(style, { diff: false });
  return true;
}

/** The basemap's name as the chip shows it; the Sentinel-2 one says its
 *  year, because a mosaic is a picture of one year and not of today. */
function basemapName(k, when) {
  k %= STYLES.length;
  if (k !== SATELLITE) return STYLES[k][0];
  return satelliteImagery === "esri" ? "satélite" : `satélite ${s2Mosaic(when).year}`;
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
