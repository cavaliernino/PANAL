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

| Parameter | Meaning | Maps to the 2020 formula |
|---|---|---|
| `T2M` | Temperature at 2 m (MERRA-2) | "surface temperature" |
| `RH2M` | Relative humidity at 2 m (MERRA-2) | "relative humidity" |

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
| **TomTom Traffic** | ✅ **Recommended for live traffic.** 2,500 non-tile requests/day and 50,000 tiles/day free, and explicitly no restriction on displaying over non-TomTom basemaps. |
| **Google Maps traffic** | ❌ Prohibited on non-Google basemaps. Incompatible with our MapLibre choice. |
| **Waze for Cities** | ❌ for PANAL. Free two-way GeoRSS feed updated every 2 minutes, but restricted to public-sector partners with no commercial use. Reachable only through the Phase 5 agency channel. |

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

---

## Licensing — read before building a business on this

| Source | License | Consequence |
|---|---|---|
| SADU respiratory (MINSAL) | **CC Non-Commercial** | **Blocks commercial use of the primary health signal.** |
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
