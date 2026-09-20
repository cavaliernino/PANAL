# PANAL

**Georeferenced environmental health risk for Chile, on a hexagonal grid.**

PANAL tells you how much risk is elevated *where you actually are*, by
combining public health surveillance, census demographics, NASA meteorological
data and NASA satellite fire detections on an H3 hex grid — and by reporting
the excess over what is normal for that place at that time of year, rather than
a raw number that turns red every winter.

Two hazards, one map, complementary seasons: **respiratory illness**, which
peaks in winter, and **wildfire and its smoke**, which peaks in summer. They
are not independent — fire smoke drives respiratory emergencies, and PANAL has
twelve years of data on both to measure exactly how much.

> 🏆 PANAL won the **Galactic Impact Award** at the NASA Space Apps Challenge
> COVID-19 in May 2020 — *"the solution with the most potential to improve life
> on Earth or in the universe."* This repository is the 2026 effort to build
> what that 48-hour prototype only described. See [`docs/legacy`](docs/legacy)
> for the original, preserved intact.

---

## Status

**Phase 0 of 7 — repository groundwork. Nothing computes yet.**

The 2020 prototype returned a constant. The risk index described in the
award-winning submission was never implemented in code. Phase 1 is the first
time PANAL will actually calculate anything, and this README will not claim
otherwise until it does.

| Phase | Scope | Status |
|---|---|---|
| 0 | Repo hygiene, key revocation, monorepo, docs | ✅ done |
| 1 | The risk engine — H3 aggregation, seasonal baselines | next |
| 2 | Ingest pipelines for every source, **FIRMS first** | |
| 3 | API | |
| 4 | Web PWA — the first time PANAL is visible | |
| 5 | Forecasting, with honest backtesting | |
| 6 | Android, rebuilt against the same API | |
| 7 | Heat waves, evacuation alerts, public API | |

---

## What changed in six years

The 2020 project depended on the **MinCiencia COVID-19 data repository**, which
stopped updating on 31 August 2023 when Chile's health alert ended. Its URL now
404s. PANAL's original fuel no longer exists.

The replacement is better than what the project had in 2020:

| Input | 2020 | 2026 |
|---|---|---|
| Health | MinCiencia COVID, comuna-level *(dead)* | MINSAL SADU — **635 establishments, 100% geocoded, weekly, 2014→2026** |
| Demographics | Global gridded raster, coarse | **Censo 2024 at block level**, 189 variables |
| Weather | Manual NOAA downloads | **NASA POWER API**, `T2M` + `RH2M` by coordinate |
| Fire | not covered | **NASA FIRMS** (VIIRS/MODIS, no API key) + CONAF + SINCA |
| Grid | Hexagons drawn by hand | **H3**, stable global cell ids |

And the disease changed. In 2026 Chile, COVID-19 emergency attendances run
**2–103 per week nationally**, while upper respiratory infections run
**55,000–87,000**. Building a COVID-only product today would render an empty
map. PANAL now covers respiratory risk as a whole: influenza, RSV/bronchiolitis,
pneumonia, URI and COVID.

Full verification of every source, including the traps, is in
[`docs/data-sources.md`](docs/data-sources.md).

---

## Repository layout

```
ingest/    Python ETL — SADU, FIRMS, NASA POWER, Censo 2024, SINCA → H3 → PostGIS
engine/    the risk index and seasonal baselines (pure, testable library)
api/       FastAPI — /risk, /forecast, /timeseries
web/       PWA — MapLibre GL + deck.gl H3HexagonLayer
android/   the 2020 app, carried forward for a Phase 6 rebuild
docs/      the model, the sources, and the 2020 originals
```

`engine/` is deliberately a pure library with no I/O: the risk model is the
part of this project that has to be correct, so it must be testable without a
database or a network.

---

## The model in one paragraph

Respiratory emergency attendances are attributed to their establishment's H3
cell and spread across a catchment, normalised per 100,000 inhabitants from
Censo 2024, then compared against a seasonal baseline built from 2014–2024 to
yield an **excess over expected** for that epidemiological week. That health
term carries 50% of the index, demographics 35% and weather 15%, following the
2020 hypothesis — weights we intend to test against 12 years of history and to
revise if the data disagrees, including with the presentation that won the
award.

Wildfire is deliberately **not** a fourth weighted term, because it is partly a
*cause* of the health signal and adding both would double-count. Smoke feeds
the health component as an acute exposure term; the acute fire front is a
separate layer on its own time constant. Details and open questions:
[`docs/risk-model.md`](docs/risk-model.md).

---

## Ground rules

1. **Show the lag.** SADU runs ~2 weeks behind. Never imply live surveillance.
2. **Show the breakdown.** One number is not actionable; expose every
   component that went into it.
3. **Show the uncertainty.** Small-population cells are unstable and must look
   different from confident ones, never silently safe.
4. **Never invent granularity.** Health data is establishment-level and
   weekly; fire detections are 375 m and sub-daily. Never render one at the
   other's resolution, or blend them onto a single colour scale.
5. **Validate before shipping.** If the index has no predictive skill, publish
   that finding too.
6. **No personal data, ever.** PANAL models places, not people. The 2020
   submission committed to this and it remains binding.

---

## Licensing

Code is **GPL-3.0** (see [LICENSE](LICENSE)).

⚠️ The MINSAL respiratory dataset is **Creative Commons Non-Commercial**. That
permits public-good deployment, research and an open API; it rules out a paid
product built on that feed without a separate agreement with MINSAL. This needs
a decision before Phase 3.

When publishing derived work:

> Data produced by the Ministerio de Salud de Chile and obtained from the
> Portal de Datos Abiertos (datos.gob.cl). Census data from the Instituto
> Nacional de Estadísticas, Censo 2024. Meteorological data from the NASA
> POWER Project. Active fire data from NASA FIRMS (MODIS and VIIRS). Forest
> fire statistics from CONAF. Air quality data from SINCA, Ministerio del
> Medio Ambiente.

---

## Team

PANAL was built by **Carolina Retamal**, **Marcos Maldonado**,
**Nino Bozzi** and **Patricio Alarcón** — Concepción, Santiago and
Viña del Mar, Chile.
