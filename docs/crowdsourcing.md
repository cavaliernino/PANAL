# Crowdsourced first alarm

**Status: specification. Phase 3.**

A satellite cannot see a fire in its first ten minutes. A person standing in
front of it can. This is the only layer in PANAL with sub-minute latency, and
it is also the only one an adversary can write to — so the design has to earn
every bit of trust it claims.

---

## The burst

A report is not a photo. It is a **burst**: several frames captured over
roughly 30–60 seconds, inside the app, each frame carrying its own sensor
telemetry.

```
frame[i] = { image, timestamp, gps, compass bearing, device pitch, accuracy }
```

Capture is **in-app only**. No gallery upload, no file picker. Server-side
timestamp, plus platform attestation (Play Integrity / App Attest) to
establish the frames came from a real device running a real build.

### What the burst kills for free

The successive-frames idea removes several fraud classes at once, without
needing a model to judge anything:

1. **A downloaded or screenshotted image cannot produce a coherent burst.**
   Multiple frames with consistent, drifting sensor telemetry and natural
   handheld jitter is a hard artefact to synthesise. A single JPEG is trivial.
2. **Smoke moves.** Between frames a real plume changes shape, drifts and
   grows. A photo of a photo does not. This is a *physical* check on live
   capture — cheap, robust, and independent of any classifier.
3. **EXIF forgery stops mattering.** We never trust file metadata. Location
   and time come from the device session and the server.
4. **Plume direction can be checked against wind.** The drift observed across
   frames should agree with NASA POWER wind for that cell. A plume blowing the
   wrong way is a strong fraud signal.

### The part that makes it more than a report

Each frame has a **compass bearing**. Two bursts from different reporters give
two lines of position, and their intersection locates **the fire**, not the
reporter.

This is a cross-bearing fix — the same method fire lookouts have used with an
Osborne Firefinder for a century, with the towers replaced by whoever happens
to be nearby. A single burst gives a bearing and a distance estimate; two give
a fix; three give a fix with residual error you can report honestly.

A crowd fix can be produced within **seconds** of a fire being visible, on a
new fire, with no satellite involved. That is the whole point of the layer.

---

## Trust tiers

Never a boolean. Every cell carries a tier, rendered as opacity plus stroke.

| Tier | Source | Effect |
|---|---|---|
| **T0** | Satellite (GOES / VIIRS) | Paints the cell |
| **T1** | Official — CONAF / SENAPRED, **including lookout towers** | Authoritative, overrides all |
| **T2** | Corroborated crowd | Raises cell confidence |
| **T3** | Single uncorroborated burst | Shown as unverified. Triggers nothing. |

Promotion from T3 to T2 requires corroboration, and corroboration is a
**weight, not a gate**:

- Independent reporters from distinct locations, with consistent bearings.
- Agreement with a satellite detection inside a radius and time window.
- SINCA PM2.5 rising downwind.
- Reporter reputation, earned from previously corroborated bursts. New
  accounts carry low weight, and that is not a punishment, it is arithmetic.

A vision classifier filters obvious non-fire. It is a **filter, not a gate** —
assume from day one that it is defeatable, and never let it be the only thing
standing between a bad report and a rendered cell.

**Human moderation is required** before anything reaches T2 in a populated
area. The precedent that works is Watch Duty in the United States: trusted
humans in the loop, not full automation. A crowd report never auto-escalates.

---

## Fixed observer stations — CONAF lookout towers

The best version of the cross-bearing idea is not the crowd. It is a
**surveyed station with a trained observer**, and CONAF already operates a
network of them.

A lookout tower beats every other source on the one metric that matters for
initial attack:

| | Crowd burst | Lookout tower |
|---|---|---|
| Observer position | GPS, metres of error, unverified | **Surveyed, known to the centimetre** |
| Observer | anyone | **trained, accountable** |
| Trust tier | T3 → T2 with corroboration | **T1 immediately** |
| Latency | seconds | seconds |

Because the station's position is *known*, a single azimuth is already a line
of position with no estimation error in its origin. Two towers give a fix
whose only error is angular. This is the Osborne Firefinder method with the
towers it was designed for, and many lookouts already have an alidade.

