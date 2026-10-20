/* The exposure map, for the two pages that show it.
 *
 * wui.html ranks each region against itself. chile.html ranks every
 * region against the whole country, and without a region it shows the
 * summary: the whole country, summed up to large hexagons. The page sets
 * PAGE before loading this file — its scope, its regions, the region it
 * opens on (none, for the summary) and the summary's file.
 */

const $ = id => document.getElementById(id);
const nf = n => n.toLocaleString("es-CL");

// Column positions in the export (see ingest/scripts/export_wui_web.py).
const H = 0, HZ = 1, CS = 2, VIV = 3, PER = 4, PEND = 5, COMB = 6, EGR = 7,
      COMUNA = 8, PRIO = 9;

// From light blue to red: the ACHEZ brand light blue, the isotipo's
// yellow, two oranges and the red of the ACHEZ "Polygon" component.
// Light blue is the least exposed end, red the most fuel next to homes. It
// is the same on every basemap: the order is read by meaning, not by
// lightness. The hexagon is the component's: fill at 70%, a solid inner
// edge in the same colour, screen-blended over the dark basemap. No black
// (the burn scar).
const RAMP = [[100,217,242], [240,195,40], [242,135,5], [243,50,4], [167,6,4]];
const BREAKS = [25, 50, 75, 90];        // <25, 25–50, 50–75, 75–90, top 10%
const FILL_ALPHA = 179;                 // 0.7, as in the component
// Humo: a dark neutral, so "no fuel observed" can never pass for the
// palest, highest class.
const UNOBSERVED = [79, 96, 103];

// The census grid is adaptive: sparse rural entities sit in coarser cells
// (r8 down to r5) instead of being refined into precision nobody measured.
// Drawn at full strength, a 36 km² cell holding three houses would carry
// more visual weight than a dense hillside — area would read as people. So
// coarser cells are fainter, and outlined so faint never becomes absent.
const RES_ALPHA = { 9: 1, 8: .5, 7: .3, 6: .3, 5: .3 };
const resOf = h => h3.getResolution(h);

let D, byCell, map, overlay, mode = "hz", styleIdx = 0, selected = null, me = null;

// The satellite here is Esri's sub-metre picture, not the dated
// Sentinel-2 the other maps use: a cell is checked against the streets
// and the houses in it, and at 10 m neither shows.
satelliteImagery = "esri";

const cls = p => BREAKS.filter(b => p >= b).length;
const ramp = () => RAMP;
const val = r => mode === "hz" ? r[HZ] : r[CS];

// The selected cell is left out of the base layer and drawn only by "sel":
// screen blending only ever lightens, so a darker selected state drawn on
// top of the cell would come out lighter.
// On the satellite map the picture under the cell is the point — the
// houses, the slope and the vegetation the index is about — so the fill
// is halved and the solid edge carries the class.
function fill(r) {
  if (r[H] === selected) return [0, 0, 0, 0];
  const p = val(r), f = (RES_ALPHA[resOf(r[H])] ?? .3) * (styleIdx === SATELLITE ? .5 : 1);
  if (p == null) return [...UNOBSERVED, Math.round(140 * f)];
  return [...ramp()[cls(p)], Math.round(FILL_ALPHA * f)];
}

// The component's edge: solid, the cell's own colour. Coarse cells keep it
// a little stronger than their fill, so faint never reads as absent.
function edge(r) {
  if (r[H] === selected) return [0, 0, 0, 0];
  const p = val(r);
  if (p == null) return [...UNOBSERVED, 160];
  const f = RES_ALPHA[resOf(r[H])] ?? .3;
  return [...ramp()[cls(p)], Math.round(255 * Math.max(f, .45))];
}

// The edge is about a tenth of a resolution-9 hexagon, as drawn in the
// component (4 px inside a 68 px hexagon). Coarse cells keep that same
// width instead of scaling up: a thick rim on a 36 km² cell would give
// area the weight the faint fill took away.
const EDGE_M = h3.getHexagonEdgeLengthAvg(9, "m") * 0.18;
const edgeWidth = () => EDGE_M;

