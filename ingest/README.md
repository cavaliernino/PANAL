# ingest — ETL pipelines

Pulls each source, normalises it onto the H3 grid and loads PostGIS. One module
per source, each idempotent and re-runnable, scheduled weekly via GitHub
Actions.

| Source | Cadence | Notes |
|---|---|---|
| MINSAL SADU respiratory | weekly | ~65 MB parquet; **comma decimal separator** in lat/lon |
| NASA POWER | daily | per H3 centroid, cached |
| Censo 2024 (INE) | once | block level → H3, static reference |
| Establecimientos de Salud | monthly | distance-to-care term |

See [`../docs/data-sources.md`](../docs/data-sources.md) for verified schemas
and the parsing traps.

## Status

Not implemented. Phase 2.
