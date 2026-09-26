# PANAL

**Georeferenced environmental health risk for Chile, on a hexagonal grid.**

PANAL tells you how much risk is elevated *where you actually are*, by
combining public health surveillance, census demographics, NASA meteorological
data and NASA satellite fire detections on an H3 hex grid — and by reporting
the excess over what is normal for that place at that time of year, rather than
a raw number that turns red every winter.

**Wildfire is the main line.** Megafires start as small fires, and the window
in which one can still be stopped by a rapid initial attack is measured in tens
of minutes. PANAL does not fight fires; it compresses the time between a fire
starting and someone competent knowing exactly where it is — and, before any of
that, shows which neighbourhoods are built in the condition that turns a small
fire into a catastrophe.

Respiratory risk remains, and follows. The two hazards are seasonally
opposite — fire peaks November to March, respiratory illness June to August —
and they are linked, because fire smoke drives respiratory emergencies. That
calendar sets the build order.

> 🏆 PANAL won the **Galactic Impact Award** at the NASA Space Apps Challenge
> COVID-19 in May 2020 — *"the solution with the most potential to improve life
> on Earth or in the universe."* This repository is the 2026 effort to build
> what that 48-hour prototype only described. See [`docs/legacy`](docs/legacy)
> for the original, preserved intact.

---

## Status

**Phases 0 and 1 done. Phase 2 built and half validated.**

| Phase | Scope | Deadline | Status |
|---|---|---|---|
| 0 | Repo hygiene, key revocation, monorepo, docs | — | ✅ done |
| 1 | Fire foundation — H3 grid, GOES + VIIRS ingest, maps | **Nov 2026** | ✅ done |
| 2 | WUI exposure — which neighbourhoods are built to burn | **Nov 2026** | ⚠️ hazard validated, consequence not |
| 3 | Crowdsourced first alarm — burst capture, bearing triangulation | | |
| 4 | Fire behaviour — spread vector, C2F+K, egress, traffic | | |
| 5 | Agency channel — CONAF/SENAPRED write official zones | | |
| 6 | Respiratory — the original PANAL index | autumn 2027 | |
| 7 | Android, hardening, public API | | |

Phase 2 is finished as engineering and cannot finish as science without
data only CONAF and SENAPRED hold — see
[`docs/alianzas.md`](docs/alianzas.md).

Picking this up after a break? Start at [`docs/estado.md`](docs/estado.md):
what runs unattended, what is blocked on whom, what expires when, and the
decisions already settled so they do not get reopened.

### What works today

**Detection, running.** GOES-East every 10 minutes over all of Chile,
published to a public bucket about a minute after each scan closes.
VIIRS at 375 m for precision. A cron refreshes the national snapshot on
the satellite's own cadence.

**Two maps.** [`web/index.html`](web) replays the 2 February 2024 Viña del
Mar fire at native cadence; `web/national.html` shows live national
detection with deck.gl.

**An industrial anomaly mask.** 63 cells across 12 sites — El Teniente,
Chuquicamata, Ventanas, Coloso. In a 24-hour window, 11 of 29 detections
were fixed industrial sources. Without it a dispatcher would read 29 fires
where 11 are smelters.

**A wildland-urban exposure index** over 677,426 census cells, from four
layers: Censo 2024 at block level, Copernicus 30 m slope, Sentinel-2 fuel
and OpenStreetMap egress.

### What is measured, not claimed

| | |
|---|---|
| GOES first saw the Viña fire at | **12:10 local**, 2 h 37 min before VIIRS |
| Hazard half of the index ranks the interface at | **3.83× chance** |
| Over Valparaíso, hazard and consequence both top-decile | **62 cells, 12,555 people** |
| OSM road coverage of inhabited cells, by population | **95.7%** |
| GOES coverage of Chile, every hour of the day | **100%** |

**The consequence half is not validated and carries the largest weights.**
A burn footprint cannot test it — only 9 of the 173 cells VIIRS saw burning
were inhabited. Structure-loss records would settle it, and that is the
first ask in `docs/alianzas.md`.

The index does **not** predict where a fire starts. It predicts how bad one
would be if it arrived.

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
| Fire | not covered | **GOES-East** (10 min) + **FIRMS** VIIRS/MODIS + CONAF + SINCA |
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
ingest/    goes · viirs · power · anomaly · census · terrain · fuel · egress
engine/    wui — the exposure index (pure, no I/O, 16 tests)
web/       index.html (replay) · national.html (live) · panal.js (shared)
api/       FastAPI — not started
android/   the 2020 app, carried forward for a Phase 7 rebuild
docs/      roadmap · data-sources · risk-model · crowdsourcing · alianzas
```

90 tests across `ingest` and `engine`:

```bash
cd ingest && ../.venv/bin/python -m pytest tests -q
cd engine && ../.venv/bin/python -m pytest tests -q
```

`engine/` is deliberately a pure library with no I/O: the risk model is the
part of this project that has to be correct, so it must be testable without a
database or a network.

---

## Detection is a latency stack

No single source is fast and precise at once:

| Layer | Latency | Resolution | Role |
|---|---|---|---|
| Crowd burst (in-app) | seconds | eyewitness | first alarm on a new fire |
| CONAF lookout tower | seconds | surveyed cross-fix | first alarm at T1 trust, ~20 bytes |
| GOES-East ABI | 10 min cadence, ~20–30 min lag | 2 km | tempo — detection and tracking |
| VIIRS / MODIS | ~3 h | 375 m | precision — confirm and map perimeter |
| CONAF / SENAPRED | human | authoritative | overrides everything |

FIRMS's sub-hour tiers are **US and Canada only**; Chile's floor is ~30 min
through GOES. A 2 km pixel cannot resolve a fire running up an urban ravine,
and a three-hour-old fix arrives after the initial-attack window has shut —
which is exactly why the crowd layer exists. See
[`docs/crowdsourcing.md`](docs/crowdsourcing.md).

---

## The respiratory model in one paragraph

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

**PANAL is non-commercial and will not charge for use.** This is a decision,
not a constraint: charging would cost the project global reach and, more
importantly, the ability to connect with the government institutions that
could give it real operational capacity.

It also resolves the licensing question outright. The MINSAL respiratory
dataset is Creative Commons Non-Commercial, and Waze for Cities is free but
restricted to non-commercial public-sector partners — PANAL satisfies both.

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

---

## What PANAL does not do

PANAL publishes a heat map and associated risk information. **It does not
issue evacuation orders.** Official alerts in Chile are SENAPRED's, through
SAE; PANAL's role is to surface and amplify them, never to imitate one. The
Phase 5 agency channel exists so CONAF and SENAPRED can publish official zones
through PANAL directly — which makes this a design, not a limitation.
