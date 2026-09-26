#!/usr/bin/env python3
"""Cross the census grid with terrain and score wildland-urban exposure.

    python scripts/build_wui.py --region valparaiso -o ../data/processed/wui_valparaiso.parquet
    python scripts/build_wui.py --all -o ../data/processed/wui_chile.parquet

Terrain is fetched per 1°x1° DEM tile and cached, so the first run over a
region is slow and later ones are not.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ingest"))
sys.path.insert(0, str(ROOT / "engine"))

import pandas as pd  # noqa: E402

from panal_engine import wui  # noqa: E402
from panal_ingest import census, terrain  # noqa: E402

REGIONS = {
    # cut prefixes: 5 = Valparaíso, 13 = Metropolitana, 8 = Biobío
    "valparaiso": (5,),
    "metropolitana": (13,),
    "biobio": (8, 16),
    "centro_sur": (5, 13, 6, 7, 16, 8),
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--census", default=str(ROOT / "data/processed/censo_h3_r9.parquet"))
    p.add_argument("--region", choices=sorted(REGIONS))
    p.add_argument("--all", action="store_true")
    p.add_argument("-o", "--out", required=True)
    a = p.parse_args()

    df = pd.read_parquet(a.census)
    print(f"censo: {len(df):,} celdas", file=sys.stderr)

    if a.region:
        # CUT is region*1000 + comuna for both 4- and 5-digit codes, so
        # integer division recovers the region either way: 5101 -> 5,
        # 13101 -> 13.
        prefixes = set(REGIONS[a.region])
        df = df[(df["cut"].fillna(0).astype("int64") // 1000).isin(prefixes)]
        print(f"  {a.region}: {len(df):,} celdas", file=sys.stderr)
    elif not a.all:
        p.error("elige --region o --all")

    cells = df["h3"].tolist()
    # Count the tiles that actually contain cells, not every tile in the
    # bounding box: Valparaíso reaches Rapa Nui at -109°, so its box spans
    # 39° of empty ocean and tiles_for would report 280 for about nine.
    import math
    import h3 as _h3
    need = {terrain.tile_name(math.floor(la), math.floor(lo))
            for la, lo in (_h3.cell_to_latlng(c) for c in cells)}
    print(f"terreno para {len(cells):,} celdas ({len(need)} tiles DEM)…",
          file=sys.stderr)
    t = terrain.cells_terrain(cells)
    print(f"  con elevación: {len(t):,}", file=sys.stderr)

    df = df.copy()
    df["slope_deg"] = [t.get(c, {}).get("slope_deg") for c in cells]
    df["elev_m"] = [t.get(c, {}).get("elev_m") for c in cells]
    df["relief_m"] = [t.get(c, {}).get("relief_m") for c in cells]
    df["slope_factor"] = [terrain.slope_factor(s) for s in df["slope_deg"]]

    df = census.exposure_terms(df)
    scored = wui.score_frame(df)

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    scored.to_parquet(tmp)
    tmp.replace(out)

    print(f"\n{out}  ({out.stat().st_size / 1024 / 1024:.1f} MB)", file=sys.stderr)
    print(f"  {len(scored):,} celdas puntuadas", file=sys.stderr)
    top = scored.head(12)
    print(f"\n{'wui':>6}{'viv':>8}{'pers':>8}{'pend°':>7}"
          f"{'precar':>8}{'vulner':>8}{'s/agua':>8}  comuna", file=sys.stderr)
    for r in top.itertuples():
        print(f"{r.wui:>6.3f}{r.n_vp:>8.0f}{r.n_per:>8.0f}"
              f"{(r.slope_deg or 0):>7.1f}{r.frac_precario:>8.2f}"
              f"{r.frac_vulnerable:>8.2f}{r.frac_sin_red_agua:>8.2f}"
              f"  {r.cut}", file=sys.stderr)


if __name__ == "__main__":
    main()
