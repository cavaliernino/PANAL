#!/usr/bin/env python3
"""Build the persistent thermal anomaly mask from a year of VIIRS archive.

    export FIRMS_MAP_KEY=...
    python scripts/build_anomaly_mask.py --months 12

FIRMS serves at most 5 days per request, so a year is ~73 calls. Each chunk
is cached, making re-runs and threshold experiments nearly free.

Rebuild once a season. Industrial sites open and close, and a mask that is
never revisited quietly becomes wrong in both directions.
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

# Wide enough to cover Chile end to end; detections are clipped to real
# territory afterwards, because a box here is mostly Argentina and Bolivia.
BBOX = (-76.0, -56.5, -66.0, -17.0)
CHUNK_DAYS = 5                       # FIRMS hard limit
PRODUCTS = ("VIIRS_NOAA20_SP", "VIIRS_SNPP_SP")

CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "firms"


def fetch_chunk(key, start: dt.date, product: str):
    """One 5-day window, cached to disk."""
    import pandas as pd

    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{product}_{start:%Y%m%d}_{CHUNK_DAYS}d.json"

    if path.exists():
        rows = json.loads(path.read_text())
        if not rows:
            return pd.DataFrame(columns=["lat", "lon", "confidence", "frp_mw",
                                         "acq", "sensor", "source"])
        df = pd.DataFrame(rows)
        df["acq"] = pd.to_datetime(df["acq"], utc=True)
        return df

    df = viirs.fetch_archive(key, BBOX, start, days=CHUNK_DAYS, product=product)
    keep = df[["lat", "lon", "confidence", "frp_mw", "acq", "sensor", "source"]] \
        if len(df) else df
    rows = []
    if len(keep):
        rows = json.loads(keep.assign(acq=keep["acq"].astype(str)).to_json(
            orient="records"))
    path.write_text(json.dumps(rows, separators=(",", ":")))
    return df


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--months", type=int, default=12,
                   help="how far back to look (default 12)")
    p.add_argument("--end", type=dt.date.fromisoformat,
                   help="last day to include (default: 90 days ago, so the "
                        "standard-processing archive is complete)")
    a = p.parse_args()

    key = os.environ.get("FIRMS_MAP_KEY", "").strip()
    if not key:
        sys.exit("FIRMS_MAP_KEY no definido. Registro gratuito e inmediato en "
                 "https://firms.modaps.eosdis.nasa.gov/api/map_key/")

    # Standard-processing products lag a couple of months; ending the window
    # short of today avoids a ragged tail of missing days.
    end = a.end or (dt.date.today() - dt.timedelta(days=90))
    start = end - dt.timedelta(days=int(a.months * 30.44))

    import pandas as pd

    windows = []
    cur = start
    while cur <= end:
        windows.append(cur)
        cur += dt.timedelta(days=CHUNK_DAYS)

    total = len(windows) * len(PRODUCTS)
    print(f"{start} → {end}  ·  {len(windows)} ventanas × {len(PRODUCTS)} "
          f"productos = {total} llamadas", file=sys.stderr)

    frames, failed = [], 0
    done = 0
    for product in PRODUCTS:
        for w in windows:
            done += 1
            try:
                df = fetch_chunk(key, w, product)
                if len(df):
                    frames.append(df)
            except Exception as exc:                    # noqa: BLE001
                failed += 1
                print(f"  ! {product} {w}: {str(exc)[:70]}", file=sys.stderr)
            if done % 25 == 0 or done == total:
                n = sum(len(f) for f in frames)
                print(f"  {done}/{total}  ·  {n:,} detecciones",
                      file=sys.stderr)

    if not frames:
        sys.exit("sin datos: no se pudo construir la máscara")

    raw = pd.concat(frames, ignore_index=True)
    print(f"\n{len(raw):,} detecciones en el bbox", file=sys.stderr)

    cl = viirs.to_h3(raw)
    print(f"{len(cl):,} en territorio chileno  ·  "
          f"{cl.h3.nunique():,} celdas r9", file=sys.stderr)

    summary = anomaly.summarise(cl)
    payload = anomaly.save(summary, window=f"{start}..{end}")

    flagged = summary[summary["industrial"]]
    print(f"\nmáscara: {len(flagged)} celdas marcadas de "
          f"{len(summary):,} examinadas", file=sys.stderr)
    if failed:
        print(f"  ({failed} ventanas fallaron)", file=sys.stderr)

    print(f"\n{'celda':<18}{'det':>6}{'días':>6}{'meses':>7}{'fuera':>7}"
          f"{'FRP med':>9}", file=sys.stderr)
    for r in flagged.head(15).itertuples():
        print(f"{r.h3:<18}{r.detections:>6}{r.days:>6}{r.months:>7}"
              f"{r.offseason_days:>7}{r.frp_median:>9.1f}", file=sys.stderr)
    print(f"\n→ {anomaly.MASK_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()
