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

## Licensing — read before building a business on this

| Source | License | Consequence |
|---|---|---|
| SADU respiratory (MINSAL) | **CC Non-Commercial** | **Blocks commercial use of the primary health signal.** |
| Establecimientos de Salud | Check per-resource | — |
| Censo 2024 (INE) | Check INE terms | — |
| NASA POWER | Open, no restriction | Free to use. |
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
> POWER Project.
