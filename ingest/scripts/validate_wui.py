#!/usr/bin/env python3
"""Test the exposure index against an event whose outcome we know.

    python scripts/validate_wui.py \
        --wui ../data/processed/wui_valparaiso.parquet \
        --replay ../web/data/vina2024.json

Ground rule 5 says validate before shipping, and publish the finding either
way. This script exists so the negative result below can be re-run rather
than taken on trust.

## What it found, 2026-09-25

No skill. Against the February 2024 Viña del Mar fire:

* Of 173 r9 cells VIIRS saw burning, only **9 were inhabited** — the fire
  ran overwhelmingly through unpopulated terrain.
* Widening to an interface zone three rings out gives 115 inhabited cells.
  Their median index value sits at the **51st percentile** of the region:
  indistinguishable from chance.
* The index's top decile contains **2 of those 115** cells. Chance would
  give 12. The composite is worse than random here.
* Every component alone is no better. Slope, the term with the clearest
  physical basis, puts **0 of 115** in its top decile — even though burned
  cells are genuinely steeper than average (21.9° against 9.8°). They are
  elevated, not extreme.

## Why the test is also wrong

The result is real, but it does not mean quite what it looks like, and the
distinction matters more than the number.

**This index does not predict where a fire starts.** It predicts how bad
things would be if one arrived. The February 2024 fire burned where it did
because of an ignition point and a wind, not because that hillside was the
most dangerous in the region. Ranking the cells that happened to burn
conflates hazard with consequence.

The honest validation is against **structure loss** — did houses burn where
the index said they would — which needs CONAF and SENAPRED damage records,
not a satellite burn footprint. That is a Phase 5 dependency, and it is now
the blocker on calling this index anything at all.

## What is not excused by that

Two weaknesses stand regardless of the test:

* **There is no fuel layer.** The interface is defined by adjacency to
  burnable vegetation and the index does not measure it. A house beside
  dense matorral and the same house surrounded by asphalt score alike.
* **The weights are unvalidated**, and one is suspect: `frac_sin_red_agua`
  carries 25%, yet burned cells had *better* mains coverage than the
  regional median (0.37 against 0.53).

Until this reports a positive result, the index is a research artefact. It
must not be published as a risk product, and nothing in the interface should
imply it ranks danger.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main():
    import h3
    import numpy as np
    import pandas as pd

    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--wui", required=True)
    p.add_argument("--replay", required=True)
    p.add_argument("--rings", type=int, default=3,
                   help="how far out the interface zone reaches (cells)")
    a = p.parse_args()

    wui = pd.read_parquet(a.wui)
    replay = json.loads(Path(a.replay).read_text())
    burned = {c["h"] for pas in replay.get("viirs", []) for c in pas["cells"]}
    if not burned:
        sys.exit("el replay no trae celdas VIIRS")

    zone: set[str] = set()
    for b in burned:
        zone |= set(h3.grid_disk(b, a.rings))
    wui["interface"] = wui["h3"].isin(zone)

    n_int = int(wui["interface"].sum())
    direct = int(wui["h3"].isin(burned).sum())
    print(f"celdas detectadas ardiendo:        {len(burned)}")
    print(f"  de ellas habitadas:              {direct}")
    print(f"zona de interfaz (k={a.rings}):            {n_int} de {len(wui):,}"
          f"  ({100 * n_int / len(wui):.2f}%)")
    if not n_int:
        sys.exit("sin celdas habitadas en la zona")

    vals = wui["wui"].to_numpy()
    near = wui[wui["interface"]]
    pct = [100.0 * (vals < v).mean() for v in near["wui"]]
    print(f"\npercentil del índice en la interfaz: "
          f"mediana p{np.median(pct):.0f}")

    expected = n_int * 0.1
    print(f"\n{'ordenar por':<22}{'en decil sup':>13}{'lift':>8}")
    print("-" * 44)
    for col in ["wui", "hazard", "fragility", "deficit", "slope_deg",
                "relief_m", "frac_precario", "frac_vulnerable",
                "frac_sin_red_agua", "n_vp"]:
        if col not in wui.columns:
            continue
        top = wui.nlargest(int(len(wui) * 0.1), col)
        got = int(top["interface"].sum())
        print(f"{col:<22}{got:>13}{got / expected:>7.2f}x")
    print(f"\n(azar daría {expected:.0f})")

    lift = int(wui.nlargest(int(len(wui) * 0.1), "wui")["interface"].sum()) / expected
    print("\nVEREDICTO: " + (
        "el índice supera el azar." if lift > 1.5 else
        "sin habilidad demostrada. No publicar como producto de riesgo."))


if __name__ == "__main__":
    main()
