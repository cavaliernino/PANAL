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

**Coverage.** GOES-19 sits at 75.2°W, almost on Chile's meridian. Every
Chilean latitude band from Arica to Magallanes came back **100% usable** —
zero pixels lost to the LZA or glint block-out zones. Verified with
`goes.blocked_fraction()`. Caveat: that is one scan at 18:00 local, and glint
block-out is a daytime, solar-angle effect, so coverage should be re-checked
across the diurnal cycle before the claim is treated as permanent.

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

One that costs credibility instead of time: satellites report **persistent
industrial thermal anomalies**. Chuquicamata and the northern smelters read
as permanent fires. Mask them before anything reaches a human.

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
