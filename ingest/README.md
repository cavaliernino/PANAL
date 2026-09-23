# ingest — ETL pipelines

Pulls each source, normalises it onto the H3 grid and loads PostGIS. One module
per source, each idempotent and re-runnable, scheduled via GitHub Actions.

| Source | Cadence | Status | Notes |
|---|---|---|---|
| **GOES-East ABI FDC** | **every 10 min** | ✅ **working** | the tempo layer; 2 km, provisional, high-confidence filtering |
| **NASA FIRMS VIIRS/MODIS** | several times daily | ✅ **working** | the precision layer; VIIRS 375 m → H3 r9. Keyless for the last 7 days; archive needs a free MAP_KEY |
| OpenStreetMap roads | once, refreshed | | static egress capacity |
| TomTom Traffic | live, during events | | free tier; OK over non-TomTom basemaps |
| Waze for Cities | every 2 min | | needs the agency partnership |
| MINSAL SADU respiratory | weekly | | ~65 MB parquet; **comma decimal separator** in lat/lon |
| SINCA air quality | hourly | | PM2.5/PM10 per station |
| NASA POWER | daily | | per H3 centroid, cached |
| CONAF fire statistics | per season | | ground truth on burned area and cause |
| Censo 2024 (INE) | once | | block level → H3 |
| Establecimientos de Salud | monthly | | distance-to-care term |

---

## Running it

```bash
python -m venv ../.venv && ../.venv/bin/pip install -r requirements.txt

# latest scan
../.venv/bin/python -m panal_ingest.pipeline

# backfill the last 6 hours
../.venv/bin/python -m panal_ingest.pipeline --hours 6

# replay a past fire at its native cadence
../.venv/bin/python scripts/backfill_event.py --preset vina2024
```

Output lands in `data/processed/` as parquet: raw detections, plus the H3
aggregate at the chosen resolution (default r7, ~5.2 km² per cell — larger
than a 2 km GOES pixel, so a cell never implies more precision than the
sensor has).

---

## What is verified, and how

Measured on 2026-09-20 against live and archive data, not from documentation:

**Latency.** A full-disk file covering 22:00:20–22:09:51 UTC was readable from
the public bucket at 22:11 — roughly **one minute after the scan closed**.
That is better than FIRMS's ~20–30 minute republication of the same product.
Files are ~1.8 MB and download in about 1.5 s.

**Coverage, across a full day.** GOES-19 sits at 75.2°W, almost on Chile's
meridian. Sampling one scan per hour for 24 hours, every Chilean latitude
band from Arica to Magallanes came back **100% usable at every hour** — zero
pixels lost to the LZA or glint block-out zones, minimum and mean both
100.0%. The earlier single-scan measurement is now confirmed across the
diurnal cycle, which mattered because glint block-out is a solar-angle
effect. Re-run with `scripts/check_goes_coverage.py`.

**Geometry.** Chile clipping is tested against known points: Santiago, Viña
del Mar, Punta Arenas, Rapa Nui and Chuquicamata accepted; Mendoza,
Bariloche, La Paz and open ocean rejected. Mendoza and Bariloche are exactly
the false positives that made the bounding-box approach 90% wrong.

**Detection, against a known event.** Replaying 2 February 2024 over
Valparaíso, GOES-16 first saw the Viña del Mar / Quilpué fire at **15:10 UTC,
12:10 local** — one pixel, 170 MW — and the file was public about ten minutes
later. Growth was monotonic and unambiguous: 4 pixels by 12:30, 10 by 14:00,
42 and 21 GW by 18:20.

> What that does **not** establish is a counterfactual. CONAF has its own
> detection and the public calls 130; the satellite signal existing early
> does not by itself mean anyone would have learned anything new from it.
> Whether this adds to what the agencies already had is a question for them,
> and it is the right first question to ask in that conversation.

---

## Traps

Three that will cost you a day each:

