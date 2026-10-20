#!/usr/bin/env python3
"""The exposure index for all of Chile: one file per region, and a summary.

    python scripts/export_wui_chile.py -o ../web/data/chile

Reads the per-region builds (build_wui.py --region <id>, one per region;
Biobío and Ñuble are the one `biobio` build the regional map publishes)
and ranks every cell against the whole country, not its region. That is
the point of the national map: the same colour means the same thing in
Arica and in Aysén, so a region can be set beside the rest.

Writes:
  <region>.json   the same shape export_wui_web.py writes, ranked nationally
  resumen.json    the light one: inhabited cells summed up to H3 r6, and a
                  line per region with the homes in the country's top decile

Summing is exact, so the summary can be coarsened further on the page
without changing a count. Cells the census already put at r6 or coarser
stay as they are.

The index was tested only against fires in Valparaíso, Biobío and Ñuble.
Everywhere else it is the same arithmetic on the same sources, untested,
and the summary says which regions are which.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import h3
import numpy as np
import pandas as pd

from export_wui_web import (_fuel_source, export, refuse_senapred, write,
                            ROOT, SOURCES, VALIDATION)

sys.path.insert(0, str(ROOT / "ingest"))
from panal_ingest.fuel import DEFAULT_WINDOW  # noqa: E402

PROCESSED = ROOT / "data/processed"

# North to south. (CUT region code, id, name, build it comes from.)
REGIONS = [
    (15, "arica", "Arica y Parinacota", "arica"),
    (1, "tarapaca", "Tarapacá", "tarapaca"),
    (2, "antofagasta", "Antofagasta", "antofagasta"),
    (3, "atacama", "Atacama", "atacama"),
    (4, "coquimbo", "Coquimbo", "coquimbo"),
    (5, "valparaiso", "Valparaíso", "valparaiso"),
    (13, "metropolitana", "Metropolitana", "metropolitana"),
    (6, "ohiggins", "O'Higgins", "ohiggins"),
    (7, "maule", "Maule", "maule"),
    (16, "nuble", "Ñuble", "biobio"),
    (8, "biobio", "Biobío", "biobio"),
    (9, "araucania", "La Araucanía", "araucania"),
    (14, "los_rios", "Los Ríos", "los_rios"),
    (10, "los_lagos", "Los Lagos", "los_lagos"),
    (11, "aysen", "Aysén", "aysen"),
    (12, "magallanes", "Magallanes", "magallanes"),
]

# The validation record keys its fires by build, so Ñuble's fires are
# filed under biobio along with Biobío's.
VALIDATION_KEY = {"nuble": "biobio"}

SUMMARY_RES = 6
TOP = 90  # percentile: the country's top decile


def fuel_dates(chile) -> str | None:
    """The fuel dates for the whole country, with any region read apart.

    Magallanes is built from a wider window (Punta Arenas had no clear scene
    in February–March), and one span over the whole country would stretch
    to its dates and hide that every other region was read in the default.
    """
    lo, hi = (d.replace("-", "") for d in DEFAULT_WINDOW)
    inside = lambda scene: lo <= scene.split("_")[2][4:] <= hi
    scenes = chile["fuel_scene"].where(chile["fuel_scene"].map(lambda v: isinstance(v, str)))
    apart = [(code, name) for code, _, name, _ in REGIONS
             if not scenes[chile["reg"] == code].dropna().map(inside).all()]
    main = _fuel_source(scenes[~chile["reg"].isin([c for c, _ in apart])])
    notes = [f"{name}: " + _fuel_source(scenes[chile["reg"] == code]).removeprefix("Sentinel-2, ")
             for code, name in apart]
    return "; ".join(n for n in [main, *notes] if n) or None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("-o", "--out", required=True, help="carpeta de salida")
    p.add_argument("--partial", action="store_true",
                   help="exportar aunque falten regiones (solo para probar: "
                        "el ranking nacional sin ellas no es el de Chile)")
    a = p.parse_args()

    builds, missing = {}, []
    for build in dict.fromkeys(r[3] for r in REGIONS):
        path = PROCESSED / f"wui_{build}.parquet"
        if not path.exists():
            missing.append(build)
            continue
        s = pd.read_parquet(path)
        refuse_senapred(s, path)
        builds[build] = s
    if missing and not a.partial:
        sys.exit("faltan builds: " + ", ".join(missing) +
                 "\n  python scripts/build_wui.py --region <id> "
                 "-o ../data/processed/wui_<id>.parquet")
    if missing:
        print(f"PARCIAL, sin: {', '.join(missing)}", file=sys.stderr)

    chile = pd.concat(builds.values(), ignore_index=True)
    dup = chile["h3"].duplicated().sum()
    if dup:
        sys.exit(f"{dup} celdas en más de un build: las regiones se solapan")
    chile["reg"] = chile["cut"].fillna(0).astype("int64") // 1000

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    events = json.loads(VALIDATION.read_text()).values() if VALIDATION.exists() else []
    tested = {v.get("region") for v in events}

    lines = []
    for code, rid, name, build in REGIONS:
        if build not in builds:
            lines.append({"id": rid, "name": name, "missing": True})
            continue
        s = chile[chile["reg"] == code]
        doc = export(s, f"Región de {name}" if code != 13 else "Región Metropolitana",
                     VALIDATION_KEY.get(rid, rid), ref=chile)
        doc["meta"]["scope"] = "chile"
        # Where the page opens: the extent of the region's homes, without
        # the outlying 2% on each side — Valparaíso's would otherwise
        # reach Rapa Nui and open on the Pacific.
        lat, lon = np.array([h3.cell_to_latlng(c) for c in s.loc[s["inhabited"], "h3"]]).T
        q = lambda v, f: round(float(np.quantile(v, f)), 3)
        doc["meta"]["view"] = {"bounds": [[q(lon, .02), q(lat, .02)],
                                          [q(lon, .98), q(lat, .98)]]}
        write(doc, out / f"{rid}.json")
        m = doc["meta"]
        top = [r for r in doc["rows"] if r[1] is not None and r[1] >= TOP]
        lines.append({
            "id": rid, "name": name,
            "tested": VALIDATION_KEY.get(rid, rid) in tested,
            "cells": m["cells"], "unobserved": m["unobserved"],
            "viv": sum(r[3] for r in doc["rows"]),
            "per": sum(r[4] for r in doc["rows"]),
            "viv_hz": sum(r[3] for r in top),
            "per_hz": sum(r[4] for r in top),
            "prio": m["priority"],
        })

    # The summary: the national ranking itself, then summed per r6 cell.
    doc = export(chile, "Chile", "chile", ref=chile)
    region_of = dict(zip(chile["h3"], chile["reg"]))
    idx = {r[0]: i for i, r in enumerate(REGIONS)}
    agg: dict[str, list] = {}
    for h, hz, cs, viv, per, *_, prio in doc["rows"]:
        key = h3.cell_to_parent(h, SUMMARY_RES) if h3.get_resolution(h) > SUMMARY_RES else h
        acc = agg.setdefault(key, [key, 0, 0, 0, 0, 0, 0, 0, {}])
        acc[1] += viv
        acc[2] += per
        if hz is None:
            acc[3] += viv                   # homes with no fuel observation
        elif hz >= TOP:
            acc[4] += viv
            acc[5] += per
        if cs >= TOP:
            acc[6] += viv
        if prio:
            acc[7] += viv
        reg = idx[region_of[h]]
        acc[8][reg] = acc[8].get(reg, 0) + viv
    # A cell on a border goes to the region with most of its homes.
    rows = [[*acc[:8], max(acc[8], key=acc[8].get)] for acc in agg.values()]

    meta = doc["meta"]
    summary = {
        "meta": {
            "generated": meta["generated"],
            "scope": "chile",
            "partial": missing,
            "res": SUMMARY_RES,
            "top": TOP,
            "cells": meta["cells"],
            "ranked": meta["ranked"],
            "unobserved": meta["unobserved"],
            "priority": meta["priority"],
            "validation": meta["validation"],
            "sources": {
                **SOURCES,
                **({"combustible": fuel_dates(chile)}
                   if "fuel_scene" in chile.columns and fuel_dates(chile) else {}),
                "egreso": meta["sources"]["egreso"],
            },
            "regions": lines,
        },
        "cols": ["h", "viv", "per", "viv_nd", "viv_hz", "per_hz", "viv_cs",
                 "viv_prio", "region"],
        "rows": rows,
    }
    path = out / "resumen.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    tmp.replace(path)

    print(f"\n{path}  ({path.stat().st_size / 1024:.0f} KB, {len(rows):,} celdas r{SUMMARY_RES})",
          file=sys.stderr)
    print(f"{'región':<20}{'viv':>11}{'viv top10':>11}{'pers top10':>11}{'prio':>6}",
          file=sys.stderr)
    for l in lines:
        if l.get("missing"):
            print(f"{l['name']:<20}{'sin build':>11}", file=sys.stderr)
            continue
        print(f"{l['name']:<20}{l['viv']:>11,}{l['viv_hz']:>11,}{l['per_hz']:>11,}"
              f"{l['prio']['cells']:>6}{'  probado' if l['tested'] else ''}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
