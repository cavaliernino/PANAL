# web — the PANAL map

The first phase where PANAL is visible. A static page: no backend, no API key,
no build step, no install.

```bash
python3 -m http.server 8000 --directory web
# http://localhost:8000              replay de Viña 2024
# http://localhost:8000/national.html  detección nacional en vivo
```

| Page | What it is |
|---|---|
| `index.html` | The Viña del Mar 2024 replay — the demo |
| `national.html` | Live national detection — the product |
| `panal.js` | Shared encoding rules, so the calibrated ramp cannot drift |

## What ships first: the Viña del Mar replay

`index.html` plays back the 2 February 2024 Viña del Mar / Quilpué fire from
GOES-East, at the satellite's native 10-minute cadence, on the same H3 grid
the live product uses. Scrub, play at 1× to 10×, click a cell for its
readings.

Regenerate the data with:

```bash
cd ingest
../.venv/bin/python scripts/build_replay.py --preset vina2024 -o ../web/data/vina2024.json
```

This is the artifact to open in the first conversation with CONAF and
SENAPRED. It shows the tempo layer doing the one thing it is for, on an event
everyone in the room remembers.

## The national view

`national.html` shows current fire detection across Chile: the latest GOES
scan rolled up by zoom (r5 → r6 → r7), VIIRS at r9 with an age filter from
6 hours to 7 days, and the inferred extent beneath. Refreshes every five
minutes and always states how old its data is.

Regenerate the snapshot with:

```bash
cd ingest
../.venv/bin/python scripts/build_national.py -o ../web/data/national.json
```

Run it on a schedule for a live view. The installed cron matches the GOES
full-disk cadence:

```
*/10 * * * * /Users/nino/Dev/PANAL/ingest/scripts/cron_national.sh
```

The wrapper logs to `data/cron_national.log`, caps that log at 1 MB, and
keeps failures in the log rather than mailing root. The snapshot write is
**atomic** — written beside the target then renamed — so a crash mid-write
leaves the previous snapshot intact instead of serving the page truncated
JSON. Running unattended every ten minutes, that will happen eventually.

On macOS, if the job silently never runs, check that `cron` has Full Disk
Access in System Settings → Privacy & Security.

### The empty state is the normal state

For eight months a year almost nothing is burning in Chile. Measured on
2026-09-20: **zero GOES detections in the current scan**, 16 VIIRS
detections in 24 hours, 562 cells across 7 days.

A fire map that looks broken when there is no fire is a badly designed fire
map. So "nothing detected" is a deliberate, confident state — it says so in
words, and it says the chain is alive: the last GOES scan arrived and was
processed. An empty map and a broken pipeline must never look the same.

### Why deck.gl here, and not in the replay

`H3HexagonLayer` takes H3 indices directly and builds the geometry on the
GPU. That is why the national snapshot ships cell ids instead of polygons,
and why it can afford resolutions the replay could not. At 50–200 hexagons
per frame the replay did not need any of this, and a 1.6 MB dependency for
that would have been decoration. At national scale it earns its place.

## Why MapLibre alone in the replay

**MapLibre GL** is the open fork of Mapbox GL — vector basemaps in WebGL, no
API key, no quota. **deck.gl** is Uber's data-visualisation layer that sits on
top of it, and its `H3HexagonLayer` renders H3 cells natively.

The replay draws 50–200 hexagons per frame, which a native MapLibre `fill`
layer does perfectly, with one less dependency and one less failure mode.
Its cell geometry is precomputed into the JSON, so that page needs no H3
library at all.

## Two resolutions on one map

The replay now carries both detection layers, and seeing them together is the
point:

| Layer | Pixel | H3 | Cell ⌀ | Cadence |
|---|---|---|---|---|
| GOES-East | 2 km | r7 | **2,244 m** | every 10 min |
| VIIRS | 375 m | r9 | **321 m** | 3-4 passes a day |

On 2 February 2024 the difference is stark. GOES saw the fire at **12:10
local**; the first VIIRS pass was **14:47**, two hours and thirty-seven
minutes later — and seven times sharper. A wide GOES hexagon says *something
is burning here, ten minutes ago*; the small VIIRS cells inside it say
*precisely here, two hours ago*.

VIIRS fixes persist until the next pass supersedes them, with their age shown
and a dimmed outline past an hour, so a stale precise fix never reads as a
current one. Toggle the layer from the stats panel.

Regenerating the VIIRS layer needs a free FIRMS MAP_KEY in `.env`:

```bash
cp .env.example .env    # then paste your key
```

Without it the replay still builds; it just has no precision layer.

## Basemaps

Switchable from the header chip, all keyless:

| Style | Source |
|---|---|
| oscuro | CARTO Dark Matter — default; fire colours read best on it |
| claro | CARTO Positron |
| callejero | OpenFreeMap Liberty |

A topographic style is worth adding — slope drives fire spread, so terrain is
operationally relevant, not decoration.

## Encoding rules this page follows

From [`../docs/roadmap.md`](../docs/roadmap.md):

- **Colour carries intensity, opacity carries confidence.** The FRP ramp runs
  pale yellow to deep red on a log scale; the evidence tier sets alpha.
- **Opacity never works alone.** The weakest tiers also get a dashed outline,
  because opacity alone fails WCAG and reads differently on light and dark
  basemaps.
- **Opacity is floored** so an uncertain cell never disappears into the
  basemap and silently becomes "nothing here".
- **No black.** In wildland fire operations the black is the burned area, a
  survival refuge. It is reserved for the burn scar.
- **Provenance is always on screen** — satellite, product, 2 km pixel,
  10-minute cadence — and the footer says plainly that geostationary fire
  data is provisional, and that a detection record is not a counterfactual.

## Next

- National live view: every Chilean H3 cell, current detections, deck.gl.
- WUI exposure layer (Phase 2), the preventive map.
- Official zones from the agency channel (Phase 5), visually distinct from
  anything PANAL derived.
