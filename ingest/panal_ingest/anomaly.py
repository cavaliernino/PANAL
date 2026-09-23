"""Persistent thermal anomalies — the mines, smelters and flares that read as
permanent fires.

Satellites detect heat, not fire. Northern Chile is full of fixed industrial
sources that trip the algorithm every single pass: Chuquicamata appears in
almost every scene PANAL has looked at, across two satellites and two days,
scattered over ±0.2 km with a stable ~3.7 MW. A wildfire moves and grows. A
smelter does not.

The discriminator is time, not intensity. **A wildfire is bounded; an
industrial source is not.** Even a catastrophic fire occupies one place for
weeks — one or two calendar months. A plant appears in ten or twelve, and
keeps appearing through the austral winter when nothing is burning.

## The mask labels, it never deletes

A real fire can start at a mine, in the yards around it, or in the scrub
beside it. Silently dropping detections there would build a blind spot
exactly where industrial ignition sources sit. So a masked cell is still
carried, still visible, and merely **flagged** — excluded from headline
counts and from anything that would alert a human, never from the record.

That distinction is the difference between a filter and a lie.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

MASK_FILE = Path(__file__).parent / "reference" / "anomaly_mask.json"

# Chile's fire season runs roughly November to March. Everything else is the
# off-season, when a repeated detection has no plausible wildfire explanation.
OFFSEASON_MONTHS = frozenset({4, 5, 6, 7, 8, 9, 10})

# A cell is treated as a fixed source when all three hold.
#
# MIN_DAYS is the one that actually separates industry from agriculture, and
# it was not obvious. Months alone flagged 38 cells in the central valley,
# where recurring *quemas agrícolas* are real fire and must never be masked.
# The distinction is that a fixed plant is detected on many days in the *same
# cell* — El Teniente shows 196 days, Chuquicamata 213 — while agricultural
# burning recurs across a zone but moves between fields, topping out at 9 or
# 10 days in any one cell. Twenty days in a 321 m cell, spread over four
# months including three off-season days, has no wildfire explanation.
#
# These thresholds deliberately under-mask. Industrial noise that leaks
# through stays visible and reviewable; a suppressed real fire does not.
MIN_DAYS = 20
MIN_MONTHS = 4
MIN_OFFSEASON_DAYS = 3


def summarise(df):
    """Per-cell persistence statistics from a long archive of detections.

    Expects the columns `viirs.to_h3` produces: `h3` and `acq`.
    """
    import pandas as pd

    if len(df) == 0:
        return pd.DataFrame(columns=[
            "h3", "detections", "days", "months", "offseason_days",
            "first", "last", "frp_median", "frp_max", "industrial",
        ])

    d = df.copy()
    d["day"] = d["acq"].dt.floor("D")
    # tz_localize(None) first: to_period drops the timezone anyway and warns,
    # and dropping it silently could shift a detection across a month boundary.
    d["month"] = d["acq"].dt.tz_localize(None).dt.to_period("M")
    d["offseason"] = d["acq"].dt.month.isin(OFFSEASON_MONTHS)

    g = d.groupby("h3")
    out = pd.DataFrame({
        "detections": g.size(),
        "days": g["day"].nunique(),
        "months": g["month"].nunique(),
        "offseason_days": g.apply(
            lambda x: x.loc[x["offseason"], "day"].nunique(),
            include_groups=False),
        "first": g["acq"].min(),
        "last": g["acq"].max(),
        "frp_median": g["frp_mw"].median().round(2),
        "frp_max": g["frp_mw"].max().round(2),
    }).reset_index()

    out["industrial"] = (
        (out["days"] >= MIN_DAYS)
        & (out["months"] >= MIN_MONTHS)
        & (out["offseason_days"] >= MIN_OFFSEASON_DAYS)
    )
    return out.sort_values("detections", ascending=False)


def save(summary, path: Path = MASK_FILE, window: str = "") -> dict:
    """Write the flagged cells, with enough context to audit the decision."""
    flagged = summary[summary["industrial"]]
    payload = {
        "meta": {
            "generated": dt.datetime.now(dt.timezone.utc)
                           .isoformat(timespec="seconds").replace("+00:00", "Z"),
            "window": window,
            "rule": {
                "min_days": MIN_DAYS,
                "min_months": MIN_MONTHS,
                "min_offseason_days": MIN_OFFSEASON_DAYS,
                "offseason_months": sorted(OFFSEASON_MONTHS),
            },
            "cells_examined": int(len(summary)),
            "cells_flagged": int(len(flagged)),
            "note": "Cells are flagged, never dropped. A real fire can start "
                    "at an industrial site.",
        },
        "cells": {
            r.h3: {
                "d": int(r.detections), "days": int(r.days),
                "m": int(r.months), "os": int(r.offseason_days),
                "frp": float(r.frp_median),
            }
            for r in flagged.itertuples()
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, separators=(",", ":")))
    tmp.replace(path)
    return payload


_cache: dict | None = None


def load(path: Path = MASK_FILE) -> dict:
    """The flagged cells, keyed by H3 index. Empty if no mask is built yet."""
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            _cache = {"meta": {"cells_flagged": 0}, "cells": {}}
    return _cache


def flag(df, col: str = "h3"):
    """Add an `industrial` column. Rows are marked, never removed."""
    cells = load().get("cells", {})
    out = df.copy()
    out["industrial"] = out[col].isin(cells) if len(out) else False
    return out
