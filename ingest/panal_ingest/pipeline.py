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


# Coarser levels served as the viewport zooms out. Aggregating up the H3
# hierarchy is exact; refining down is not, and must never be done to sensor
# data — a 2 km pixel rendered as 400 m cells invents precision it does not
# have. Coarsen out, never refine in.
ROLLUP_LEVELS = (6, 5)


def rollup(cells: pd.DataFrame, to_res: int) -> pd.DataFrame:
    """Aggregate scored H3 cells to a coarser resolution.

    Exact: every child cell belongs to exactly one parent, so summing FRP and
    detection counts loses nothing but detail.
    """
    import h3

    if len(cells) == 0:
        return cells

    src_res = h3.get_resolution(cells["h3"].iloc[0])
    if to_res >= src_res:
        raise ValueError(
            f"rollup only coarsens: asked for r{to_res} from r{src_res}. "
            "Refining sensor data would invent precision."
        )

    out = cells.copy()
    out["h3"] = [h3.cell_to_parent(c, to_res) for c in out["h3"]]

    order = pd.Categorical(
        out["best_confidence"], categories=CONFIDENCE_ORDER_PD, ordered=True
    )
    out["_rank"] = order.codes

    agg = out.groupby(["h3", "scan_start"], as_index=False).agg(
        detections=("detections", "sum"),
        frp_mw=("frp_mw", "sum"),
        frp_max_mw=("frp_max_mw", "max"),
        area_m2=("area_m2", "sum"),
        temp_max_k=("temp_max_k", "max"),
        _rank=("_rank", "max"),
        any_temporally_filtered=("any_temporally_filtered", "any"),
    )
    agg["best_confidence"] = [
        CONFIDENCE_ORDER_PD[i] if i >= 0 else None for i in agg["_rank"]
    ]
    agg["h3_res"] = to_res
    return agg.drop(columns=["_rank"])


CONFIDENCE_ORDER_PD = goes.CONFIDENCE_ORDER


def merge_recent(scans, now: dt.datetime) -> dict:
    """The last hour of GOES as one layer, each cell from its newest scan.

    `scans` is `[(scan_end, {level: [cell, ...]}), ...]` in any order, each
    cell a dict with at least `h`. Every merged cell carries `age` (minutes
    since the scan that last saw it ended), `k` (how many of the scans saw
    it) and `l` (1 if the newest scan saw it, else 0).

    A single scan was the whole layer before, so a fire hidden by its own
    smoke or a passing cloud for ten minutes vanished from the map — the
    same empty hexagon as no fire at all. Within the hour it stays, and `l`
    says the newest look did not confirm it.
    """
    ordered = sorted(scans, key=lambda s: s[0])
    newest = ordered[-1][0] if ordered else None
    levels: dict[str, list] = {}
    for lvl in {k for _, cells in ordered for k in cells}:
        merged: dict[str, dict] = {}
        for end, cells in ordered:                  # oldest first; newest wins
            age = int((now - end).total_seconds() // 60)
            for c in cells.get(lvl, []):
                seen = merged.get(c["h"], {}).get("k", 0)
                merged[c["h"]] = {**c, "age": age, "k": seen + 1,
                                  "l": int(end == newest)}
        levels[lvl] = list(merged.values())
    return levels


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