// Clicked: the component's second state — a darker fill and a lighter,
// thicker edge in the same hue.
const mix = (c, t, w) => c.map((v, j) => Math.round(v + (t[j] - v) * w));
function selFill(h) {
  const r = byCell.get(h), p = r && val(r);
  return p == null ? [0, 0, 0, 0] : [...mix(ramp()[cls(p)], [10, 46, 56], .45), FILL_ALPHA];
}
function selEdge(h) {
  const r = byCell.get(h), p = r && val(r);
  return p == null ? [245, 154, 85, 255] : [...mix(ramp()[cls(p)], [255, 255, 255], .5), 255];
}

// ---------------------------------------------------------------------------
// The summary: all of Chile, for chile.html with no region chosen.
//
// Column positions in it (see ingest/scripts/export_wui_chile.py): the
// homes and people in each cell, and how many of the homes sit in the
// country's top decile of hazard, of consequence, of both, or have no fuel
// observation at all.
const S_H = 0, S_VIV = 1, S_PER = 2, S_ND = 3, S_VHZ = 4, S_PHZ = 5,
      S_VCS = 6, S_VPR = 7, S_REG = 8, S_KM2 = 9;
let S = null;

// The colour is the homes in the top decile per km², not their count. A
// count would change meaning with the size of the hexagon, and the
// hexagons grow as the map zooms out; a density does not. The cut points
// split the hexagons that hold any such homes roughly into halves, then a
// quarter, an eighth and the rest (measured on the export). Consequence
// counts every home in a dense city block, so its cut points sit higher.
const DENSITY = { hz: [0.5, 2, 10], cs: [5, 50, 500] };

// Coarser as the map zooms out, so the country never draws as dust. Exact:
// the export sums, and so does this.
const sumRes = z => z < 5.5 ? 4 : z < 7.5 ? 5 : 6;
const sumCache = {};

/** The summary at resolution `res`: every cell finer than it summed into
 *  its parent there. A summed cell is filed under the region of the cell
 *  that brought it the most homes. */
function summaryAt(res) {
  if (sumCache[res]) return sumCache[res];
  const acc = new Map(), top = new Map();
  for (const r of S.rows) {
    const k = resOf(r[S_H]) > res ? h3.cellToParent(r[S_H], res) : r[S_H];
    let a = acc.get(k);
    if (!a) acc.set(k, a = [k, 0, 0, 0, 0, 0, 0, 0, r[S_REG], h3.cellArea(k, "km2")]);
    for (let j = S_VIV; j <= S_VPR; j++) a[j] += r[j];
    if (r[S_VIV] > (top.get(k) ?? -1)) { a[S_REG] = r[S_REG]; top.set(k, r[S_VIV]); }
  }
  return sumCache[res] = { rows: [...acc.values()], by: acc };
}

const sumCount = r => r[mode === "hz" ? S_VHZ : S_VCS];
// No home in the top decile and at least half with no fuel observation:
// unknown, not low.
const sumUnobserved = r => mode === "hz" && !r[S_VHZ] && 2 * r[S_ND] >= r[S_VIV];
const sumCls = r => sumCount(r) ? 1 + DENSITY[mode].filter(b => sumCount(r) / r[S_KM2] >= b).length : 0;

function sumFill(r) {
  if (r[S_H] === selected) return [0, 0, 0, 0];
  const f = styleIdx === SATELLITE ? .5 : 1;
  if (sumUnobserved(r)) return [...UNOBSERVED, Math.round(110 * f)];
  const k = sumCls(r);
  // Inhabited with none in the top decile: there, faint, so the country
  // reads as the backdrop and the exposure as the figure.
  return [...RAMP[k], Math.round((k ? FILL_ALPHA : 70) * f)];
}

function sumEdge(r) {
  if (r[S_H] === selected) return [255, 255, 255, 255];
  if (sumUnobserved(r)) return [...UNOBSERVED, 160];
  const k = sumCls(r);
  return [...RAMP[k], k ? 230 : 110];
}

