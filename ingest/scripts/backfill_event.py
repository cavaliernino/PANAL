#!/usr/bin/env python3
"""Replay GOES-East over a past fire, at its native 10-minute cadence.

Validates the ingest against events whose outcome we already know, and
produces the growth curve that makes the case for the tempo layer.

    # The Viña del Mar / Quilpué fire, 2 February 2024
    python scripts/backfill_event.py --preset vina2024

    # Anything else
    python scripts/backfill_event.py \
        --date 2023-02-03 --from-hour 14 --to-hour 22 \
        --bbox -37.2 -36.4 -72.8 -71.8 --label "Ñuble 2023"

Hours are UTC. Chile is UTC-3 in summer, UTC-4 in winter.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from panal_ingest import goes, pipeline  # noqa: E402

PRESETS = {
    "vina2024": dict(
        date="2024-02-02", from_hour=14, to_hour=23,
        bbox=(-33.20, -32.90, -71.65, -71.25), utc_offset=-3,
        label="Viña del Mar / Quilpué, 2 Feb 2024",
    ),
}


def run(date, from_hour, to_hour, bbox, utc_offset, label):
    lat_min, lat_max, lon_min, lon_max = bbox
    day = dt.datetime.combine(date, dt.time(), tzinfo=dt.timezone.utc)

    scans = []
    for h in range(from_hour, to_hour + 1):
        scans += goes.list_scans(day.replace(hour=h))
    scans.sort(key=lambda s: s.start)

    print(f"\n{label}")
    print(f"ventana: lat {lat_min}/{lat_max}, lon {lon_min}/{lon_max}")
    print(f"satélite: {goes.bucket_for(date)}  ·  {len(scans)} barridos\n")
    print(f"{'UTC':<6}{'local':<7}{'px':>4}{'FRP MW':>9}  perfil")
    print("-" * 62)

    first = None
    peak = (0.0, None)
    for scan in scans:
        df = pipeline.ingest_scan(scan)
        local = scan.start + dt.timedelta(hours=utc_offset)
        if len(df):
            df = df[
                df.lat.between(lat_min, lat_max)
                & df.lon.between(lon_min, lon_max)
            ]
        n = len(df)
        frp = float(df.frp_mw.sum()) if n else 0.0

        if n and first is None:
            first = (scan, n, frp)
        if frp > peak[0]:
            peak = (frp, scan)

        if n or first:
            bar = "▏" * max(1, int(frp / 400)) if frp else ""
            print(f"{scan.start:%H:%M} {local:%H:%M} {n:>4}{frp:>9.0f}  {bar}")

    if not first:
        print("\nsin detecciones en la ventana")
        return

    scan, n, frp = first
    local = scan.start + dt.timedelta(hours=utc_offset)
    lag = (scan.end - scan.start).total_seconds() / 60
    print(f"\nPRIMERA DETECCIÓN  {scan.start:%H:%M} UTC = {local:%H:%M} local")
    print(f"  {n} píxel(es), {frp:.0f} MW")
    print(f"  barrido cerró {scan.end:%H:%M:%S} UTC ({lag:.0f} min de barrido);")
    print("  el archivo aparece en el bucket público ~1 min después.")
    if peak[1]:
        pl = peak[1].start + dt.timedelta(hours=utc_offset)
        delta = (peak[1].start - scan.start).total_seconds() / 3600
        print(f"\nPICO  {pl:%H:%M} local, {peak[0]:,.0f} MW "
              f"({delta:.1f} h después de la primera detección)")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--preset", choices=sorted(PRESETS))
    p.add_argument("--date", type=dt.date.fromisoformat)
    p.add_argument("--from-hour", type=int, default=12)
    p.add_argument("--to-hour", type=int, default=23)
    p.add_argument("--bbox", nargs=4, type=float,
                   metavar=("LAT_MIN", "LAT_MAX", "LON_MIN", "LON_MAX"))
    p.add_argument("--utc-offset", type=int, default=-3)
    p.add_argument("--label", default="evento")
    a = p.parse_args()

    if a.preset:
        cfg = dict(PRESETS[a.preset])
        cfg["date"] = dt.date.fromisoformat(cfg["date"])
        run(**cfg)
    elif a.date and a.bbox:
        run(a.date, a.from_hour, a.to_hour, tuple(a.bbox), a.utc_offset, a.label)
    else:
        p.error("usa --preset, o --date junto con --bbox")


if __name__ == "__main__":
    main()
