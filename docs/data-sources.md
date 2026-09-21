# Data sources

Every source below was verified on **2026-09-20**. The 2020 project relied on a
feed that no longer exists, so each entry records *what it replaces* and *how we
know it is alive*.

---

## The source that died

**MinCiencia / Datos-COVID19** — `https://github.com/MinCiencia/Datos-COVID19`

The backbone of PANAL 2020. It stopped being updated on **31 August 2023** when
Chile's health alert ended, and the URL now returns 404. The frozen products
were moved to the Observa MinCiencia open-data section.

This is the single fact that forced the 2026 pivot from "COVID-19 risk" to
"respiratory risk".

---

## 1. Health — 50% of the risk index

### SADU: weekly respiratory emergency care (primary signal)

| | |
|---|---|
| Publisher | Ministerio de Salud, via `datos.gob.cl` |
| Dataset | `Atenciones de urgencias de causas respiratorias por semana epidemiológica` |
| Dataset ID | `606ef5bb-11d1-475b-b69f-b980da5757f4` |
| Resource ID | `ae6c9887-106d-4e98-8875-40bf2b836041` |
| Format | Parquet, ~65 MB (also XLSX) |
| Last update | 2026-09-16 |
| **License** | **Creative Commons Non-Commercial** — see the warning below |

Verified shape, read directly from the file:

```
3,655,636 rows · 25 columns · 4 row groups
2014 → 2026 (data through epidemiological week 36; ~2 week reporting lag)
635 establishments · 100% geocoded · 308 comunas · 16 regions
bbox: lat -54.935 .. -18.198 | lon -109.421 .. -67.600  (includes Rapa Nui)
```

Columns that matter:

| Column | Why it matters |
|---|---|
| `Latitud`, `Longitud` | **Point-level geolocation.** This is what makes an H3 grid possible. |
| `Causa`, `OrdenCausa` | 12 causes — lets us separate influenza from bronchiolitis from COVID. |
| `Anio`, `SemanaEstadistica` | 12 years of weekly history → seasonal baselines and honest backtesting. |
| `NumTotal` | Total attendances. |
| `NumMenor1Anio` … `Num65oMas` | 6 age bands → vulnerability weighting. 65+ is 10.9% of 2026 volume. |
| `ComunaCodigo` | Join key to Censo 2024. |
| `TipoEstablecimiento`, `NivelComplejidad` | Lets us weight a regional hospital differently from a SAPU. |

> **Parsing trap:** `Latitud` and `Longitud` are strings using a **comma decimal
> separator** (`-33,610078`), Chilean locale. Parsed naively they silently
> become 100% null. Always `str.replace(",", ".")` before `to_numeric`.

The 12 causes:

```
 3  TOTAL CAUSA SISTEMA RESPIRATORIO (J00-J98)
 4  IRA Alta (J00-J06)
 5  Influenza (J09-J11)
 6  Neumonía (J12-J18)
 7  Bronquitis/bronquiolitis aguda (J20-J21)
 8  Crisis obstructiva bronquial (J40-J46)
 9  Otra causa respiratoria (J22; J30-J39, J47, J60-J98)
10  TOTAL ATENCIONES POR COVID-19, Virus no Identificado U07.2
11  TOTAL ATENCIONES POR COVID-19, Virus Identificado U07.1
33  - Causas sistema respiratorio (J00-J98)          ← subtotal row
34  - Por covid-19, virus no identificado U07.2      ← subtotal row
35  - Por covid-19, virus identificado U07.1         ← subtotal row
```

> **Aggregation trap:** rows 3, 33, 34 and 35 are **totals and subtotals**, not
> peer categories. Summing all 12 double-counts. Use rows 4–9 as the disjoint
> respiratory partition, and 10/11 for COVID.

Why COVID is no longer the headline — national weekly volume, 2026:

| Cause | Weeks 26–36, per week |
|---|---|
| IRA Alta | 55,040 – 86,612 |
| Bronquitis/bronquiolitis | 14,605 – 24,661 |
| Neumonía | 4,609 – 6,737 |
| Influenza | 3,444 – 5,190 |
| **COVID-19 (identified)** | **2 – 103** |

