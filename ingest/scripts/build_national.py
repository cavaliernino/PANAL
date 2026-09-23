#!/usr/bin/env python3
"""Snapshot of current fire detection across Chile, for the national view.

    python scripts/build_national.py -o ../web/data/national.json

Emits H3 indices rather than polygons: deck.gl's H3HexagonLayer takes cell
ids directly and builds the geometry on the GPU, which is the reason the
national view can afford resolutions the replay could not.

Run it on a schedule. The page shows the data's age, and treats an empty
result as a confident "nothing detected", not as a failure — for eight
months of the year that is the correct answer.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panal_ingest import anomaly, goes, pipeline, viirs  # noqa: E402

GOES_LEVELS = (7, 6, 5)
VIIRS_PRODUCTS = ("VIIRS_NOAA20_NRT", "VIIRS_SNPP_NRT", "VIIRS_NOAA21_NRT")
VIIRS_WINDOW = "7d"          # the client filters by age within this
EXTENT_RINGS = 1             # inferred extent, same rule as the replay


def collect_goes(now):
    """Latest scan, rolled up the hierarchy for wider viewports."""
    try:
        scan = goes.latest_scan(now)
    except Exception as exc:                            # noqa: BLE001
        print(f"  ! GOES no disponible: {exc}", file=sys.stderr)
        return None

    df = pipeline.ingest_scan(scan)
    agg = pipeline.aggregate(df) if len(df) else df

    levels = {}
    if len(agg):
        levels["7"] = [
            {"h": r.h3, "n": int(r.detections), "f": round(float(r.frp_mw), 1),
             "c": r.best_confidence}
            for r in agg.itertuples()
        ]
        for lvl in GOES_LEVELS[1:]:
            rolled = pipeline.rollup(agg, lvl)
            levels[str(lvl)] = [
                {"h": r.h3, "n": int(r.detections), "f": round(float(r.frp_mw), 1),
                 "c": r.best_confidence}
                for r in rolled.itertuples()
            ]
    else:
        for lvl in GOES_LEVELS:
            levels[str(lvl)] = []

    return {
        "scan_start": scan.start.isoformat().replace("+00:00", "Z"),
        "scan_end": scan.end.isoformat().replace("+00:00", "Z"),
        "satellite": scan.bucket.replace("noaa-", "").upper(),
        "levels": levels,
    }


def collect_viirs(now):
    """Recent VIIRS across Chile, each cell carrying its age in minutes."""
    import h3
    import pandas as pd

    frames = []
    for product in VIIRS_PRODUCTS:
        try:
            frames.append(viirs.fetch_recent(product, VIIRS_WINDOW))
        except Exception as exc:                        # noqa: BLE001
            print(f"  ! {product}: {exc}", file=sys.stderr)
    if not frames:
        return {"window": VIIRS_WINDOW, "cells": [], "halo": []}

    df = viirs.to_h3(pd.concat(frames, ignore_index=True))
    if len(df) == 0:
        return {"window": VIIRS_WINDOW, "cells": [], "halo": []}

    # Flag known fixed industrial sources. Flag, never drop: a real fire can
    # start at a mine, and a silent filter there would build a blind spot
    # exactly where industrial ignition sources are concentrated.
    df = anomaly.flag(df)

    order = goes.CONFIDENCE_ORDER
    cells = {}
    for row in df.itertuples():
        c = cells.setdefault(row.h3, {
            "h": row.h3, "n": 0, "f": 0.0, "c": None, "age": None,
            "ind": bool(row.industrial),
        })
        c["n"] += 1
        c["f"] += float(row.frp_mw)
        if c["c"] is None or order.index(row.confidence) > order.index(c["c"]):
            c["c"] = row.confidence
        age = int((now - row.acq).total_seconds() // 60)
        c["age"] = age if c["age"] is None else min(c["age"], age)
    for c in cells.values():
        c["f"] = round(c["f"], 1)

    # Each halo cell inherits the freshest age among the detections that
    # justify it, so the client can filter it with the same age slider and
    # an inferred cell can never outlive the observation behind it.
    halo: dict[str, int] = {}
    for cell, rec in cells.items():
        if rec["ind"]:
            continue            # no inferred extent around a smelter
        for n in h3.grid_disk(cell, EXTENT_RINGS):
            if n in cells:
                continue
            prev = halo.get(n)
            halo[n] = rec["age"] if prev is None else min(prev, rec["age"])

    return {
        "window": VIIRS_WINDOW,
        "industrial_cells": sum(1 for c in cells.values() if c["ind"]),
        "oldest_min": max(c["age"] for c in cells.values()),
        "newest_min": min(c["age"] for c in cells.values()),
        "cells": list(cells.values()),
        "halo": [{"h": h, "age": a} for h, a in sorted(halo.items())],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("-o", "--out", required=True)
    a = p.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    print("GOES…", file=sys.stderr)
    g = collect_goes(now)
    print("VIIRS…", file=sys.stderr)
    v = collect_viirs(now)

    data = {
        "meta": {
            "generated": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "goes_product": goes.PRODUCT,
            "goes_levels": [int(k) for k in GOES_LEVELS],
            "viirs_res": viirs.RESOLUTION["viirs"],
            "viirs_products": list(VIIRS_PRODUCTS),
            "viirs_extent_rings": EXTENT_RINGS,
            "anomaly_mask": {
                "cells": anomaly.load()["meta"].get("cells_flagged", 0),
                "window": anomaly.load()["meta"].get("window", ""),
                "rule": anomaly.load()["meta"].get("rule", {}),
            },
        },
        "goes": g,
        "viirs": v,
    }

    # Atomic write. This runs unattended every ten minutes against a page
    # that reloads on its own, so a crash mid-write would serve truncated
    # JSON and break the map. Write beside the target, then rename — rename
    # is atomic on the same filesystem, so a reader sees either the old file
    # or the new one, never half of either.
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":")))
    tmp.replace(out)

    ng = len(g["levels"]["7"]) if g else 0
    print(f"\n{out}  ({out.stat().st_size/1024:.0f} KB)", file=sys.stderr)
    print(f"  GOES  {ng:>4} celdas r7"
          + (f"  (barrido {g['scan_start'][11:16]} UTC)" if g else "  — sin barrido"),
          file=sys.stderr)
    ind = v.get("industrial_cells", 0)
    if ind:
        print(f"  máscara industrial: {ind} celda(s) marcada(s) "
              f"de {len(v['cells'])}", file=sys.stderr)
    print(f"  VIIRS {len(v['cells']):>4} celdas r9 en {VIIRS_WINDOW}"
          + (f", la más reciente hace {v['newest_min']} min" if v["cells"] else ""),
          file=sys.stderr)
    if not ng and not v["cells"]:
        print("  sin detecciones en territorio chileno — estado normal "
              "fuera de temporada", file=sys.stderr)


if __name__ == "__main__":
    main()
