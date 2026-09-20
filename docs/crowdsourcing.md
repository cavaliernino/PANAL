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
| **T1** | Official (CONAF / SENAPRED) | Authoritative, overrides all |
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