### Why this is the most resilient input in the system

**A bearing is about twenty bytes.** Where a photo burst needs a working data
connection, a bearing survives almost anything: SMS, a radio call relayed by a
dispatcher and typed in, a satellite messenger. In the conditions where PANAL
matters most — towers congested, power out, a fire between the observer and
the nearest cell site — the bearing gets through and the photograph does not.

Design accordingly:

- **Station registry**: surveyed position, elevation, horizon mask, the sectors
  each tower can actually see.
- **Bearing entry**: azimuth, optional elevation angle and distance estimate.
  The interface is a compass dial and nothing else.
- **Out-of-band paths are first class**, not fallbacks: SMS gateway and a
  dispatcher console for radio-relayed reports.
- **Automatic fix** when two or more stations report consistent bearings inside
  a time window, with the residual error published rather than hidden.
- A tower's horizon mask is also **negative evidence**: if a tower that can see
  a sector reports nothing, that is information.

### The binding constraint is the operator's time, not the technology

This layer is cheap to build and it is the highest-value non-satellite input
in the project. It will still fail if it is designed as though tower
operators were waiting for something to do.

Entering a bearing is **additional work on top of existing duties**. That sets
hard requirements:

- **Under ten seconds, end to end.** Open, dial, send. No login per report, no
  form, no free text. Anything longer competes with their actual job and
  loses.
- **Never in the critical path.** Their first obligation is the radio call to
  CONAF dispatch. PANAL must never sit between an observer and that call.
- **The lowest-friction path may not be the tower at all.** Operators already
  radio bearings to dispatch. A **dispatcher console** lets the person
  receiving that call enter it, adding zero burden to the tower. Build that
  first; the tower-side app is the optimisation, not the starting point.
- **Give something back.** An operator who sends a bearing should immediately
  see the resulting cross-fix and what other towers reported. Reciprocity is
  what sustains voluntary data entry; pure extraction does not.

A half-adopted observer network is worse than none, because a tower's silence
only carries information if that tower reliably reports.

---

## Rate limiting

Handled in the app rather than at the edge, and in a catastrophic area the
**cell network is itself the binding rate limit** — towers burn, congest, or
lose power long before a server would.

That has a consequence worth designing for rather than discovering:

- **Store and forward.** Bursts queue on the device and upload when signal
  returns. A report from the worst-hit area may arrive hours late.
- **Timestamp at capture, never at receipt.** A late burst is evidence about
  the moment it was taken. Treating arrival time as event time would put the
  fire in the wrong place at the wrong hour — exactly the kind of error that
  looks authoritative and is not.
- **Small payloads.** Compressed stills, resumable upload, no video-first.
  Live streaming is the least likely thing to survive the conditions it is
  most needed in. A burst of stills gets through; a stream does not.

---

## Adversarial cases to design against

- **Panic injection.** Coordinated false reports to trigger an evacuation.
  Mitigated by tiering, corroboration, moderation, and by PANAL never issuing
  evacuation orders at all.
- **Suppression.** Flooding a real fire's cell with contradicting reports.
  Reputation weighting and satellite corroboration make this expensive.
- **Reporter safety.** A geotagged burst says *a person is standing in a fire
  zone*. Never publish exact reporter location or identity; fuzz to the H3
  cell and keep the precise fix server-side.
- **Evidence handling.** Photographs of an ignition may be evidence in an
  arson investigation. Chilean forest fires are overwhelmingly human-caused
  and CONAF investigates cause, so retention, chain of custody and lawful
  disclosure need a policy before launch, not after the first subpoena.
- **False reporting is an offence** in Chile. The terms of service should say
  so plainly, in Spanish, before the first capture.

---

## What this layer is not

It is not an alerting system, and it is not a substitute for calling
emergency services. The app should make reporting to **CONAF (130)** or
SENAPRED the primary action and PANAL's own capture secondary — a person
watching a fire start should be talking to a dispatcher, not curating a
dataset.

PANAL's value is that the burst also lands in a map that a hundred other
people and, through Phase 5, the agencies themselves can see.
