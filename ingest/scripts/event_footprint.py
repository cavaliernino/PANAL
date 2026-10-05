#!/usr/bin/env python3
"""The cells VIIRS saw burning in a past fire — what validate_wui.py tests
the exposure index against.

    python scripts/event_footprint.py --preset rocuant2019
    python scripts/event_footprint.py --all

Writes panal_ingest/reference/events/<preset>.json: the r9 cells, the window
and the products, so a validation can be re-run without the archive. Needs
FIRMS_MAP_KEY (see .env.example).

One event is one sample of 115 cells that sit next to each other, which is
why these exist: the index was validated on Viña 2024 alone, and a lift
measured on one fire says more about that fire than about the index.

Windows are UTC and start where the satellite first saw the fire, not where
the news put it. The 2026 complex was reported on 14 January and its
deadliest front, Penco-Lirquén, ran the night of the 17th; the archive shows
the Ránquil fire burning from the early hours of the 14th. So the fuel for
that validation has to end by the 12th.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panal_ingest import anomaly, viirs  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "panal_ingest" / "reference" / "events"

SP = ("VIIRS_SNPP_SP", "VIIRS_NOAA20_SP")

PRESETS = {
    # bbox is (lon_min, lat_min, lon_max, lat_max). `region` is the
    # build_wui.py region the event is validated inside.
    "vina2024": dict(
        event="Viña del Mar y Quilpué", region="valparaiso",
        start="2024-02-02T15:00", end="2024-02-03T03:00",
        bbox=(-71.80, -33.30, -71.10, -32.85),
        note="Mismo recorte que el replay (web/data/vina2024.json)."),
    "rocuant2019": dict(
        event="Valparaíso, cerros Rocuant y San Roque", region="valparaiso",
        start="2019-12-24T15:00", end="2019-12-25T15:00",
        bbox=(-71.75, -33.15, -71.45, -32.95),
        note="316 viviendas afectadas según el catastro del Serviu."),
    "vina2022": dict(
        event="Viña del Mar, Nueva Esperanza y Forestal", region="valparaiso",
        start="2022-12-22T15:00", end="2022-12-23T15:00",
        bbox=(-71.62, -33.10, -71.42, -32.95),
        note="Entre 200 y 500 viviendas según las cifras de esos días."),
    # Held out by docs/preregistro-combustible.md: chosen by date and place
    # before any fuel-type rule was written or any of these was scored.
    "quilpue2021": dict(
        event="Quilpué, Lago Peñuelas y Las Palmas", region="valparaiso",
        start="2021-01-15T12:00", end="2021-01-17T12:00",
        bbox=(-71.60, -33.20, -71.30, -33.02),
        note="Reservado. 2.630 ha; 25.000 personas evacuadas."),
    "biobio2023": dict(
        event="Biobío y Ñuble: Santa Ana, Santa Juana, Nacimiento",
        region="biobio",
        start="2023-02-02T12:00", end="2023-02-07T12:00",
        bbox=(-73.30, -37.80, -71.90, -36.20),
        note="Reservado. 64.500 ha el incendio Santa Ana; 873 viviendas en Biobío."),
    "biobio2026": dict(
        event="Ñuble y Biobío: Ránquil, Penco-Lirquén, Florida-Bulnes",
        region="biobio",
        start="2026-01-13T12:00", end="2026-01-19T15:00",
        bbox=(-73.20, -37.10, -72.00, -36.30),
        note="21 fallecidos; más de 800 viviendas destruidas."),
}


def footprint(start: dt.datetime, end: dt.datetime, bbox, map_key,
              products=SP):
    """r9 cells with a VIIRS detection in the window, fixed sources excluded.

    Industrial cells are left out here, unlike on the live map, because
    this is a test set: a smelter in it would count as a fire the index was
    supposed to rank.
    """
    import pandas as pd

    frames = []
    for product in products:
        day = start.date()
        while day <= end.date():
            span = min(5, (end.date() - day).days + 1)
            df = viirs.fetch_archive(map_key, bbox, day, days=span,
                                     product=product)
            if len(df):
                frames.append(df)
            day += dt.timedelta(days=span)
    if not frames:
        return [], 0
    df = pd.concat(frames, ignore_index=True)
    df["acq"] = pd.to_datetime(df["acq"], utc=True)
    df = df[df["acq"].between(start, end)]
    df = anomaly.flag(viirs.to_h3(df))
    df = df[~df["industrial"]]
    return sorted(set(df["h3"])), len(df)


def build(name: str, map_key: str) -> dict:
    p = PRESETS[name]
    start = dt.datetime.fromisoformat(p["start"]).replace(tzinfo=dt.timezone.utc)
    end = dt.datetime.fromisoformat(p["end"]).replace(tzinfo=dt.timezone.utc)
    cells, n = footprint(start, end, p["bbox"], map_key)
    out = {
        "meta": {
            "preset": name, "event": p["event"], "region": p["region"],
            "start": p["start"] + "Z", "end": p["end"] + "Z",
            "bbox": list(p["bbox"]), "products": list(SP),
            "detections": n, "note": p["note"],
        },
        "cells": cells,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"{path.name}: {n} detecciones → {len(cells)} celdas r9", file=sys.stderr)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--preset", choices=sorted(PRESETS))
    p.add_argument("--all", action="store_true")
    a = p.parse_args()
    key = os.environ.get("FIRMS_MAP_KEY", "").strip()
    if not key:
        sys.exit("define FIRMS_MAP_KEY (ver .env.example)")
    names = sorted(PRESETS) if a.all else [a.preset] if a.preset else None
    if not names:
        p.error("elige --preset o --all")
    for name in names:
        build(name, key)


if __name__ == "__main__":
    main()
