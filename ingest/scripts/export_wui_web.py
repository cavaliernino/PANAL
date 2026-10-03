#!/usr/bin/env python3
"""The exposure index, cut down to what the web map needs.

    python scripts/export_wui_web.py \
        --wui ../data/processed/wui_valparaiso.parquet \
        -o ../web/data/wui_valparaiso.json

Only inhabited cells: the map answers "where do people live in this
condition", and the gate already scores empty land at zero.

Cells are not all one size. The census grid lands sparse rural entities at
coarser resolutions (r5-r8) rather than inventing where their few houses
are, and each H3 index says its own resolution. The page has to know that:
a coarse cell's colour describes a handful of houses spread over many
square kilometres.

Percentiles are taken over the same set `wui.priority` ranks — every cell
with a hazard score — so a cell the map calls top decile is one the
published count includes. Cells with no fuel observation carry no hazard
rank at all, never a low one.

Refuses the SENAPRED-enriched build. Its layers are public, but the
permission being sought from SENAPRED is precisely for public use.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from panal_engine import wui  # noqa: E402

COMUNAS = ROOT / "data/cache/censo/Cartografia_censo2024_Pais_Comunal.parquet"
OSM = ROOT / "data/cache/osm/chile-latest.osm.pbf"

# What the page has to say about where these numbers come from. Kept here,
# beside the export, so a rebuild that changes a source changes the claim.
SOURCES = {
    "censo": "Censo 2024, INE — viviendas y personas por manzana",
    "terreno": "Copernicus GLO-30, pendiente a 30 m",
    "combustible": "Sentinel-2, temporada seca feb–mar 2026",
}

SMALL = {"de", "del", "la", "las", "los", "y", "el"}


def _nombre(s: str) -> str:
    words = str(s).lower().split()
    return " ".join(w if (i and w in SMALL) else w[:1].upper() + w[1:]
                    for i, w in enumerate(words))


def _pct(values: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """Share of `ref` strictly below each value, 0-100, floored."""
    ref = np.sort(ref)
    return np.floor(100 * np.searchsorted(ref, values, side="left")
                    / len(ref)).astype(int)


def _r(v, nd):
    return None if v is None or v != v else round(float(v), nd)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--wui", required=True)
    p.add_argument("--region", default="Región de Valparaíso")
    p.add_argument("--lift", type=float, required=True,
                   help="lift de la amenaza en la última corrida de "
                        "validate_wui.py contra el build que se exporta")
    p.add_argument("-o", "--out", required=True)
    a = p.parse_args()

    s = pd.read_parquet(a.wui)

    for col in ("response_factor", "ignition"):
        if col in s.columns and s[col].notna().any():
            sys.exit(f"{a.wui} trae `{col}`: es el build con capas SENAPRED. "
                     "No se publica sin su permiso explícito.")

    scored = s[s["wui"].notna()]
    both = set(wui.priority(s)["h3"])

    cells = s[s["inhabited"]].copy()
    ranked = cells["wui"].notna()
    cells["hz"] = None
    cells.loc[ranked, "hz"] = _pct(cells.loc[ranked, "wui"].to_numpy(),
                                   scored["wui"].to_numpy())
    cells["cs"] = _pct(cells["consequence"].to_numpy(),
                       scored["consequence"].to_numpy())

    comunas = pd.read_parquet(COMUNAS, columns=["CUT", "COMUNA"])
    names = {int(c): _nombre(n) for c, n in zip(comunas["CUT"], comunas["COMUNA"])}
    cuts = sorted({int(c) for c in cells["cut"].dropna()})
    cut_idx = {c: i for i, c in enumerate(cuts)}

    rows = []
    for r in cells.itertuples():
        rows.append([
            r.h3,
            None if r.hz is None else int(r.hz),
            int(r.cs),
            int(r.n_vp), int(r.n_per),
            _r(r.slope_deg, 0),
            _r(r.fuel_factor, 2),
            _r(r.egress_deficit, 2) if r.has_egress else None,
            cut_idx.get(int(r.cut)) if r.cut == r.cut else None,
            1 if r.h3 in both else 0,
        ])

    prio = cells[cells["h3"].isin(both)]
    w = wui.DEFAULT
    # The public build has no response term, so its weight is shared out
    # over the rest — exactly what consequence_of does per cell.
    terms = {"egreso": w.egress, "precariedad": w.precarious,
             "vulnerabilidad": w.vulnerable, "sin_red_agua": w.no_water}
    t = sum(terms.values())

    out = {
        "meta": {
            "generated": dt.datetime.now(dt.timezone.utc)
                           .isoformat(timespec="seconds").replace("+00:00", "Z"),
            "region": a.region,
            "res_max": 9,
            "res_cells": {str(k): int(v) for k, v in
                          cells["res"].value_counts().sort_index().items()},
            "cells": len(rows),
            "ranked": int(ranked.sum()),
            "unobserved": int((~ranked).sum()),
            "priority": {
                "cells": len(prio),
                "viviendas": int(prio["n_vp"].sum()),
                "personas": int(prio["n_per"].sum()),
                "egreso_conocido": int(prio["has_egress"].sum()),
            },
            "validation": {
                "hazard_lift": a.lift,
                "event": "incendio de Viña del Mar y Quilpué, 2 feb 2024",
                "consequence": None,
            },
            "consequence_weights": {k: round(v / t, 3) for k, v in terms.items()},
            "sources": {
                **SOURCES,
                "egreso": "OpenStreetMap, extracto " + dt.date.fromtimestamp(
                    OSM.stat().st_mtime).isoformat() if OSM.exists()
                    else "OpenStreetMap",
            },
            "comunas": [names.get(c, str(c)) for c in cuts],
        },
        "cols": ["h", "hz", "cs", "viv", "per", "pend", "comb", "egr",
                 "comuna", "prio"],
        "rows": rows,
    }

    path = Path(a.out)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    tmp.replace(path)

    m = out["meta"]
    print(f"{path}  ({path.stat().st_size / 1024:.0f} KB)", file=sys.stderr)
    print(f"  {m['cells']:,} celdas habitadas · {m['ranked']:,} con amenaza · "
          f"{m['unobserved']:,} sin combustible observado", file=sys.stderr)
    pr = m["priority"]
    print(f"  prioridad: {pr['cells']} celdas · {pr['viviendas']:,} viviendas · "
          f"{pr['personas']:,} personas · egreso conocido en "
          f"{pr['egreso_conocido']}/{pr['cells']}", file=sys.stderr)


if __name__ == "__main__":
    main()