function summaryLayers() {
  const { H3HexagonLayer, ScatterplotLayer } = deck;
  const res = sumRes(map.getZoom());
  const out = [new H3HexagonLayer({
    id: "sum", data: summaryAt(res).rows, getHexagon: r => r[S_H],
    extruded: false, stroked: true, getFillColor: sumFill, getLineColor: sumEdge,
    lineWidthMinPixels: .5, lineWidthMaxPixels: 3,
    getLineWidth: r => r[S_H] === selected ? 3 : 1, lineWidthUnits: "pixels",
    updateTriggers: { getFillColor: [mode, styleIdx, selected],
                      getLineColor: [mode, styleIdx, selected],
                      getLineWidth: [selected] },
  })];
  if (me) out.push(new ScatterplotLayer({
    id: "me", data: [me], getPosition: d => d, getRadius: 7,
    radiusUnits: "pixels", getFillColor: [56, 189, 248, 255],
    stroked: true, getLineColor: [255, 255, 255, 255], lineWidthMinPixels: 2,
  }));
  return out;
}

function findSummary(lat, lon) {
  const { by } = summaryAt(sumRes(map.getZoom()));
  for (let r = sumRes(map.getZoom()); r >= 3; r--) {
    const c = h3.latLngToCell(lat, lon, r);
    if (by.has(c)) return c;
  }
  return null;
}

function showSummaryCard(h, note) {
  const r = h && summaryAt(sumRes(map.getZoom())).by.get(h);
  selected = r ? h : null;
  if (!r) return openCard(`<div class="where">${note}</div>
    <div class="why" style="margin-top:6px">Aquí el Censo 2024 no registra
    viviendas. <b>Eso no significa que no haya peligro.</b></div>`);
  const reg = S.meta.regions[r[S_REG]], km2 = r[S_KM2];
  const [lat, lon] = h3.cellToLatLng(h);
  let html = `<div class="where">${reg.name}${note ? " · " + note : ""} ·
    hexágono de ${nf(Math.round(km2))} km²</div>
    <div class="row"><span>Viviendas</span><b>${nf(r[S_VIV])}</b></div>
    <div class="row"><span>En el 10% de mayor amenaza de Chile</span><b>${nf(r[S_VHZ])}</b></div>
    <div class="why">${nf(r[S_PHZ])} personas</div>`;
  if (r[S_ND]) html += `<div class="why">${nf(r[S_ND])} viviendas sin datos de
    combustible: no se clasifican, y eso no significa que estén a salvo.</div>`;
  html += `<div class="row"><span>En el 10% de mayor consecuencia
    <small style="color:var(--warn)">sin validar</small></span><b>${nf(r[S_VCS])}</b></div>
    <div class="row"><span>En celdas prioritarias</span><b>${nf(r[S_VPR])}</b></div>
    <a class="go" href="?r=${reg.id}&c=${lat.toFixed(4)},${lon.toFixed(4)}">Ver las
    celdas de esta zona →</a>`;
  if (!reg.tested) html += `<div class="why" style="margin-top:8px">El índice no
    se ha probado con incendios en ${reg.name}.</div>`;
  openCard(html);
  requestAnimationFrame(() => reveal(h));
}

// Each region beside the rest, ordered by its homes in the country's top
// decile of hazard. The regions it was tested in are marked: everywhere
// else it is the same arithmetic, untested.
function drawRegionTable() {
  const regs = S.meta.regions.filter(r => !r.missing)
    .sort((a, b) => b.viv_hz - a.viv_hz);
  $("rtab").innerHTML = `<span>Región</span><span>viviendas</span><span>personas</span>` +
    regs.map(r => `<a href="?r=${r.id}">${r.name}${r.tested ? ' <i>probado</i>' : ""}</a>` +
      `<b>${nf(r.viv_hz)}</b><b>${nf(r.per_hz)}</b>`).join("") +
    S.meta.regions.filter(r => r.missing)
      .map(r => `<a class="miss">${r.name}</a><b class="miss">sin calcular</b><b></b>`).join("");
}

// ---------------------------------------------------------------------------

