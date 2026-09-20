# The PANAL risk index

**Status: specification, not yet implemented.** This document is the Phase 1
contract. `engine/` implements exactly what is written here, and nothing here
is considered settled until it has a test.

---

## What 2020 promised

The Space Apps submission described a weighted index over three groups:

| Group | Weight | Variables |
|---|---|---|
| Weather | 15% | surface temperature, relative humidity |
| Demographics | 35% | population density, socioeconomic index |
| Health | 50% | distance to health centres, active cases |

**None of this existed in code.** The 2020 backend returned a hardcoded
`HttpResponse("{[50,50,50,50,50]}")` and the app displayed a hardcoded `50%`.
The weights come from the presentation, so they are a starting hypothesis, not
a validated model. Phase 1 is the first time PANAL actually computes anything.

---

## Spatial unit: H3

2020 drew hexagons by hand in `MapsActivity.drawHexagon()`, computing vertex
offsets from metres-per-degree at the centroid. The instinct was right — the
team chose hexagons over squares deliberately — but the implementation had no
stable cell identity, so a cell could not be keyed, cached or joined.

We adopt [H3](https://h3geo.org): a global hierarchical hexagonal index where
every cell has a stable 64-bit id.

| Resolution | Avg. area | Avg. edge | Use |
|---|---|---|---|
| 6 | ~36 km² | ~1.2 km | regional rollup |
| **7** | **~5.2 km²** | **~1.4 km** | **default city view** |
| **8** | **~0.74 km²** | **~0.46 km** | **dense urban detail** |

The H3 cell id is the primary key everywhere: ingest output, database, API
response, map layer. Resolution 7 is the default; 8 where density justifies it.

---

## The core correction: excess over expected

The most important design decision, and the one the 2020 data could not
support.

Raw attendance counts measure **where the big hospitals are**, not where the
risk is. A regional hospital always shows a high number. Two normalisations fix
this:

**1. Per capita.** Normalise by population from Censo 2024, per 100k
inhabitants, so a rural cell and a metropolitan cell are comparable.

**2. Seasonal baseline.** Respiratory illness in Chile is strongly seasonal —
the winter campaign is an annual, expected event. An index that turns red every
July tells nobody anything. With 2014–2024 of history we compute, for each cell
and each epidemiological week, the expected level, and the index reports the
**excess over that expectation**.

So the health term is not *"how many respiratory cases are there here"* but
*"how many more than normal for this place, at this time of year"*.

Baseline method is open: a per-week-of-year robust central estimate
(median plus MAD, or a Farrington-style approach) over the pre-2025 years,
excluding 2020–2021 as pandemic-distorted outliers. **To be decided with data
in hand during Phase 1.**

---

## Component definitions

Each component yields a 0–1 score before weighting.

### Health (50%)

```
health = w1 · excess_respiratory   (per-capita excess over seasonal baseline)
       + w2 · vulnerability        (age-band mix, 65+ and under-1 weighted up)
       + w3 · access_deficit       (distance to nearest facility, inverted)
```

Attendances are attributed to their establishment's H3 cell, then spread to
neighbouring cells with a distance decay — a hospital serves a catchment, not
its own hexagon. Catchment radius is a parameter, fit against comuna-level
totals.

### Demographics (35%)

```
demographics = w4 · population_density   (Censo 2024 manzana → H3)
             + w5 · socioeconomic        (derived from the 189 block variables)
             + w6 · overcrowding         (persons per dwelling)
```

### Weather (15%)

```
weather = f(T2M, RH2M)
```

From NASA POWER per cell centroid. The 2020 submission asserted a
temperature/humidity relationship with transmission but never specified the
function. Phase 1 starts with a documented, literature-grounded transfer
function and **validates it against the 12-year history before trusting it**.
If it does not predict, the 15% weight drops to zero and we say so.

### Composition

```
risk = 0.50 · health + 0.35 · demographics + 0.15 · weather
```

Weights live in a config file, not in code.

---

## Wildfire: a driver, not a fourth component

The obvious move is to bolt fire on as a fourth weighted term. That would be
wrong. Fire is not a peer of the health signal — it is partly a **cause** of
it, and adding both would double-count the same people.

Fire enters in two places, because it produces two hazards with different time
constants and different actions for the person holding the phone:

### A. Acute fire hazard — hours

```
fire_hazard(cell) = f(distance to active detections, FRP, wind direction)
```

From NASA FIRMS, refreshed several times a day. The question it answers is
*"is there fire near me right now"*, and the action is evacuation. This is a
**separate output layer**, not folded into the respiratory index, because
mixing a 15-minute-old fire front into a two-week-lagged health average would
destroy both.

### B. Smoke exposure — days

```
smoke(cell) = g(upwind FRP, distance, wind, PM2.5 from SINCA)
```

This **feeds the health component** as an acute exposure term, alongside the
seasonal-baseline excess:

```
health = w1 · excess_respiratory
       + w2 · vulnerability
       + w3 · access_deficit
       + w4 · smoke_exposure      ← new
```

Smoke also raises the vulnerability weighting for the under-1 and 65+ bands
that SADU already breaks out.

### Why this is the strongest part of the project

PANAL has, in one place, twelve years of weekly geolocated respiratory
emergency attendances **and** a satellite fire record covering the same period
and territory. Chile's catastrophic seasons — 2016–17, 2022–23, and Valparaíso
in February 2024 — all fall inside the SADU record that starts in 2014.

So the smoke-to-health link is not an assumption we have to make. **It is a
hypothesis we can test against history**, cell by cell and week by week: did
respiratory attendances rise downwind of large fires, above the seasonal
baseline, controlling for population? If yes, the coefficient is measured
rather than guessed, and PANAL can forecast respiratory load from a fire that
is burning today. If no, we report that and drop the term.

This is also the most direct possible answer to the Space Apps *Human Factors*
challenge, which asked for human activities that drive disease spread. Chilean
forest fires are overwhelmingly human-caused, and CONAF records the cause of
each one. The chain is: human activity → fire → smoke → respiratory disease,
and every link in it is measurable from open data.

### What it does for the product

Respiratory risk peaks June–August. Fire risk peaks November–March. Adding
fire turns PANAL from a four-month winter app into a **year-round** one, with
no dead season.

### Timing

Chile's fire season opens around November. The FIRMS ingest should be running
**before then** so the 2026–27 season is captured live rather than backfilled.
That is the one real external deadline on this roadmap.

---

## Honesty requirements

Non-negotiable properties of the output:

1. **Show the lag.** SADU runs ~2 weeks behind. The UI states the data date; it
   never implies live surveillance.
2. **Show the breakdown.** A single number is not actionable. Every cell
   exposes its three components.
3. **Show the uncertainty.** Cells with small populations have unstable rates.
   Low-confidence cells are visually distinct, not silently rendered as safe.
4. **Never invent granularity.** Data is establishment-level and weekly.
   Rendering a smooth continuous surface implies precision we do not have.
5. **Validate before shipping.** The index is backtested against 2023–2025
   before any public deployment. If it has no skill, that gets published too.

---

## Open questions

- [ ] Baseline estimator: median/MAD vs. Farrington vs. STL decomposition?
- [ ] Catchment decay function and radius — fit how?
- [ ] Do the Censo 2024 block variables support a defensible socioeconomic
      index, or do we need CASEN?
- [ ] Is there a defensible weather transfer function, or do we drop the 15%?
- [ ] Are the 2020 weights (15/35/50) supportable at all, or does backtesting
      demand different ones? **We should be willing to contradict the
      award-winning presentation.**
- [ ] Smoke dispersion: is a simple upwind-FRP decay good enough, or do we
      need a real plume model? Validate against SINCA PM2.5 stations.
- [ ] How do we mask persistent industrial thermal anomalies (Chuquicamata
      and the northern smelters) without suppressing real fires near them?
- [ ] Does fire hazard belong in the same map as respiratory risk, or in a
      separate view? Two hazards with different time constants may not
      belong on one colour scale.
