#!/usr/bin/env python3
"""Aggregate Censo 2024 onto the H3 grid.

    python scripts/build_census_h3.py --res 9 -o ../data/processed/censo_h3_r9.parquet

Reads both cartography files — Manzanas for the urban population and
Entidades for the 2.04M rural people who are not in it — and writes one row
per H3 cell with the curated exposure variables.

Run once. The census does not change between fire seasons.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panal_ingest import census  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--res", type=int, default=9)
    p.add_argument("-o", "--out", required=True)
    a = p.parse_args()

    df = census.to_h3(res=a.res)
    df = census.exposure_terms(df)

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    df.to_parquet(tmp)
    tmp.replace(out)

    print(f"\n{out}  ({out.stat().st_size/1024/1024:.1f} MB)", file=sys.stderr)
    print(f"  {len(df):,} celdas H3 r{a.res}", file=sys.stderr)
    print(f"  población {df.n_per.sum():,.0f} · viviendas {df.n_vp.sum():,.0f}",
          file=sys.stderr)
    print(f"  comunas distintas: {df.cut.nunique()}", file=sys.stderr)


if __name__ == "__main__":
    main()
