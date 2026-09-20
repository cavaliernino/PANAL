# engine — the PANAL risk index

A pure library. No database, no network, no filesystem. It takes dataframes in
and returns scored H3 cells out, so the part of PANAL that has to be correct
can be tested in milliseconds.

Implements the specification in [`../docs/risk-model.md`](../docs/risk-model.md).

## Responsibilities

- H3 aggregation of point observations, with catchment decay
- Per-capita normalisation against Censo 2024
- Seasonal baselines from 2014–2024 and excess-over-expected scoring
- Component scoring (health / demographics / weather) and weighted composition
- Confidence estimation for small-population cells

## Non-responsibilities

Downloading anything (`ingest/`), serving anything (`api/`), drawing anything
(`web/`).

## Status

Not implemented. Phase 1.