function layers() {
  if (S) return summaryLayers();
  const { H3HexagonLayer, ScatterplotLayer } = deck;
  const out = [
    new H3HexagonLayer({
      id: "cells", data: D.rows, getHexagon: r => r[H],
      extruded: false, stroked: true,
      getFillColor: fill,
      // Unobserved and coarse cells get a visible edge, so "no data" never
      // reads as "low" and "faint" never reads as "nothing here".
      getLineColor: edge,
      getLineWidth: edgeWidth, lineWidthUnits: "meters",
      lineWidthMinPixels: .6, lineWidthMaxPixels: 4,
      updateTriggers: { getFillColor: [mode, styleIdx, selected],
                        getLineColor: [mode, styleIdx, selected] },
    }),
    new H3HexagonLayer({
      id: "prio", data: D.rows.filter(r => r[PRIO]), getHexagon: r => r[H],
      extruded: false, filled: false, stroked: true,
      getLineColor: STYLES[styleIdx][2] ? [255, 255, 255, 235] : [17, 24, 39, 235],
      lineWidthMinPixels: 2, updateTriggers: { getLineColor: [styleIdx] },
    }),
  ];
  if (selected) out.push(new H3HexagonLayer({
    id: "sel", data: [selected], getHexagon: h => h, extruded: false,
    filled: true, stroked: true, getFillColor: selFill, getLineColor: selEdge,
    getLineWidth: h => h3.getHexagonEdgeLengthAvg(resOf(h), "m") * 0.22, lineWidthUnits: "meters",
    lineWidthMinPixels: 3, lineWidthMaxPixels: 6,
  }));
  if (me) out.push(new ScatterplotLayer({
    id: "me", data: [me], getPosition: d => d, getRadius: 7,
    radiusUnits: "pixels", getFillColor: [56, 189, 248, 255],
    stroked: true, getLineColor: [255, 255, 255, 255], lineWidthMinPixels: 2,
  }));
  return out;
}

function render() { overlay.setProps({ layers: layers() }); }

function setMode(m) {
  mode = m;
  $("m-hz").setAttribute("aria-pressed", m === "hz");
  $("m-cs").setAttribute("aria-pressed", m === "cs");
  $("leg-hz").hidden = m !== "hz";
  $("leg-cs").hidden = m !== "cs";
  drawRamp();
  render();
}

function drawRamp() {
  $("ramp").innerHTML = ramp().map((c, k) =>
    `<i style="background:rgba(${c.join(",")},${(S && !k ? 70 : FILL_ALPHA) / 255})"></i>`).join("");
  if (!S) return;
  const b = DENSITY[mode].map(v => v.toLocaleString("es-CL"));
  $("ramp-lbl").innerHTML = `<span>ninguna</span><span>&lt; ${b[0]}</span>` +
    `<span>${b[0]}–${b[1]}</span><span>${b[1]}–${b[2]}</span><span>&gt; ${b[2]}</span>`;
}

async function setStyle(k) {
  styleIdx = k % STYLES.length;
  $("c-style").textContent = "mapa: " + basemapName(styleIdx);
  if (!await setBasemap(map, styleIdx)) return;
  $("map").classList.toggle("screen", styleIdx === 0);
  drawRamp();
  render();
}

const rankText = p => p >= 90 ? `entre el ${Math.max(1, 100 - p)}% más alto` : `percentil ${p}`;

// Components are described by where they sit among the cells ranked with
// this one — the region's, or the country's — not by labels like "high"
// or "difficult": those would need thresholds nobody has validated. A
// region ranked against the country brings the country's quantiles in its
// meta; otherwise its own cells are sorted once at load.
const SORTED = {};
function share(col, v) {
  const q = D.meta.ref_quantiles?.[col];
  if (q) return q.slice(1).filter(x => x < v).length;
  const a = SORTED[col];
  let lo = 0, hi = a.length;
  while (lo < hi) { const mid = (lo + hi) >> 1; a[mid] < v ? lo = mid + 1 : hi = mid; }
  return Math.round(100 * lo / a.length);
}
const among = () => PAGE.scope === "chile" ? "las celdas de Chile" : "las celdas";

function openCard(html) {
  const card = $("card");
  card.innerHTML = `<button class="x" aria-label="Cerrar">×</button>` + html;
  card.hidden = false;
  card.querySelector(".x").onclick = closeCard;
  $("sheet").classList.add("open");
  $("sheet").scrollTop = 0;
  render();
}

function showMsg(text) {
  selected = null;
  openCard(`<div class="where">${text}</div>`);
}