COVID-19 is now three to four orders of magnitude below the dominant signal.
A 2026 product built on COVID alone would show an empty map.

### Health facility registry (access-to-care component)

| | |
|---|---|
| Dataset | `Establecimientos de Salud` on `datos.gob.cl` |
| Format | CSV (also PDF) |
| Last update | 2026-09-16 |

Covers all active public and private facilities, not just the 635 with
emergency departments. Used for the distance-to-care term that PANAL 2020
described but never implemented.

---

## 2. Demographics — 35% of the risk index

**Censo de Población y Vivienda 2024, INE** — `https://censo2024.ine.gob.cl`

Replaces the Columbia/SEDAC global gridded population raster used in 2020.

- Total population 18,480,432 (+5.16% over 2017).
- Block-level (`manzana`) database published **December 2024**: 189 variables
  across people, households and housing.
- Smallest geography: urban block, village block, rural entity, urban zone,
  rural locality.
- Official census cartography published alongside, plus a variable dictionary.

This is a large resolution upgrade: 2020 used a coarse global raster plus a
comuna-level socioeconomic index. The 189 block-level variables should let us
derive the density **and** the socioeconomic/overcrowding terms from one
consistent, official source.

---

## 3. Weather — 15% of the risk index

**NASA POWER API** — `https://power.larc.nasa.gov/docs/services/api/`

Replaces the manual NOAA dataset downloads used in 2020, and keeps PANAL
anchored to a NASA source, which matters for a Space Apps project.

| Parameter | Meaning | Used for |
|---|---|---|
| `T2M` | Temperature at 2 m (MERRA-2) | 2020 formula; 30-30-30 |
| `RH2M` | Relative humidity at 2 m (MERRA-2) | 2020 formula; 30-30-30 |
| `WS10M` | Wind speed at 10 m | 30-30-30; smoke drift; rate of spread |
| `WD10M` | Wind direction at 10 m | where the fire runs; plume bearing check |

10 m is the fire-weather standard height for wind, not 2 m.

#### The 30-30-30 factor

Chile's fire services use a pre-alert heuristic — **temperature ≥ 30 °C,
relative humidity ≤ 30%, wind ≥ 30 km/h** — treated as extreme conditions for
fire spread. PANAL computes it per frame from POWER and shows which of the
three legs are met.

Two things to be careful about:

- **The unit is km/h in every published Chilean source we found.** Some
  services state the wind limit in knots, which is nearly double
  (30 kt = 55.6 km/h) and therefore trips far less often. On 2 February 2024
  over Viña del Mar, the 30 km/h threshold was met from 16:00 to 18:50 local,
  while 30 kt would never have been met — the peak was 17.1 kt. The threshold
  and its unit are configurable (`power.Factor30`) rather than assumed.
- **It is a heuristic, not a model.** Chilean academics have criticised it as
  lacking scientific backing and as insufficient for the severity now seen.
  PANAL shows it because it is what the services act on. Cell2Fire + Kitral
  is the physics.

> **Resolution trap.** MERRA-2 is a ~50 km global reanalysis. In terrain like
> Valparaíso's ravines, local wind can differ sharply from the grid-cell
> average, so POWER is right for regional context and for replaying past
> events, and wrong as the sole input to an operational alert. Local stations
> — DMC, or a corps' own — are what an alert should eventually read.

- Endpoints: hourly, daily and monthly, queried by point coordinates.
- Limits: 20 parameters per request for daily, 15 for hourly.
- Hourly data available in both UTC and Local Solar Time.
- No API key required.

Queried per H3 cell centroid, cached, and refreshed on the ingest schedule.

---

## 4. Wildfire

Fire is not a fourth silo. In Chile it is **seasonally complementary** to
respiratory illness — respiratory risk peaks in winter (June–August), fire
peaks in summer (November–March) — and the two are causally linked through
smoke. See [`risk-model.md`](risk-model.md) for how it enters the index.

### NASA FIRMS — active fire detections

| | |
|---|---|
| Publisher | NASA / MODAPS EOSDIS |
| Latency | Near-real-time, <60 min from satellite pass |
| **API key** | **Not required** for the regional CSV endpoints |

Verified working on 2026-09-20 with no registration:

