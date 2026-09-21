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
| **Lookout tower bearing** | seconds | surveyed cross-fix | **First alarm, T1 trust, ~20 bytes** |
| **Fire corps dispatch** | seconds | street address | **Someone called and a unit rolled** — T1, with incident id and committed resources |
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
- **Burn probability** from C2F+K Monte Carlo ensembles — simulated, not just
  inferred from where fires happened to burn before.
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
- **Modelled rate of spread** via **Cell2Fire + Kitral**, the Chilean system
  CONAF's lineage already uses. Open source at `github.com/fire2a/C2F-W`,
  **GPL-3.0 — the same licence as PANAL**, actively maintained. Kitral takes
  slope, wind, fuel moisture and fuel type; elliptical growth with a crown
  fire module; cell-based, so it pairs naturally with H3.
- **Traffic.** Congestion turns an evacuation into a death trap.

### Phase 5 — Agency channel

> **Start this conversation in Phase 1.** The alliance has a long lead time
> and it gates three separate things — lookout towers, Waze for Cities, and
> official zone publishing. The engineering can wait; the relationship cannot.
> The route in is through firefighters who work or have worked at CONAF, and
> through firefighter contacts inside SENAPRED.

An authenticated write path so CONAF and SENAPRED can publish official zones
directly into PANAL. This is also what resolves the alerting boundary: PANAL
never issues an evacuation order; authorities do, through PANAL.

- Authenticated agency role, fully audited, every write attributed.
- Official polygons render as authoritative and visually distinct from
  anything PANAL derived.
- **CONAF lookout towers** as registered observer stations — surveyed
  positions, trained observers, T1 trust at seconds of latency, and a payload
  small enough to arrive by SMS when nothing else does. See
  [`crowdsourcing.md`](crowdsourcing.md).

  ⚠️ **This tier depends entirely on the CONAF alliance**, and not only for
  access: tower entry is *additional work* for operators who already have
  duties. If it is not nearly frictionless it will not get used, and a
  half-used observer network is worse than none because its silence stops
  meaning anything.
- This is the legitimate channel for **Waze for Cities** data, which is free
  and non-commercial but restricted to public-sector partners. PANAL is
  non-commercial, so the only missing piece is the partner.

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

**Both Waze and TomTom are in scope**, fused rather than chosen between.
They are independent probe networks, so their errors are largely independent
and agreement between them is itself a quality signal.

| Provider | Verdict | Available |
|---|---|---|
| **TomTom** | ✅ The independent path, no partnership needed. 2,500 non-tile requests/day and 50,000 tiles/day free, no restriction over non-TomTom basemaps. | **now** |
| **Waze for Cities** | ✅ Free two-way GeoRSS, every 2 minutes. Non-commercial public-sector partners only — PANAL qualifies through CONAF/SENAPRED. Deeper probe density in Chile. | with the alliance |
| **Google Maps** | ❌ Traffic content **prohibited on non-Google basemaps**. Dead end with MapLibre. | — |

Fusion notes: build the TomTom path first since it needs no one's permission,
and design the road-segment model provider-agnostic so Waze slots in beside
it rather than replacing it. Where they disagree on a segment, take the worse
of the two — during an evacuation, an optimistic travel time is the dangerous
error. Attribution requirements differ per provider and must be rendered per
layer.

---

## Resolution: the source sets it, not the zoom

The instinct is that zooming in should shrink the hexagons. H3 will happily
do that, and it would be wrong: a 2 km GOES pixel rendered as 400 m cells
invents precision the sensor never had, which is ground rule 4.

Two rules instead.

**Coarsen out, never refine in.** Aggregating up the H3 hierarchy is exact —
every child belongs to exactly one parent, so FRP and detection counts are
conserved to the digit (verified: 586,568.6 MW and 1,357 detections identical
across r5, r6 and r7 in the Viña replay). Refining down is forbidden in
`pipeline.rollup()`, which raises rather than let it happen by accident.

| Zoom | Level | Cell area |
|---|---|---|
| < 7.5 | r5 | ~253 km² |
| 7.5 – 9.5 | r6 | ~36 km² |
| ≥ 9.5 | r7 | ~5.2 km² |

**Real detail comes from a finer sensor, not a finer grid.** Each source
renders at the resolution it actually has, and they stack:

| Source | Pixel | Honest level | Cell ⌀ / pixel |
|---|---|---|---|
| GOES-East ABI | 2 km | **r7** | 1.41 |
| VIIRS | 375 m | **r9** | **1.07** |
| Lookout cross-fix | — | point + error ellipse | — |
| Official CONAF perimeter | — | the actual polygon | — |

So zooming in does not shrink one layer — it reveals others. A wide GOES
hexagon says *something is burning here, ten minutes ago*; the small VIIRS
cells inside it say *and precisely here, two hours ago*. The difference in
size and age between them **is** the information, and the interface should
let cell size communicate precision rather than disguise it.

**A gap is not an absence.** VIIRS detections arrive as a scatter, not a
blob: one pass over Viña gave 105 cells at r9 in **33 disconnected
components**, 11% of them isolated. Rendered naively that reads as confetti,
and worse, the space between reads as *safe*.

The holes turn out to be tiny — median 201 m, p90 402 m, at most 603 m, all
smaller than the 375 m pixel that produced them. So the fragmentation is a
sampling artefact, not fire-free ground, and dilating by a single H3 ring
collapses those 33 components into 4.

That dilation ships as a separate **inferred extent** layer: flat, neutral,
carrying no intensity value because none was measured there, drawn beneath
the detections and never merged with them. One is observed, the other is a
neighbourhood guess, and a map that blurs the two is lying.

And do not assume the coarse layer covers the gaps — it does not. At the peak
frame only **8 of 17** VIIRS parent cells at r7 coincided with a GOES
detection. More than half of what VIIRS saw, GOES missed entirely. The layers
are complementary, not nested.

The rule that follows: **no colour may read as "safe."** Absence of a cell
means no detection — a fire below the sensor threshold, or hidden by smoke or
cloud, produces exactly the same empty space as no fire at all. The legend
says so in as many words.

**Derived layers are a separate case.** WUI exposure, slope and dwelling
density come from Censo 2024 at block level and a DEM, which genuinely are
fine, so those layers can legitimately live at r9 or r10. An *observation* is
bounded by its sensor; a *derivation* is bounded by its worst input.

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