// On a phone the open sheet covers most of the screen. Bring the cell into
// the strip still visible above it, or the card describes a hexagon nobody
// can see.
function reveal(h) {
  if (window.innerWidth > 640) return;
  const [lat, lng] = h3.cellToLatLng(h);
  const covered = $("sheet").getBoundingClientRect().height;
  map.easeTo({ center: [lng, lat], offset: [0, -covered / 2], duration: 350 });
}

function showCard(h, note) {
  selected = h;
  const r = byCell.get(h);
  let html = "";
  if (!r) {
    html += `<div class="where">${note}</div>
      <div class="why" style="margin-top:6px">El índice solo califica celdas
      donde el Censo 2024 registró viviendas. <b>Que una celda no aparezca
      no significa que no haya peligro.</b></div>`;
  } else {
    const comuna = r[COMUNA] != null ? D.meta.comunas[r[COMUNA]] : "—";
    const km2 = h3.cellArea(r[H], "km2");
    html += `<div class="where">${comuna}${note ? " · " + note : ""}</div>`;
    if (resOf(r[H]) < 9) html += `<div class="why">Celda rural de
      ${km2 >= 10 ? Math.round(km2) : km2.toFixed(1)} km²: sus valores son el
      promedio de pocas viviendas dispersas, no de un punto.</div>`;
    if (r[HZ] == null) {
      html += `<div class="row"><span>Amenaza</span><b>sin clasificar</b></div>
        <div class="why">No hay datos de combustible para esta celda: las
        imágenes de verano salieron con nubes. <b>Eso no significa que sea
        segura.</b></div>`;
    } else {
      html += `<div class="row"><span>Amenaza</span><b>${rankText(r[HZ])}</b></div>
        <div class="why">pendiente ${r[PEND] ?? "—"}° · más combustible que
        el ${share("comb", r[COMB])}% de ${among()}</div>`;
    }
    html += `<div class="row"><span>Consecuencia <small style="color:var(--warn)">
      sin validar</small></span><b>${rankText(r[CS])}</b></div>
      <div class="why">${nf(r[VIV])} viviendas · ${nf(r[PER])} personas ·
      ${r[EGR] == null ? "salida: sin datos en OpenStreetMap"
        : `salida más difícil que en el ${share("egr", r[EGR])}% de ${among()}`}</div>`;
    if (r[PRIO]) html += `<span class="tag u">prioridad · consecuencia sin validar</span>`;
  }
  openCard(html);
  if (h) requestAnimationFrame(() => reveal(h));
}

function closeCard() {
  selected = null;
  $("card").hidden = true;
  render();
}

// The finest indexed cell containing a point. Cells come in several sizes,
// so a point in the countryside may only be covered by a coarse one.
function findCell(lat, lon) {
  const resMin = Math.min(...Object.keys(D.meta.res_cells || { 5: 0 }).map(Number));
  for (let r = D.meta.res_max; r >= resMin; r--) {
    const c = h3.latLngToCell(lat, lon, r);
    if (byCell.has(c)) return c;
  }
  return null;
}

function placeMe(lat, lon) {
  me = [lon, lat];
  if (S) {
    map.jumpTo({ center: me, zoom: 8 });
    return showSummaryCard(findSummary(lat, lon), "tu ubicación");
  }
  map.jumpTo({ center: me, zoom: 14.5 });
  const found = findCell(lat, lon);
  if (found) return showCard(found, "tu ubicación");
  const h = h3.latLngToCell(lat, lon, D.meta.res_max);
  const near = h3.gridDisk(h, 20).some(c => findCell(...h3.cellToLatLng(c)));
  showCard(h, near ? "tu ubicación: aquí el censo no registra viviendas"
    : `tu ubicación está fuera de este mapa (${D.meta.region})`);
}

// Location never leaves the device: the cell is computed here, and nothing
// about it is sent anywhere.
function locate() {
  if (!navigator.geolocation) return showMsg("Este navegador no permite obtener la ubicación.");
  $("locate").textContent = "◎ Buscando…";
  navigator.geolocation.getCurrentPosition(pos => {
    $("locate").textContent = "◎ Cerca de mí";
    placeMe(pos.coords.latitude, pos.coords.longitude);
  }, err => {
    $("locate").textContent = "◎ Cerca de mí";
    showMsg(err.code === 1 ? "No diste permiso de ubicación. Puedes tocar el mapa para ver una celda."
                           : "No se pudo obtener la ubicación.");
  }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 });
}