```
https://firms.modaps.eosdis.nasa.gov/data/active_fire/{product}/csv/{FILE}_24h.csv

noaa-20-viirs-c2/csv/J1_VIIRS_C2_South_America_24h.csv      200 OK  24,341 rows
suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_South_America_24h.csv 200 OK  24,294 rows
modis/csv/MODIS_C6_1_South_America_24h.csv                  200 OK   3,378 rows
```

Also available as `_48h` and `_7d`. Columns:

```
latitude, longitude, bright_ti4, scan, track, acq_date, acq_time,
satellite, confidence, version, bright_ti5, frp, daynight
```

`frp` (Fire Radiative Power, MW) is the key field: it proxies fire intensity
and therefore smoke emission rate. VIIRS resolution is 375 m, MODIS 1 km, so
prefer VIIRS and use MODIS to corroborate.

A free `MAP_KEY` unlocks the `/api/area/` endpoint for arbitrary bounding
boxes and historical dates (1–5 day ranges, 5,000 transactions per 10 min).
Worth registering for backfill, but **not needed to start**.

> **Trap 1 — a bounding box over Chile is 90% wrong.** Chile is narrow and the
> Andes run its whole length. A naive box (`lon -76..-66, lat -56..-17`)
> returned 260 detections, of which only **25 were west of the Andean divide**.
> The other 235 were Argentine and Bolivian. Clip against real geometry — the
> INE census cartography we already need for demographics — never a box.

> **Trap 2 — FIRMS detects industry, not just fire.** On 2026-09-20 the
> strongest persistent Chilean cluster sat at `-22.316, -68.882`: nine
> detections, two satellites, two days, scattered over ±0.2 × ±0.4 km with a
> stable ~3.7 MW FRP. That is **Chuquicamata**, an open-pit copper mine, not a
> wildfire. Northern Chile is full of smelters and mines that read as permanent
> thermal anomalies. A real fire moves and grows; a plant does not. Mask
> persistent sources by building a static exclusion layer from a full season of
> detections before trusting any alert.

> **Trap 3 — we are out of season.** Chile's fire season runs roughly November
> to March. September detections are near zero, so the pipeline **cannot be
> validated on live data until summer**. Build and backfill against history.

### GOES-East — geostationary, the tempo layer

| | |
|---|---|
| Satellite | GOES-19, operational as GOES-East since April 2025, at 75.2°W |
| Product | ABI Level 2 Fire / Hot Spot Characterization (FDC) |
| Cadence | **Full disk every 10 minutes**, 24 h, no revisit gaps |
| Latency | ~20–30 min via FIRMS; ~10–15 min direct from NOAA on AWS Open Data |
| Resolution | 2 km |

The fire mask comes with fire temperature, fire area and FRP per pixel.

GOES-East sits almost on Chile's meridian, so viewing geometry over the
central and southern zone — Valparaíso, Ñuble, Biobío, La Araucanía, where
the fires and the towns are — is good. It degrades toward Magallanes.

The trade against VIIRS is stark and both directions matter:

```
GOES   every 10 min, 2 km,  beta quality  -> sees fast, not fine
VIIRS  every ~6 h,  375 m,  reliable      -> sees fine, not fast
```

> **Trap — geostationary fire data is beta.** FIRMS classifies all of it as
> provisional and shows only high-confidence detections, because the current
> generation of geostationary algorithms is "prone to significant errors of
> commission and/or omission". Treat a GOES detection as *something is
> happening near here*, never as a fix.

FIRMS latency tiers, for the record: Ultra Real-Time (<1 min) and Real-Time
(<1 h) exist but are **US and Canada only**, served by direct-readout ground
stations. Global Near Real-Time is ~3 hours. Standard Processing is 2–3
months. **Chile's floor through polar orbiters is 3 hours; through GOES it is
about 30 minutes.**

### Fire department dispatch feeds

A dispatch is the strongest human signal available: someone called, and a
unit rolled. It is T1-quality evidence arriving in real time, and it carries
something no satellite has — a street address and a incident classification
made by a professional.

Chilean corps publish dispatches to automated X accounts:

```
X-1 CLAVE 2 U-32 U-11 U-31 U-51 U-61 U-73 U-41 U-62
Autopista Troncal Sur con Camino El Olivar, sector El Salto
info -> cbvm132.cl/Sisgemer.aspx?sid=dLI%2fKcSo8qw%3d
```

