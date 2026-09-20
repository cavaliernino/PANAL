# web — the PANAL map

The first phase where PANAL is visible. A static page: no backend, no API key,
no build step, no install.

```bash
python3 -m http.server 8000 --directory web
# http://localhost:8000
```

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

## Why MapLibre and not deck.gl, yet

**MapLibre GL** is the open fork of Mapbox GL — vector basemaps in WebGL, no
API key, no quota. **deck.gl** is Uber's data-visualisation layer that sits on
top of it, and its `H3HexagonLayer` renders H3 cells natively.

deck.gl is the right tool for the national view, where Chile at r7 is
hundreds of thousands of cells and GPU aggregation earns its keep. It is not
the right tool for this replay, which draws 50–200 hexagons per frame — a
native MapLibre `fill` layer does that perfectly, with one less dependency
and one less failure mode. The cell geometry is precomputed into the JSON, so
the page needs no H3 library at all.

deck.gl comes in with the national layer, not before.

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
