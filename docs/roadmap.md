# Roadmap

**Wildfire is the main line.** Respiratory risk remains, but it follows.

---

## The thesis

Megafires start as small fires. The window in which a fire can still be
stopped by a rapid initial attack is measured in tens of minutes, and it closes
fast. Everything after that window is consequence management.

PANAL does not fight fires. What it can do is **compress the time between a
fire starting and someone competent knowing exactly where it is** — and, before
any of that, show which neighbourhoods are built in the condition that turns a
small fire into a catastrophe.

That is the whole product. Detection latency and exposure, not suppression.

---

## The calendar drives the order

Chile's two hazards are seasonally opposite, and that sets the schedule:

```
        SEP   OCT   NOV   DEC   JAN   FEB   MAR   APR   MAY   JUN   JUL   AUG
fire     ·     ·    ████  ████  ████  ████  ████   ·     ·     ·     ·     ·
resp     ·     ·     ·     ·     ·     ·     ·     ·    ███   ████  ████  ████
        └─ build fire ──┘                          └─ build respiratory ──┘
```

**Fire capability ships before November 2026.** Respiratory follows in autumn,
ahead of the 2027 winter. Nothing about this is arbitrary — miss the November
window and the next validation opportunity is a year away.

---

## Detection is a latency stack, not a source

No single source is good enough. Each covers another's blind spot:

| Layer | Latency | Resolution | What it is for |
|---|---|---|---|
| **Crowd burst** (in-app) | seconds | eyewitness | **First alarm on a new fire** |
| **GOES-East ABI** | new look every 10 min, ~20–30 min lag | 2 km | **Tempo** — early detection and tracking a moving front |
| **VIIRS / MODIS** (FIRMS) | ~3 h, few passes daily | 375 m / 1 km | **Precision** — confirm location, map perimeter |
| **CONAF / SENAPRED** | human | authoritative | **Truth.** Overrides everything above. |

GOES answers *"something is happening, now"*. VIIRS answers *"here is exactly
where"*. They are not redundant, and neither is sufficient alone: a 2 km pixel
cannot resolve a fire running up an urban ravine, and a three-hour-old fix
arrives after the initial-attack window has shut.

Ultra Real-Time (<1 min) and Real-Time (<1 h) FIRMS tiers exist but are
**US and Canada only**. Chile's floor via FIRMS is ~30 minutes, through GOES.
Going direct to the NOAA GOES-19 ABI L2 FDC product on AWS Open Data gets
closer to 10–15 minutes, at the cost of handling the algorithm's noise
ourselves. That is a Phase 4 optimisation, not a starting point.

---

## Phases

### Phase 1 — Fire foundation *(before November 2026)*

The H3 grid for Chile, the GOES and FIRMS ingest, and a web map that shows
live fire detections. First phase where PANAL is visible and useful.

- H3 grid clipped to **real Chilean geometry** from INE census cartography.
  A bounding box is 90% Argentina and Bolivia.
- GOES-East ABI FDC ingest, 10-minute cadence.
- FIRMS VIIRS/MODIS ingest for confirmation and perimeter.
- **Persistent thermal anomaly mask.** Chuquicamata and the northern smelters
  read as permanent fires. Build the exclusion layer from a full season of
  detections before anything is shown to a human.
- PWA v1: MapLibre + deck.gl H3 layer, detections with age and confidence.

### Phase 2 — WUI exposure *(before November 2026)*

Which neighbourhoods are built in the condition that kills. No real-time
anything, no false-alarm risk, and the highest preventive value in the project.

- Censo 2024 block-level dwellings and population → H3.
- Slope and topography from a DEM; fire spreads uphill fast.
- Fuel: vegetation cover adjacent to housing.
- Fire history from CONAF and the FIRMS archive — where fire recurs.
- **Egress capacity** (see below).

The output is a map of the condition that killed more than 130 people in
Valparaíso in February 2024: dwellings on ravine slopes, surrounded by fuel,
with a single narrow way out. That map is actionable months in advance, for
defensible space, fuel breaks and evacuation planning.

### Phase 3 — Crowdsourced first alarm

Burst capture, bearing triangulation and the trust model. Full design in
[`crowdsourcing.md`](crowdsourcing.md).

### Phase 4 — Fire behaviour