The structure is better than it looks. `CLAVE 2` is a forest emergency in the
Valparaíso region (other regions use codes like `10-2`); `CLAVE 8` is support
to another corps, which is how a neighbouring fire shows up in a corps' own
feed. The unit list gives committed resources, so escalation is visible —
`USAR-1` appearing means urban search and rescue. **The `sid` is an incident
id**, shared across every dispatch for the same fire, which turns a stream of
messages into a per-incident resource timeline.

#### Do not build on X

Tested on 2026-09-20 against `@CBVM132` for the February 2024 Viña del Mar
fire, using an authenticated session:

- **Search caps results.** Every query returned about 15 posts regardless of
  the date window, so a dispatch timeline cannot be reconstructed.
- **Date filters behave inconsistently.** `since:2024-02-02 until:2024-02-03`
  returned only 3 February; widening to 1–5 February returned only 5
  February. Timestamps are exact once retrieved (`<time datetime>`), but the
  result set is not trustworthy.
- **`@CBQuilpue` returned nothing** for the period — and Quilpué is where
  that fire started, so the origin dispatch is unreachable this way.
- **`cbvm132.cl` no longer resolves**, so every historical SISGEMER link is
  dead.

X is also fragile and contractually awkward as a production input.

#### The upstream exists: VIPER

Every one of those posts is marked *Automatizado por `@viper_cl`*. VIPER
(`viper.cl`, Santiago) is a Chilean emergency-management platform — products
VIPER APP, CREW, ONE, GO and MASS — selling dispatch and critical-information
systems to organisations including fire corps.

That changes the approach entirely. Rather than scraping one X account per
corps, **one integration with VIPER could reach many corps at once**, with
structured data instead of parsed text, and without depending on a social
network's indexing. It is the same kind of conversation as the CONAF and
SENAPRED partnership, and it belongs in Phase 5 beside them.

Worth asking VIPER directly whether a read feed is available to a
non-commercial public-good project, and worth asking the corps whether their
own SISGEMER instance can expose one.

### CONAF — official fire statistics

| | |
|---|---|
| Publisher | Corporación Nacional Forestal |
| Coverage | Season 2002–03 to present |
| Granularity | Per event: region, province, comuna, latitude, longitude |

Per-event fields include fire number and name, start and containment dates,
**cause**, initial and affected fuel type, slope, topography, and burned area
broken down by vegetation type.

Two things FIRMS cannot give us:

1. **Ground truth on burned area.** Satellite detections say where heat was;
   CONAF says how many hectares actually burned. Needed to calibrate FRP into
   anything physical.
2. **Cause.** Chilean forest fires are overwhelmingly human-caused, and CONAF
   classifies them. This is the most literal possible answer to the Space Apps
   *Human Factors* challenge: a human activity that drives an environmental
   hazard that drives respiratory disease.

Reference seasons for validation: **2016–17 is the worst on record at ~466,700
ha burned**; 2022–23 (Biobío/Ñuble) and February 2024 (Valparaíso/Viña del Mar)
were both catastrophic. All three fall inside the SADU health record, which
starts in 2014.

### SINCA — air quality, the bridge to health

| | |
|---|---|
| Publisher | Ministerio del Medio Ambiente |
| Portal | `https://sinca.mma.gob.cl` |
| Pollutants | PM2.5, PM10, O₃, SO₂, NO₂, CO |
| Cadence | Hourly, per station |

This is the measured link between fire and health. FIRMS says a fire is
burning; SINCA says whether people are breathing it. PM2.5 is the variable
that connects a fire front to an emergency-room visit, and it is also a
year-round hazard in Chile from winter wood-smoke heating in the central and
southern cities — which means the same ingest serves both seasons.

Station coverage is sparse compared to a hex grid, so SINCA calibrates and
validates a dispersion estimate; it does not replace one.

### Traffic and road network

Congestion turns an evacuation into a death trap, so egress is a data
requirement, not a nicety.

