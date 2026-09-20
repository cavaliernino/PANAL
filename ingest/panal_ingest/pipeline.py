"""GOES → Chile → H3: the Phase 1 ingest pipeline.

    python -m panal_ingest.pipeline            # latest scan
    python -m panal_ingest.pipeline --hours 6  # backfill the last 6 hours

Writes one parquet per run to data/processed/, plus a rolling H3 aggregate.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import tempfile
from pathlib import Path

import pandas as pd

from . import chile, goes

# Default H3 resolution. Res 7 cells average ~5.2 km², comfortably larger than
# a 2 km GOES pixel, so a detection never implies more precision than the
# sensor has.
DEFAULT_RES = 7

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"


def ingest_scan(scan: goes.Scan, res: int = DEFAULT_RES) -> pd.DataFrame:
    """Fetch one scan and return its Chilean detections, H3-indexed."""
    import h3

    with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as tmp:
        path = goes.download(scan.url, tmp.name)

    try:
        df = goes.extract_detections(path)
    finally:
        Path(path).unlink(missing_ok=True)

    df = chile.clip(df)
    if len(df) == 0:
        return df

    df["h3"] = [
        h3.latlng_to_cell(lat, lon, res)
        for lat, lon in zip(df["lat"], df["lon"])
    ]
    df["h3_res"] = res
    df["source"] = "GOES-19/ABI-L2-FDCF"
    df["scan_key"] = scan.key
    return df


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse detections to one row per H3 cell per scan."""
    if len(df) == 0:
        return df

    best = pd.Categorical(
        df["confidence"], categories=goes.CONFIDENCE_ORDER, ordered=True
    )
    df = df.assign(_rank=best.codes)

    out = (
        df.groupby(["h3", "scan_start"], as_index=False)
        .agg(
            detections=("mask_code", "size"),
            frp_mw=("frp_mw", "sum"),
            frp_max_mw=("frp_mw", "max"),
            area_m2=("area_m2", "sum"),
            temp_max_k=("temp_k", "max"),
            best_rank=("_rank", "max"),
            any_temporally_filtered=("temporally_filtered", "any"),
        )
    )
    out["best_confidence"] = [
        goes.CONFIDENCE_ORDER[i] if i >= 0 else None for i in out["best_rank"]
    ]
    return out.drop(columns=["best_rank"])


def run(hours: int = 0, res: int = DEFAULT_RES) -> pd.DataFrame:
    now = dt.datetime.now(dt.timezone.utc)

    if hours <= 0:
        scans = [goes.latest_scan(now)]
    else:
        scans = []
        for back in range(hours + 1):
            scans.extend(goes.list_scans(now - dt.timedelta(hours=back)))
        cutoff = now - dt.timedelta(hours=hours)
        scans = sorted({s.key: s for s in scans}.values(), key=lambda s: s.start)
        scans = [s for s in scans if s.start >= cutoff]

    frames = []
    for i, scan in enumerate(scans, 1):
        df = ingest_scan(scan, res)
        frames.append(df)
        print(
            f"  [{i}/{len(scans)}] {scan.start:%Y-%m-%d %H:%M} UTC  "
            f"→ {len(df):3d} detecciones en Chile",
            file=sys.stderr,
        )

    detections = (
        pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    if len(detections):
        detections.to_parquet(OUT_DIR / f"goes_detections_{stamp}.parquet")
        agg = aggregate(detections)
        agg.to_parquet(OUT_DIR / f"goes_h3_r{res}_{stamp}.parquet")
        print(
            f"\n{len(detections)} detecciones → {len(agg)} celdas H3 r{res}",
            file=sys.stderr,
        )
    else:
        print("\nsin detecciones en territorio chileno", file=sys.stderr)

    return detections


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hours", type=int, default=0,
                   help="backfill this many hours (0 = latest scan only)")
    p.add_argument("--res", type=int, default=DEFAULT_RES, help="H3 resolution")
    args = p.parse_args()
    run(hours=args.hours, res=args.res)


if __name__ == "__main__":
    main()
