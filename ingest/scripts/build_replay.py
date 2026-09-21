#!/usr/bin/env python3
"""Build a replay dataset for the web map.

Walks GOES-East at its native 10-minute cadence over a past fire and writes
a compact JSON the PWA can load without a backend.

    python scripts/build_replay.py --preset vina2024 -o ../web/data/vina2024.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panal_ingest import goes, pipeline, power  # noqa: E402

PRESETS = {
    "vina2024": dict(
        start="2024-02-02T15:00", end="2024-02-03T03:00",
        bbox=(-33.30, -32.85, -71.80, -71.10),
        utc_offset=-3, res=7,
        title="Viña del Mar / Quilpué",
        subtitle="2 de febrero de 2024",
        center=(-71.45, -33.05), zoom=10.5,
    ),
}

# Chile's 30-30-30 pre-alert factor. The published definition uses 30 km/h;
# pass wind_unit="knots" if a service states it that way instead.
FACTOR = power.Factor30()

# Served as the viewport zooms out. Coarsening the H3 hierarchy is exact.
LEVELS = (7, 6, 5)


def roll(cells, to_res, geom):
    """Coarsen replay cells one level, summing exactly and keeping the best
    confidence. Parent geometry is materialised on demand."""
    import h3

    order = power and goes.CONFIDENCE_ORDER  # shared vocabulary
    bucket = {}
    for c in cells:
        parent = h3.cell_to_parent(c["h"], to_res)
        b = bucket.setdefault(parent, {"h": parent, "n": 0, "f": 0.0, "c": None})
        b["n"] += c["n"]
        b["f"] += c["f"]
        if b["c"] is None or order.index(c["c"]) > order.index(b["c"]):
            b["c"] = c["c"]
        if parent not in geom:
            geom[parent] = [[round(lng, 5), round(lat, 5)]
                            for lat, lng in h3.cell_to_boundary(parent)]
    for b in bucket.values():
        b["f"] = round(b["f"], 1)
    return list(bucket.values())


CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "goes"


def cached_scan(scan, res, bbox):
    """Per-scan Chilean detections, cached to disk.

    A 72-scan backfill is 130 MB of downloads. Caching the extracted rows —
    a few KB each — means a failure at scan 60, or a tweak to the replay
    window, costs seconds instead of ten minutes.
    """
    lat_min, lat_max, lon_min, lon_max = bbox
    CACHE.mkdir(parents=True, exist_ok=True)
    key = CACHE / f"{scan.key.replace('/', '_')}.r{res}.json"

    if key.exists():
        return json.loads(key.read_text())

    df = pipeline.ingest_scan(scan, res=res)
    if len(df):
        df = df[df.lat.between(lat_min, lat_max)
                & df.lon.between(lon_min, lon_max)]

    rows = []
    if len(df):
        import h3
        for r in pipeline.aggregate(df).itertuples():
            rows.append({
                "h": r.h3, "n": int(r.detections),
                "f": round(float(r.frp_mw), 1), "c": r.best_confidence,
                "g": [[round(lng, 5), round(lat, 5)]
                      for lat, lng in h3.cell_to_boundary(r.h3)],
            })
    out = {"px": int(len(df)), "cells": rows}
    key.write_text(json.dumps(out, separators=(",", ":")))
    return out


def build(start, end, bbox, utc_offset, res, **meta):
    lat_min, lat_max, lon_min, lon_max = bbox

    scans, cursor = [], start.replace(minute=0, second=0, microsecond=0)
    while cursor <= end:
        scans += goes.list_scans(cursor)
        cursor += dt.timedelta(hours=1)
    scans = [s for s in sorted({s.key: s for s in scans}.values(),
                               key=lambda s: s.start)
             if start <= s.start <= end]

    print(f"{len(scans)} barridos", file=sys.stderr)

    # Weather for the event centroid. One POWER call covers the whole replay.
    wx_lat = (lat_min + lat_max) / 2
    wx_lon = (lon_min + lon_max) / 2
    try:
        hourly = power.fetch_hourly(
            wx_lat, wx_lon, start.date(), (end + dt.timedelta(days=1)).date())
        print(f"POWER: {len(hourly)} horas en ({wx_lat:.2f}, {wx_lon:.2f})",
              file=sys.stderr)
    except Exception as exc:                            # noqa: BLE001
        print(f"  ! POWER no disponible: {exc}", file=sys.stderr)
        hourly = {}

    frames, cell_geom, skipped = [], {}, []

    for i, scan in enumerate(scans, 1):
        try:
            got = cached_scan(scan, res, bbox)
        except Exception as exc:                       # noqa: BLE001
            # One unreachable scan must not lose the other seventy-one.
            skipped.append(scan.start)
            print(f"  ! {scan.start:%H:%M} UTC omitido: {exc}", file=sys.stderr)
            continue

        cells = []
        for c in got["cells"]:
            cells.append({k: c[k] for k in ("h", "n", "f", "c")})
            cell_geom.setdefault(c["h"], c["g"])

        by_res = {str(res): cells}
        for lvl in LEVELS:
            if lvl < res:
                by_res[str(lvl)] = roll(cells, lvl, cell_geom)

        wx = power.at(hourly, scan.start) if hourly else {}
        frames.append({
            "t": scan.start.isoformat().replace("+00:00", "Z"),
            "local": (scan.start + dt.timedelta(hours=utc_offset)).strftime("%H:%M"),
            "cells": cells,
            "r": by_res,
            "frp": round(sum(c["f"] for c in cells), 1),
            "px": got["px"],
            "wx": wx,
            "f30": FACTOR.evaluate(wx.get("t2m"), wx.get("rh2m"), wx.get("ws_ms"))
                   if wx else {},
        })
        if i % 12 == 0 or i == len(scans):
            print(f"  {i}/{len(scans)}  {frames[-1]['local']} local  "
                  f"{frames[-1]['px']} px  {frames[-1]['frp']:,.0f} MW",
                  file=sys.stderr)

    if skipped:
        print(f"\n  {len(skipped)} barrido(s) omitido(s) por fallo de red",
              file=sys.stderr)

    first = next((f for f in frames if f["px"]), None)
    peak = max(frames, key=lambda f: f["frp"])

    return {
        "meta": {
            **{k: v for k, v in meta.items()},
            "res": res,
            "levels": sorted({int(k) for f in frames for k in f["r"]}, reverse=True)
                      if frames else [res],
            "utc_offset": utc_offset,
            "bbox": list(bbox),
            "satellite": goes.bucket_for(start),
            "product": goes.PRODUCT,
            "cadence_min": 10,
            "pixel_km": 2,
            "first_detection": first and first["local"],
            "peak_local": peak["local"],
            "peak_frp": peak["frp"],
            "skipped_scans": len(skipped),
            "weather_point": [round(wx_lat, 3), round(wx_lon, 3)],
            "weather_source": "NASA POWER (MERRA-2, hourly, ~50 km grid)",
            "factor30": {
                "temp_c": FACTOR.temp_c, "rh_pct": FACTOR.rh_pct,
                "wind": FACTOR.wind, "wind_unit": FACTOR.wind_unit,
            },
            "factor30_frames": sum(1 for f in frames if f.get("f30", {}).get("all")),
            "generated": dt.datetime.now(dt.timezone.utc)
                           .isoformat(timespec="seconds").replace("+00:00", "Z"),
        },
        "geometry": cell_geom,
        "frames": frames,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--preset", choices=sorted(PRESETS), required=True)
    p.add_argument("-o", "--out", required=True)
    a = p.parse_args()

    cfg = dict(PRESETS[a.preset])
    cfg["start"] = dt.datetime.fromisoformat(cfg["start"]).replace(tzinfo=dt.timezone.utc)
    cfg["end"] = dt.datetime.fromisoformat(cfg["end"]).replace(tzinfo=dt.timezone.utc)

    data = build(**cfg)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, separators=(",", ":")))

    m = data["meta"]
    print(f"\n{out}  ({out.stat().st_size/1024:.0f} KB)", file=sys.stderr)
    per_lvl = {}
    for f in data["frames"]:
        for r, cs in f["r"].items():
            per_lvl.setdefault(r, set()).update(c["h"] for c in cs)
    lvls = "  ".join(f"r{r}:{len(v)}" for r, v in sorted(per_lvl.items(), reverse=True))
    print(f"  {len(data['frames'])} cuadros · celdas únicas por nivel  {lvls}",
          file=sys.stderr)
    print(f"  primera detección {m['first_detection']} · pico {m['peak_local']} "
          f"({m['peak_frp']:,.0f} MW)", file=sys.stderr)
    fu = m["factor30"]
    print(f"  factor 30-30-30 ({fu['wind']:.0f} {fu['wind_unit']}): "
          f"{m['factor30_frames']} de {len(data['frames'])} cuadros con los tres",
          file=sys.stderr)


if __name__ == "__main__":
    main()