const PARAMS = new URLSearchParams(location.search);
const REGIONS = PAGE.regions;
const REGION = (r => REGIONS[r] ? r : PAGE.home)(PARAMS.get("r"));

// The region picker: buttons for two regions, a list for sixteen.
function drawPicker() {
  const el = $("regs");
  if (el.tagName === "SELECT") {
    el.innerHTML = (PAGE.summary ? `<option value="">Todo Chile</option>` : "") +
      Object.entries(REGIONS).map(([id, r]) =>
        `<option value="${id}"${id === REGION ? " selected" : ""}>${r.label}</option>`).join("");
    el.onchange = () => location.search = el.value ? "?r=" + el.value : "";
    return;
  }
  el.innerHTML = Object.entries(REGIONS).map(([id, r]) =>
    `<button data-r="${id}" aria-pressed="${id === REGION}">${r.label}</button>`).join("");
  for (const b of el.querySelectorAll("button"))
    b.onclick = () => { if (b.dataset.r !== REGION) location.search = "?r=" + b.dataset.r; };
}

// Every fire tested, not the best one. The same bar validate_wui.py uses
// for its verdict decides which count as working.
const works = e => e.lift >= 1.5;

function drawValidation(m, regionId) {
  const ev = m.validation.events;
  $("hz-val").textContent = `${ev.filter(works).length} de ${ev.length} incendios`;
  $("res-val").textContent = `${ev.filter(works).length} de ${ev.length}`;
  $("val").innerHTML = ev.map(e =>
    `<span class="${e.region === regionId ? "here" : ""}">${e.year}</span>` +
    `<span class="${e.region === regionId ? "here" : ""}">${e.event.split(/[:,]/)[0]}</span>` +
    `<b class="${works(e) ? "" : "miss"}">` +
    `${e.lift.toLocaleString("es-CL", { maximumFractionDigits: 1 })}×</b>`).join("");
  return ev.filter(e => e.region === regionId);
}

function drawPriority(pr) {
  $("s-cells").textContent = nf(pr.cells);
  $("s-viv").textContent = nf(pr.viviendas);
  $("s-per").textContent = nf(pr.personas);
  // Where OSM maps no road, consequence is scored without the exit term.
  // Said here, because it decides how far the count can be read.
  if (pr.egreso_conocido < pr.cells) $("s-egr").textContent =
    `Solo en ${nf(pr.egreso_conocido)} de ${nf(pr.cells)} se conoce la salida. En las ` +
    `demás, OpenStreetMap no tiene las calles y la consecuencia se calcula sin ese dato.`;
}

// Some panel pieces belong to the summary and some to a region; the page
// marks them, and only one set shows.
function showOnly(which) {
  for (const el of document.querySelectorAll("[data-only]"))
    el.hidden = el.dataset.only !== which;
}

async function load(file) {
  try {
    const res = await fetch(file);
    if (!res.ok) throw new Error(res.status);
    return await res.json();
  } catch (e) {
    $("loading").textContent = "No se pudo cargar el índice. Revisa la conexión.";
    return null;
  }
}

// The whole country: the mainland from Arica to Cabo de Hornos, with room
// for the panel beside it on a wide screen and the sheet under it on a phone.
const CHILE = [[-76.5, -56], [-66.4, -17.4]];
const pad = () => window.innerWidth > 640
  ? { top: 110, bottom: 30, left: 340, right: 30 }
  : { top: 100, bottom: 170, left: 20, right: 20 };

