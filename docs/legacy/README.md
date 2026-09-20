# Legacy — NASA Space Apps Challenge COVID-19, 2020

This directory preserves the original PANAL, built in 48 hours on
30–31 May 2020 for the **Human Factors** challenge, Latin America and the
Caribbean region. It won the **Galactic Impact Award** — *"the solution with
the most potential to improve life on Earth or in the universe."*

Team: Carolina Retamal, Marcos Maldonado, Nino Bozzi, Patricio Alarcón.

## Where the 2020 code lives

| What | Where |
|---|---|
| Android app, exactly as submitted | git tag `v0.1-spaceapps-2020` |
| Django backend branch, verbatim incl. the committed virtualenv | git tag `v0.1-backend-2020` |
| Django backend, own source only (13 files) | `backend-2020/` in this directory |
| Android app, carried forward and being modernised | `/android` at the repo root |

```bash
git show v0.1-spaceapps-2020          # the submission
git checkout v0.1-backend-2020        # the original backend branch
```

## What the 2020 code actually did

Worth being precise about, because the gap between the idea and the
implementation *is* the roadmap.

The submission described a georeferenced hexagonal risk index weighting
weather (15%), demographics (35%) and health (50%).

The code did not implement it:

- `backend-2020/panal/views.py` is the entire backend logic:
  `HttpResponse("{[50,50,50,50,50]}")` — a constant.
- The app displayed a hardcoded `50%`
  (`MapsActivity.kt`, `uiThread { changePercent(50) }`).
- Every hexagon was painted the same green. There was no heat map.
- There was no data ingestion of any kind.
- `SplashActivity` and `AlertActivity` are unmodified Android Studio
  fullscreen-activity templates.

Known defects in the 2020 Android code, kept here as documentation:

- `drawHexagon()` calls `latLngList.clear()` internally, so after drawing the
  7-hexagon grid the list holds only the **vertices of the last hexagon**, not
  the grid. `getPointInfo(latLngList)` therefore received meaningless input.
- `getPointInfo()` ignored its parameter anyway and sent a hardcoded JSON
  payload of zeros.
- The response from the server was discarded before use.
- The request went over plaintext `http://` to a personal host.
- A single `polygon` field was overwritten on every draw, so individual cells
  could never be recoloured or cleared — a structural blocker for a heat map.

None of this diminishes what the project was. A 48-hour hackathon produces a
thesis and a demo, and the thesis was strong enough to win. This repository
exists to finally build it.

## Why the backend branch was removed

The `backend` branch committed a complete Python 2.7 virtualenv — Django 1.11
and its full dependency tree, roughly 13 MB — around 13 files of actual
project source. The branch was deleted from the repository and preserved in
the tag `v0.1-backend-2020`.

`backend-2020/` here holds the own source only, with one modification: the
Django `SECRET_KEY` in `panalbackend/settings.py` has been redacted. The
original value is in the tag.

## Security note

The Google Maps API key `AIzaSy…fLXA` was committed in plaintext in commit
`5fbffd7` (30 May 2020) and was publicly readable for six years. It was
**revoked** during the 2026 Phase 0 cleanup.

It remains visible in git history, and that is deliberate: rewriting the
history of an award-winning public project to hide a key that has already been
revoked would destroy the historical record to solve a problem that revocation
already solved. Revocation is the fix. History is the record.
