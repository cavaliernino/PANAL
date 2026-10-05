#!/usr/bin/env python3
"""Test the exposure index against an event whose outcome we know.

    python scripts/validate_wui.py \
        --wui ../data/processed/wui_valparaiso.parquet \
        --replay ../web/data/vina2024.json

    # any fire with a footprint from event_footprint.py
    python scripts/validate_wui.py \
        --wui ../data/processed/wui_biobio_pre2026.parquet \
        --event panal_ingest/reference/events/biobio2026.json

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

## Since then

* **2026-09-25, with the Sentinel-2 fuel layer: 3.83×.** 44 of the 115
  interface cells in the top decile, median p77. Hazard alone 3.39×. The
  hazard half clears the bar above.
* **2026-10-02, re-run before publishing the web map:** unchanged, 3.83×,
  against a full rebuild with the current weights. Consequence weights moved
  on 30 September and hazard does not use them, as it should not.

* **2026-10-05, with fuel from before the fire.** Every run above ranked
  the 2024 fire by fuel from February–March **2026** — the landscape the
  fire left, not the one it found. Re-scored with the same slope and census
  and only the fuel date changed:

  | fuel from | in top decile | lift | median pct |
  |---|---|---|---|
  | Jan 2024, up to the day before | 47 | **4.09×** | p78 |
  | Feb–Mar 2023, the season before | 40 | 3.48× | p83 |
  | Feb–Mar 2024, after the fire | 41 | 3.57× | p74 |
  | Feb–Mar 2026, as published | 44 | 3.83× | p77 |

  The hazard half survives: the post-fire landscape did not manufacture the
  result. But the figure worth quoting is the pre-fire one, so builds now
  record each cell's fuel scene and this script checks it against the
  event date.

* **2026-10-05, rebuilt** with three measurement bugs fixed — slope at DEM
  tile edges, egress counting shape vertices, and a scene search that kept
  the 40 newest scenes and took them for the window. Fuel coverage went
  from 90.4% to 99.8% of cells. Pre-fire fuel (1 Jan - 1 Feb 2024):
  **3.91×**, 45 of 115, median p84. The same build with 2026 fuel: 3.30×.
  The table above was measured before the search fix.

* **2026-10-05, four fires.** One fire is one sample of cells that sit
  next to each other, so three more were added (`event_footprint.py`), each
  with fuel from the five weeks before it:

  | fire | interface cells | in top decile | lift | median |
  |---|---|---|---|---|
  | Valparaíso, Rocuant–San Roque, Dec 2019 | 47 | 13 | 2.77× | p81 |
  | Viña del Mar, Nueva Esperanza, Dec 2022 | 105 | 7 | **0.67×** | p62 |
  | Viña del Mar–Quilpué, Feb 2024 | 115 | 45 | 3.91× | p84 |
  | Ñuble–Biobío complex, Jan 2026 | 1,664 | 204 | **1.23×** | p59 |

  The pattern holds at k = 0, 1 and 3 rings. **The hazard half works in
  two fires of four**, the two that look like what it was built for: fire
  running out of cured scrub on steep ground into sparse settlement (2024
  interface cells hold a median 1.9 dwellings, 20.7° slope, fuel 0.45).

  It fails two ways, and both are measurement, not tuning:

  - **Dense settlement.** The 2022 fire burned through Nueva Esperanza's
    *tomas*: a median 241 dwellings per interface cell. There the houses
    are the fuel, and a cell's NDVI is diluted by roofs.
  - **Plantations.** In Biobío the interface reads NDVI 0.61 yet fuel 0.26,
    under the region's 0.32: the NDMI dryness term scores a green pine or
    eucalyptus canopy as moist, and those burn in a heat wave regardless.

  Biomass alone would lift Biobío to 1.71× and Viña 2022 to 0.95× while
  dropping Valparaíso 2019 and 2024 to 2.13× and 3.39×. No one formula
  wins: what is missing is fuel *type* — scrub, grass, plantation, built-up
  — which is CONAF's Catastro, or a public land-cover proxy. Not tuned on
  four events.

Consequence still has no test at all — a burn footprint cannot give it one.
So the public map leads with hazard and labels consequence, and anything
derived from it, as unvalidated wherever it appears.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

# What the public map quotes. Written only by a run that passes, so a figure
# on the page always traces back to a validation that was actually run.
RECORD = (Path(__file__).resolve().parents[1] / "panal_ingest" / "reference"
          / "events" / "validation.json")


def main():
    import h3
    import numpy as np
    import pandas as pd

    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--wui", required=True)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--replay", help="un replay de build_replay.py")
    src.add_argument("--event", help="una huella de event_footprint.py")
    p.add_argument("--rings", type=int, default=3,
                   help="how far out the interface zone reaches (cells)")
    p.add_argument("--record", action="store_true",
                   help="guarda el resultado en reference/events/"
                        "validation.json, que es lo que cita el mapa público. "
                        "Solo con --event, k=3 y combustible anterior al evento")
    a = p.parse_args()
    if a.record and (not a.event or a.rings != 3):
        p.error("--record va con --event y el k=3 del protocolo")

    wui = pd.read_parquet(a.wui)
    if a.replay:
        replay = json.loads(Path(a.replay).read_text())
        burned = {c["h"] for pas in replay.get("viirs", []) for c in pas["cells"]}
        event_day = replay["frames"][0]["t"][:10].replace("-", "")
    else:
        event = json.loads(Path(a.event).read_text())
        burned = set(event["cells"])
        event_day = event["meta"]["start"][:10].replace("-", "")
        print(f"evento: {event['meta']['event']} ({event['meta']['start'][:10]})")
    if not burned:
        sys.exit("el evento no trae celdas VIIRS")

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

    # Fuel observed after the event describes the landscape the fire left.
    # The lift may survive it (it did, 2026-10-05) but it is not a test.
    fuel_ok, fuel_span = False, None
    if "fuel_scene" in wui.columns:
        day = wui["fuel_scene"].str.split("_").str[2]
        late = day.notna() & (day >= event_day)
        late_int = int((late & wui["interface"]).sum())
        seen = day.dropna()
        fuel_ok, fuel_span = not late_int, f"{seen.min()}..{seen.max()}"
        print(f"\ncombustible: escenas {seen.min()}..{seen.max()}, "
              f"evento {event_day}")
        if late_int:
            print(f"  ! {late_int} de {n_int} celdas de la interfaz con "
                  "combustible posterior al evento: esto no es una "
                  "validación. Rehacer con --fuel-year/--fuel-window "
                  "anteriores al incendio.")
    else:
        print("\n! el build no registra la escena del combustible: no se "
              "puede descartar que sea posterior al evento")

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

    got = int(wui.nlargest(int(len(wui) * 0.1), "wui")["interface"].sum())
    lift = got / expected
    print("\nVEREDICTO: " + (
        "el índice supera el azar." if lift > 1.5 else
        "sin habilidad demostrada. No publicar como producto de riesgo."))

    if a.record:
        if not fuel_ok:
            sys.exit("no se registra: el combustible no es anterior al evento")
        meta = event["meta"]
        record = json.loads(RECORD.read_text()) if RECORD.exists() else {}
        record[meta["preset"]] = {
            "event": meta["event"], "start": meta["start"],
            "region": meta["region"], "interface_cells": n_int,
            "in_top_decile": got, "expected": round(expected, 1),
            "lift": round(lift, 2), "median_pct": int(round(np.median(pct))),
            "fuel_scenes": fuel_span, "rings": a.rings,
            "validated": dt.date.today().isoformat(),
        }
        RECORD.write_text(json.dumps(dict(sorted(
            record.items(), key=lambda kv: kv[1]["start"])),
            ensure_ascii=False, indent=1) + "\n")
        print(f"registrado en {RECORD.name}")


if __name__ == "__main__":
    main()
