# ingest — ETL pipelines

Pulls each source, normalises it onto the H3 grid and loads PostGIS. One module
per source, each idempotent and re-runnable, scheduled via GitHub Actions.

| Source | Cadence | Notes |
|---|---|---|
| NASA FIRMS active fire | several times daily | no API key; regional CSV; **clip to real geometry, not a bbox** |
| MINSAL SADU respiratory | weekly | ~65 MB parquet; **comma decimal separator** in lat/lon |
| SINCA air quality | hourly | PM2.5/PM10 per station; validates smoke dispersion |
| NASA POWER | daily | per H3 centroid, cached |
| CONAF fire statistics | per season | ground truth on burned area and cause |
| Censo 2024 (INE) | once | block level → H3, static reference |
| Establecimientos de Salud | monthly | distance-to-care term |

See [`../docs/data-sources.md`](../docs/data-sources.md) for verified schemas
and the parsing traps. Three of them will cost you a day each if you meet them
the hard way:

1. SADU lat/lon parse to **100% null** if read without `str.replace(",", ".")`.
2. Four of SADU's twelve causes are **subtotals** that double-count when summed.
3. A bounding box over Chile is **90% Argentina and Bolivia**. Clip against the
   INE census cartography.

And one that will cost you credibility rather than time: FIRMS reports
**persistent industrial thermal anomalies** — Chuquicamata and the northern
smelters read as permanent fires. Mask them before anything alerts a human.

## Build order

FIRMS comes first. Chile's fire season opens around November and the pipeline
should be capturing the 2026–27 season live rather than backfilling it. That
is the only externally imposed deadline in the project.

## Status

Not implemented. Phase 2.