Where the fire is going, how fast, and whether people can get out ahead of it.

- **Observed spread vector.** GOES's 10-minute cadence gives successive
  detection centroids — direction and rate of spread measured, not modelled.
- **Modelled rate of spread** via **Cell2Fire + Kitral (C2F+K)**, the Chilean
  system CONAF's lineage already uses. Kitral takes slope, wind, fuel moisture
  and fuel type; it is cell-based, which pairs naturally with H3.
- **Traffic.** Congestion turns an evacuation into a death trap.

### Phase 5 — Agency channel

An authenticated write path so CONAF and SENAPRED can publish official zones
directly into PANAL. This is also what resolves the alerting boundary: PANAL
never issues an evacuation order; authorities do, through PANAL.

- Authenticated agency role, fully audited, every write attributed.
- Official polygons render as authoritative and visually distinct from
  anything PANAL derived.
- This is the legitimate channel for **Waze for Cities** data, which is free
  but restricted to public-sector partners. PANAL cannot join that programme.
  CONAF and SENAPRED can.

### Phase 6 — Respiratory *(autumn 2027, before winter)*

The original PANAL index: SADU excess over seasonal baseline, demographics,
weather. Plus the smoke-to-health link, which by then has a fire dataset to
be tested against.

### Phase 7 — Android, hardening, public API

---

## Egress capacity: the part that needs no traffic API

Live traffic is useful during an event. **Static egress capacity is useful
before one**, and it is computable today from OpenStreetMap plus Censo 2024:

- How many dwellings depend on each exit road.
- Dead ends and single-access neighbourhoods.
- Road width against the dwelling count behind it.

People died in Viña del Mar in narrow, dead-end hillside streets. That
geometry does not change between fire seasons, and knowing it in October is
worth more than knowing about the jam while it is happening.

### Live traffic: what is actually available

| Provider | Verdict |
|---|---|
| **Google Maps** | ❌ Traffic content is **prohibited on non-Google basemaps**. Dead end with MapLibre. |
| **Waze for Cities** | ❌ for PANAL — public-sector partners only, no commercial use. ✅ via Phase 5. |
| **TomTom** | ✅ **Recommended.** 2,500 non-tile requests/day and 50,000 tiles/day free, and explicitly no restriction on non-TomTom basemaps. |

---

## Colour and encoding

### Do not use black for evacuation

Two independent reasons, either one disqualifying:

1. **In wildland fire operations, "the black" is the already-burned area — a
   survival refuge.** Using black to mean *evacuate* inverts a convention
   firefighters rely on to stay alive.
2. In triage, black means deceased or expectant.

Black should be used for what it already means: **the burned area**. That is
genuinely worth rendering — it shows where the fire has passed and where the
safety zones are.

### Align with SENAPRED, do not invent a scale

Chile already has an alert vocabulary that the public and the agencies know:

| Level | Meaning |
|---|---|
| **Alerta Temprana Preventiva** (green) | Monitoring, reinforced surveillance |
| **Alerta Amarilla** (yellow) | Event growing, may exceed local capacity |
| **Alerta Roja** (red) | Critical, all resources mobilised |

PANAL uses these, with these names. Inventing a parallel colour scale during
an emergency is how people misread a map.

### Evacuation: encode with pattern, not colour

Evacuation zones get a **diagonal hatch**, orthogonal to the hazard colour
ramp. This keeps "how bad" and "must you leave" on separate visual channels,
and it survives colour blindness.

### Evidence tiers as opacity

Confirmed by the team: **colour carries hazard, opacity carries confidence**
(T0–T2). This is a sound technique — a value-suppressing uncertainty palette —
with two constraints:

- **Add a redundant channel.** Opacity alone fails WCAG and reads differently
  against light and dark basemaps. Pair it with stroke: solid border for
  confirmed, dashed for unverified.
- **Floor the range.** Below roughly 35% opacity a cell vanishes into the
  basemap and "uncertain" silently becomes "nothing here".

---

## Standing boundary

PANAL publishes a heat map and associated risk information. It does not issue
evacuation orders. Official alerts in Chile are SENAPRED's, through SAE, and
PANAL's role is to surface and amplify them — never to imitate one.

The Phase 5 agency channel is what makes this a design, not a limitation.
