#!/usr/bin/env python3
"""The pre-registered fuel-type test (docs/preregistro-combustible.md).

    python scripts/compare_fuel_rules.py --set desarrollo
    python scripts/compare_fuel_rules.py --set reservados   # once, at the end

Each case is a build whose fuel predates its fire (build_wui.py with
--fuel-year/--fuel-window) and that fire's footprint (event_footprint.py).
Hazard is re-scored with each rule — R0 as built, R1 and R2 from
`fuel.fuel_by_type` with ESA WorldCover class fractions — and the lift is
the protocol's: inhabited cells within three rings of the footprint, top
decile of the region, against chance. Same arithmetic as validate_wui.py.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ingest"))

from panal_ingest import fuel, landcover  # noqa: E402

EVENTS = ROOT / "ingest/panal_ingest/reference/events"
PROCESSED = ROOT / "data/processed"

SETS = {
    "desarrollo": [
        ("rocuant2019", "wui_valparaiso_pre2019"),
        ("vina2022", "wui_valparaiso_pre2022"),
        ("vina2024", "wui_valparaiso_pre2024"),
        ("biobio2026", "wui_biobio_pre2026"),
    ],
    "reservados": [
        ("quilpue2021", "wui_valparaiso_pre2021"),
        ("biobio2023", "wui_biobio_pre2023"),
    ],
}
RULES = ("R0", "R1", "R2")


def fractions_for(cells, region: str):
    """WorldCover fractions for a region's cells, computed once and cached."""
    import pandas as pd

    path = landcover.CACHE / f"fractions_{region}.parquet"
    if path.exists():
        cached = pd.read_parquet(path)
        if set(cells) <= set(cached["h3"]):
            return cached.set_index("h3")
    f = landcover.cells_landcover(cells)
    df = pd.DataFrame([{"h3": c, **v} for c, v in f.items()])
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    return df.set_index("h3")


def lift(df, score_col: str, zone: set) -> float:
    import numpy as np

    d = df.assign(iface=df["h3"].isin(zone))
    top = d.nlargest(int(len(d) * 0.1), score_col)
    return float(top["iface"].sum() / (d["iface"].sum() * 0.1)) if d["iface"].any() else np.nan


def score(df, lc, rule: str):
    import numpy as np

    if rule == "R0":
        f = df["fuel_factor"].astype(float)
    else:
        f = [fuel.fuel_by_type(n, m, lc.loc[h].to_dict() if h in lc.index else None,
                               p, rule)
             for h, n, m, p in zip(df["h3"], df["ndvi"], df["ndmi"], df["frac_precario"])]
        f = np.asarray(f, dtype=float)
    gate = (df["n_vp"] >= 1).astype(float)
    return gate * np.sqrt(df["slope_factor"].clip(0, 1) * np.clip(f, 0, 1))


def main():
    import h3
    import pandas as pd

    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--set", choices=sorted(SETS), required=True)
    a = p.parse_args()

    rows = []
    for preset, build in SETS[a.set]:
        event = json.loads((EVENTS / f"{preset}.json").read_text())
        df = pd.read_parquet(PROCESSED / f"{build}.parquet")
        lc = fractions_for(df["h3"].tolist(), event["meta"]["region"])
        zone = set().union(*(set(h3.grid_disk(c, 3)) for c in event["cells"]))
        row = {"incendio": preset, "interfaz": int(df["h3"].isin(zone).sum()),
               "con cobertura": f"{100 * df['h3'].isin(lc.index).mean():.1f}%"}
        for rule in RULES:
            df[f"hz_{rule}"] = score(df, lc, rule)
            row[rule] = round(lift(df, f"hz_{rule}", zone), 2)
        rows.append(row)

    out = pd.DataFrame(rows)
    print(out.to_string(index=False))
    print("\nmedia geométrica:  " + "   ".join(
        f"{r} {math.exp(sum(math.log(max(v, 1e-3)) for v in out[r]) / len(out)):.2f}x"
        for r in RULES))


if __name__ == "__main__":
    main()