| Source | Status |
|---|---|
| **OpenStreetMap** | ✅ Road network for static egress capacity. No API, no licence problem, available now. |
| **Waze for Cities** | ✅ **via the agency partnership.** Free two-way GeoRSS feed, updated every 2 minutes. Restricted to public-sector partners and non-commercial use — both of which PANAL satisfies through CONAF/SENAPRED. |
| **TomTom Traffic** | ✅ **Recommended as the independent path.** 2,500 non-tile requests/day and 50,000 tiles/day free, and explicitly no restriction over non-TomTom basemaps. |
| **Google Maps traffic** | ❌ Prohibited on non-Google basemaps. Incompatible with our MapLibre choice. |

**Where TomTom's data comes from:** crowd-sourced probe data from mobile
phone users and connected devices, combined with traditional infrastructure
sources — induction loops and traffic cameras. Chile is in TomTom's coverage
list and has its own TomTom Traffic Index country page, so the probe density
is real.

**Both are in scope, fused rather than chosen between.** They are independent
probe networks, so their errors are largely independent and agreement between
them is a quality signal in itself. Waze's penetration in Chile is almost
certainly deeper than TomTom's navigation install base, which matters because
both are ultimately probe-density plays. TomTom ships first because it needs
no one's permission; Waze joins with the alliance.

Where the two disagree on a segment, **take the worse of the two**. During an
evacuation an optimistic travel time is the dangerous error.

Static egress capacity — dwellings behind each exit road, dead ends,
single-access neighbourhoods — comes from OSM joined to Censo 2024 and needs
no traffic provider at all.

### Fire behaviour modelling

**Cell2Fire + Kitral (C2F+K).** Kitral is the Chilean fire behaviour system
developed at the Universidad de Chile in the mid-1990s — the name is
Mapudungun for fire — and its algorithm still underlies the prediction models
CONAF's lineage uses. It takes slope, wind, fuel moisture and fuel type.
C2F+K combines it with the Cell2Fire growth simulator, tuned for Chilean
forests.

It is **cell-based**, which pairs naturally with an H3 grid.

| | |
|---|---|
| `github.com/fire2a/C2F-W` | Unified version with Kitral and Scott & Burgan. Last push Aug 2026. **Preferred.** |
| `github.com/fire2a/C2FK` | Kitral-only version. Last push Jun 2026. |
| License | **GPL-3.0 — the same as PANAL.** No licence friction. |

C2F+K adds rate-of-spread and length-to-breadth equations as functions of
wind speed under an elliptical growth model, plus a crown fire module. It
generates **burn probability maps through parallel Monte Carlo ensembles**,
which is not just a Phase 4 tool: it means the Phase 2 exposure map can be
*simulated* rather than only inferred from where fires happened to burn
before.

---

## Licensing — read before building a business on this

**Resolved: PANAL is non-commercial by design.** The project will not charge
for use — charging would cost it global reach and, more importantly, the
ability to connect with the government institutions that could give it real
operational capacity. That decision removes the sharpest constraint in this
table and unlocks Waze for Cities through the agency partnership.

| Source | License | Consequence |
|---|---|---|
| SADU respiratory (MINSAL) | CC Non-Commercial | ✅ Compatible — PANAL is non-commercial. |
| Establecimientos de Salud | Check per-resource | — |
| Censo 2024 (INE) | Check INE terms | — |
| NASA POWER | Open, no restriction | Free to use. |
| NASA FIRMS | Open, attribution requested | Free to use. |
| CONAF statistics | Check CONAF terms | — |
| SINCA (MMA) | Check MMA terms | — |
| PANAL's own code | GPL-3.0 | Derivatives stay open. |

The CC-NC clause on the health data is the sharpest constraint on the project.
It does not affect a public-good deployment, research, or an open API. It does
rule out a paid product built on that feed without a separate agreement with
MINSAL. **This needs a decision before Phase 3.**

---

## Attribution

When publishing anything derived from these sources:

> Data produced by the Ministerio de Salud de Chile and obtained from the
> Portal de Datos Abiertos (datos.gob.cl). Census data from the Instituto
> Nacional de Estadísticas, Censo 2024. Meteorological data from the NASA
> POWER Project. Active fire data from NASA FIRMS (MODIS and VIIRS). Forest
> fire statistics from CONAF. Air quality data from SINCA, Ministerio del
> Medio Ambiente.
