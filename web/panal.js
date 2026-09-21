/* Shared encoding rules for every PANAL map.
 *
 * These live in one file on purpose. The FRP ramp is calibrated against
 * measured data, and a copy of it in a second page would drift the moment
 * either was retuned.
 *
 * The rules themselves are set in docs/roadmap.md:
 *   - colour carries intensity, opacity carries confidence
 *   - the weak tiers get a second visual channel, never opacity alone
 *   - opacity is floored, so uncertain never renders as absent
 *   - no black: that is reserved for the burn scar
 */

// Calibrated against per-cell FRP observed in the Viña 2024 replay:
// median 254 MW, p90 1,259, max 3,195. A plain log10 ramp put the median
// already in the reds, washing the map hot and hiding growth. The floor
// spreads the low end so the median lands mid-scale.
const FRP_FLOOR = 20, FRP_MAX = 3200;

const FRP_STOPS = [
  [0, [253, 230, 138]], [0.30, [251, 191, 36]], [0.55, [249, 115, 22]],
  [0.78, [239, 68, 68]], [1, [185, 28, 28]],
];

function frpScale(mw) {
  return Math.max(0, Math.min(1,
    Math.log10(1 + Math.max(0, mw) / FRP_FLOOR) /
    Math.log10(1 + FRP_MAX / FRP_FLOOR)));
}

/** FRP in MW to an [r,g,b] triple. */
function frpRGB(mw) {
  const s = frpScale(mw);
  for (let k = 1; k < FRP_STOPS.length; k++) {
    if (s <= FRP_STOPS[k][0]) {
      const [a, ca] = FRP_STOPS[k - 1], [b, cb] = FRP_STOPS[k];
      const u = (s - a) / (b - a || 1);
      return ca.map((v, j) => Math.round(v + (cb[j] - v) * u));
    }
  }
  return FRP_STOPS[FRP_STOPS.length - 1][1].slice();
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

// Tiers that also get a dashed or dimmed outline, because opacity alone
// fails WCAG and reads differently on light and dark basemaps.
const WEAK = new Set(["low_probability", "cloud_contaminated"]);

// Keyless basemaps.
const STYLES = [
  ["oscuro", "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"],
  ["claro", "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"],
  ["callejero", "https://tiles.openfreemap.org/styles/liberty"],
];

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