async function startSummary() {
  showOnly("summary");
  map.fitBounds(CHILE, { padding: pad(), duration: 0 });
  if (!(S = await load(PAGE.summary))) return;
  const m = S.meta;
  const tested = m.regions.filter(r => r.tested).map(r => r.name);
  const top = m.regions.reduce((t, r) => [t[0] + (r.viv_hz || 0), t[1] + (r.per_hz || 0)], [0, 0]);
  $("h-sub").textContent = `Chile · ${nf(m.cells)} celdas habitadas en ${m.regions.length} regiones`;
  drawValidation(m, null);
  $("res-reg").textContent = ` Todos son de ${tested.slice(0, -1).join(", ")} y ` +
    `${tested.at(-1)}: en las otras ${m.regions.length - tested.length} regiones es el ` +
    `mismo cálculo, sin probar.`;
  $("t-viv").textContent = nf(top[0]);
  $("t-per").textContent = nf(top[1]);
  drawPriority(m.priority);
  drawRegionTable();
  $("src").innerHTML = Object.values(m.sources).join("<br>") +
    `<br>Hexágonos H3 r${m.res} y mayores · ${nf(m.unobserved)} celdas sin combustible observado` +
    (m.partial.length ? `<br><b style="color:var(--warn)">Faltan ${m.partial.join(", ")}</b>` : "") +
    `<br>Generado ${new Date(m.generated).toLocaleDateString("es-CL")}`;
  drawRamp();
  render();
  $("loading").remove();

  let res = sumRes(map.getZoom());
  map.on("zoomend", () => {
    if (sumRes(map.getZoom()) === res) return;
    res = sumRes(map.getZoom());
    if (selected) closeCard(); else render();
  });
  map.on("click", e => {
    const h = findSummary(e.lngLat.lat, e.lngLat.lng);
    if (h) showSummaryCard(h); else if (selected) closeCard();
  });
}

async function startRegion() {
  const R = REGIONS[REGION];
  showOnly("region");
  if (!(D = await load(R.file))) return;
  byCell = new Map(D.rows.map(r => [r[H], r]));
  for (const [k, c] of [["comb", COMB], ["egr", EGR]])
    SORTED[k] = Float64Array.from(D.rows.map(r => r[c]).filter(v => v != null)).sort();
  const m = D.meta;

  // Where to look: a place the summary sent us to, else the region's own
  // extent, else the view the page set for it.
  const at = (PARAMS.get("c") || "").split(",").map(Number);
  if (at.length === 2 && at.every(Number.isFinite)) map.jumpTo({ center: [at[1], at[0]], zoom: 12 });
  else if (m.view) map.fitBounds(m.view.bounds, { padding: pad(), duration: 0 });

  $("h-sub").textContent = `${m.region} · ${nf(m.cells)} celdas habitadas`;
  const here = drawValidation(m, m.region_id);
  const x = v => v.toLocaleString("es-CL", { maximumFractionDigits: 1 }) + "×";
  if (here.length) $("res-reg").textContent =
    ` En esta región, en ${here.filter(works).length} de ${here.length}: ` +
    here.map(e => `${x(e.lift)} (${e.year})`).join(", ") + "." + (R.note ? " " + R.note : "");
  else if (PAGE.scope === "chile") $("res-reg").textContent =
    " En esta región no lo hemos probado con ningún incendio: es el mismo cálculo, sin verificar.";
  drawPriority(m.priority);
  $("src").innerHTML = Object.values(m.sources).join("<br>") +
    `<br>Celdas H3 r${Math.min(...Object.keys(m.res_cells || { 5: 0 }).map(Number))}–r${m.res_max} · ${nf(m.unobserved)} sin combustible observado` +
    `<br>Generado ${new Date(m.generated).toLocaleDateString("es-CL")}`;
  drawRamp();
  render();
  $("loading").remove();

  // Any tap on the map: a cell in the index gets its card; elsewhere, say
  // plainly that the index has nothing there rather than staying silent.
  map.on("click", e => {
    const h = findCell(e.lngLat.lat, e.lngLat.lng);
    if (h) showCard(h); else if (selected) closeCard();
  });
}

(async function init() {
  const R = REGIONS[REGION];
  drawPicker();

  map = new maplibregl.Map({
    container: "map", style: await basemap(0),
    center: R?.center ? (window.innerWidth > 640 ? R.center : R.centerPhone) : [-71, -36],
    zoom: R?.zoom ?? 4, attributionControl: { compact: true },
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
  overlay = new deck.MapboxOverlay({ interleaved: false, layers: [] });
  map.addControl(overlay);

  $("m-hz").onclick = () => setMode("hz");
  $("m-cs").onclick = () => setMode("cs");
  $("c-style").onclick = () => setStyle(styleIdx + 1);
  $("locate").onclick = locate;
  $("grip").onclick = () => $("sheet").classList.toggle("open");

  await (R ? startRegion() : startSummary());
})();