1. SADU lat/lon parse to **100% null** without `str.replace(",", ".")`.
2. Four of SADU's twelve causes are **subtotals** that double-count when summed.
3. A bounding box over Chile is **90% Argentina and Bolivia**.
4. The **INE ArcGIS Hub "Comunas de Chile" layer uses cartographic insets.**
   It places Isla de Pascua at about (-73.9, -33.1) and Juan Fernández at
   (-73.9, -33.4) — boxes drawn beside the mainland for map layout, not
   geodetic positions. Clipping against it would drop every Rapa Nui
   detection and accept open ocean off Valparaíso instead. It is also missing
   5 of 346 comunas, including Antártica. The companion OCUC "DPA 2026"
   layer is line geometry with no comuna code, so it cannot clip either.
   `tests/test_chile.py` guards against adopting a boundary with this defect.

One that costs credibility instead of time: satellites report **persistent
industrial thermal anomalies**. Chuquicamata and the northern smelters read
as permanent fires. This is now handled — see below — but the mask must be
rebuilt each season, because industrial sites open and close.

## The industrial anomaly mask

```bash
export FIRMS_MAP_KEY=...
python scripts/build_anomaly_mask.py --months 12
```

Built from a year of VIIRS archive: 110,757 detections, 54,104 inside Chile,
31,032 r9 cells examined, **63 flagged across 12 sites** — El Teniente,
Chuquicamata, the Ventanas and Coloso complexes among them.

A cell is flagged when all three hold: **≥20 distinct days**, **≥4 calendar
months**, **≥3 off-season days** (April–October, when nothing is burning).

The middle criterion alone was not enough, and finding that out mattered.
Months-only flagged 38 cells in the central valley, where recurring *quemas
agrícolas* are real fire that must never be masked. The separator is days in
the *same* cell: El Teniente shows 196, Chuquicamata 213, while agricultural
burning recurs across a zone but moves between fields and tops out at 9 or 10
days anywhere. Adding the day threshold dropped the mask from 170 cells to
63 and removed every agricultural false positive while keeping every
industrial site.

**The mask flags, it never deletes.** A real fire can start at a mine, in its
yards, or in the scrub beside it. Silently dropping detections there would
build a blind spot exactly where industrial ignition sources are
concentrated, so flagged cells stay in the data, render in slate outside the
FRP ramp, carry their own toggle, and are merely kept out of headline counts.

The thresholds deliberately under-mask. Industrial noise that leaks through
stays visible and reviewable; a suppressed real fire does not.

And one that is easy to miss: **GOES-East changed satellites on 2025-04-07.**
Backfill before that date must read `noaa-goes16`, after it `noaa-goes19`.
`goes.bucket_for()` handles this; do not hardcode a bucket.

---

## Resolution

Each source is indexed at the H3 level its sensor actually justifies, so a
cell never claims more precision than the pixel behind it:

| Source | Pixel | Level | Cell ⌀ / pixel |
|---|---|---|---|
| GOES-East ABI | 2 km | r7 | 1.41 |
| VIIRS | 375 m | r9 | 1.07 |

`pipeline.rollup()` coarsens up the hierarchy for wider viewports. It is
exact — verified lossless across the Viña replay, 586,568.6 MW and 1,357
detections identical at r5, r6 and r7. **Refining down raises**, because
rendering a 2 km pixel as 400 m cells would invent precision.

## Tests

```bash
cd ingest && ../.venv/bin/python -m pytest tests -q
```

Territory clipping and the anomaly mask both decide what a human never sees,
so both are pinned down: 23 points inside Chile including every insular
territory, 10 near misses outside, and the mask rule against a smelter, a
two-week megafire, recurring agricultural burning and summer-only
persistence.

## Layout

```
panal_ingest/
  goes.py       S3 listing, ABI fixed-grid geolocation, mask → detections
  viirs.py      FIRMS VIIRS/MODIS — precision layer, r9
  power.py      NASA POWER weather and the 30-30-30 factor
  chile.py      territory clipping against real geometry
  pipeline.py   fetch → extract → clip → H3 → parquet, plus rollup()
  reference/    boundary geometry (provisional, see its README)
scripts/
  backfill_event.py   replay a past fire at 10-minute cadence
  build_replay.py     export a replay dataset for the web map
```

`goes.geolocate()` reads the projection parameters from each file's own
`goes_imager_projection` variable rather than hardcoding them, so it keeps
working if the satellite is repositioned.
