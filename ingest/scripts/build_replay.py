#!/usr/bin/env python3
"""Build a replay dataset for the web map.

Walks GOES-East at its native 10-minute cadence over a past fire and writes
a compact JSON the PWA can load without a backend.

    python scripts/build_replay.py --preset vina2024 -o ../web/data/vina2024.json

Every build also upserts its entry in replays.json beside the output, which
is the list the page offers. Windows are UTC.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from collections import namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panal_ingest import goes, pipeline, power, viirs  # noqa: E402

PRESETS = {
    "vina2024": dict(
        start="2024-02-02T15:00", end="2024-02-03T03:00",
        bbox=(-33.30, -32.85, -71.80, -71.10),
        utc_offset=-3, res=7,
        title="Viña del Mar / Quilpué",
        subtitle="2 de febrero de 2024",
        center=(-71.45, -33.05), zoom=10.5,
        viirs_products=("VIIRS_NOAA20_SP", "VIIRS_SNPP_SP"),
    ),
    # Before GOES-16 (launched November 2016) there is no ABI fire product
    # to replay: GOES-13 flew, but not at 2 km every ten minutes. The clock
    # still ticks every ten minutes, so the hours before the first polar
    # pass are visible as what they were.
    "valparaiso2014": dict(
        start="2014-04-12T18:00", end="2014-04-14T12:00",
        bbox=(-33.12, -32.98, -71.75, -71.50),
        utc_offset=-3, res=7, goes=False,
        title="Gran Incendio de Valparaíso",
        subtitle="12 de abril de 2014",
        center=(-71.61, -33.05), zoom=12,
        viirs_products=("VIIRS_SNPP_SP", "MODIS_SP"),
    ),
    # The windows and boxes below are the validation set's
    # (scripts/event_footprint.py), so the replay shows the same fire the
    # exposure index was tested against.
    "rocuant2019": dict(
        start="2019-12-24T15:00", end="2019-12-25T15:00",
        bbox=(-33.15, -32.95, -71.75, -71.45),
        utc_offset=-3, res=7,
        title="Valparaíso · Rocuant y San Roque",
        subtitle="24 de diciembre de 2019",
        center=(-71.60, -33.05), zoom=11,
        viirs_products=("VIIRS_NOAA20_SP", "VIIRS_SNPP_SP"),
    ),
    # Starts eleven hours before the validation window: the Lago Peñuelas
    # fire was reported on the night of the 14th.
    "quilpue2021": dict(
        start="2021-01-14T23:00", end="2021-01-17T12:00",
        bbox=(-33.20, -33.02, -71.60, -71.30),
        utc_offset=-3, res=7,
        title="Quilpué · Lago Peñuelas y Las Palmas",
        subtitle="14 al 17 de enero de 2021",
        center=(-71.45, -33.11), zoom=11,
        viirs_products=("VIIRS_NOAA20_SP", "VIIRS_SNPP_SP"),
    ),
    "vina2022": dict(
        start="2022-12-22T15:00", end="2022-12-23T15:00",
        bbox=(-33.10, -32.95, -71.62, -71.42),
        utc_offset=-3, res=7,
        title="Viña del Mar · Nueva Esperanza y Forestal",
        subtitle="22 de diciembre de 2022",
        center=(-71.52, -33.03), zoom=11.5,
        viirs_products=("VIIRS_NOAA20_SP", "VIIRS_SNPP_SP"),
    ),
    "biobio2023": dict(
        start="2023-02-02T12:00", end="2023-02-07T12:00",
        bbox=(-37.80, -36.20, -73.30, -71.90),
        utc_offset=-3, res=7,
        title="Biobío y Ñuble · Santa Ana",
        subtitle="2 al 7 de febrero de 2023",
        center=(-72.60, -37.00), zoom=8,
        viirs_products=("VIIRS_NOAA20_SP", "VIIRS_SNPP_SP"),
    ),
    "sancarlos2025": dict(
        start="2025-12-29T14:00", end="2025-12-31T23:00",
        bbox=(-33.46, -33.34, -70.58, -70.38),
        utc_offset=-3, res=7,
        title="Las Condes · San Carlos de Apoquindo",
        subtitle="29 de diciembre de 2025",
        center=(-70.48, -33.41), zoom=12,
        viirs_products=("VIIRS_NOAA20_SP", "VIIRS_SNPP_SP", "VIIRS_NOAA21_NRT"),
    ),
    "biobio2026": dict(
        start="2026-01-13T12:00", end="2026-01-19T15:00",
        bbox=(-37.10, -36.30, -73.20, -72.00),
        utc_offset=-3, res=7,
        title="Ñuble y Biobío · Ránquil y Penco-Lirquén",
        subtitle="13 al 19 de enero de 2026",
        center=(-72.60, -36.70), zoom=8.8,
        viirs_products=("VIIRS_NOAA20_SP", "VIIRS_SNPP_SP", "VIIRS_NOAA21_NRT"),
    ),
}

# FIRMS answers at most five days per request.
FIRMS_MAX_DAYS = 5

SENSOR_LABEL = {"viirs": "VIIRS 375 m", "modis": "MODIS 1 km"}

# A VIIRS fix stays on screen this long before it is too stale to show.
VIIRS_MAX_AGE_MIN = 240
# Detections more than this far apart in time belong to different passes.
PASS_GAP_MIN = 30

# VIIRS detections arrive as a scatter, not a blob: at r9 one pass over Viña
# gave 105 cells in 33 disconnected components. The holes between them are
# tiny — median 201 m, p90 402 m, at most 603 m — which is smaller than the
# 375 m pixel that produced them, so the fragmentation is a sampling artefact
# rather than fire-free ground. Dilating by a single ring collapses those 33
# components into 4.
#
# That dilation is rendered as a separate, clearly labelled *inferred* layer.
# It is never mixed into the detections: one is observed, the other is a
# neighbourhood guess, and a map that blurs the two is lying.
EXTENT_RINGS = 1

# Chile's 30-30-30 pre-alert factor. The published definition uses 30 km/h;
# pass wind_unit="knots" if a service states it that way instead.
FACTOR = power.Factor30()

# Served as the viewport zooms out. Coarsening the H3 hierarchy is exact.
LEVELS = (7, 6, 5)


def roll(cells, to_res):
    """Coarsen replay cells one level, summing exactly and keeping the best
    confidence."""
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
    for b in bucket.values():
        b["f"] = round(b["f"], 1)
    return list(bucket.values())


CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "goes"

# A frame's clock where there was no scan to read (see valparaiso2014).
Tick = namedtuple("Tick", "start")
NO_SCAN = {"px": 0, "cells": []}


def cached_scan(scan, res, bbox):
    """Per-scan Chilean detections, cached to disk.

    A 72-scan backfill is 130 MB of downloads. Caching the extracted rows —
    a few KB each — means a failure at scan 60, or a tweak to the replay
    window, costs seconds instead of ten minutes.
    """
    lat_min, lat_max, lon_min, lon_max = bbox
    CACHE.mkdir(parents=True, exist_ok=True)
    # The rows are clipped to the box before caching, so the box is part of
    # the key: a wider box must not be served a narrower box's rows.
    box = "_".join(f"{v:.2f}" for v in bbox)
    key = CACHE / f"{scan.key.replace('/', '_')}.r{res}.{box}.json"

    if key.exists():
        return json.loads(key.read_text())

    df = pipeline.ingest_scan(scan, res=res)
    if len(df):
        df = df[df.lat.between(lat_min, lat_max)
                & df.lon.between(lon_min, lon_max)]

    rows = []
    if len(df):
        for r in pipeline.aggregate(df).itertuples():
            rows.append({
                "h": r.h3, "n": int(r.detections),
                "f": round(float(r.frp_mw), 1), "c": r.best_confidence,
            })
    out = {"px": int(len(df)), "cells": rows}
    key.write_text(json.dumps(out, separators=(",", ":")))
    return out


def build_viirs(bbox, start, end, products, utc_offset, map_key):
    """VIIRS passes over the window, indexed at r9.

    VIIRS is the precision layer: 375 m against GOES's 2 km, but only three
    or four passes a day instead of a look every ten minutes. So it is not a
    per-frame layer — it is a sequence of discrete fixes, each shown with its
    age until the next one supersedes it.
    """
    import h3
    import pandas as pd

    lat_min, lat_max, lon_min, lon_max = bbox
    frames = []
    for product in products:
        day = start.date()
        while day <= end.date():
            span = min(FIRMS_MAX_DAYS, (end.date() - day).days + 1)
            try:
                df = viirs.fetch_archive(
                    map_key, (lon_min, lat_min, lon_max, lat_max),
                    day, days=span, product=product)
            except Exception as exc:                    # noqa: BLE001
                print(f"  ! {product} {day}: {exc}", file=sys.stderr)
                df = None
            if df is not None and len(df):
                frames.append(df)
            day += dt.timedelta(days=span)
    if not frames:
        return []

    df = pd.concat(frames, ignore_index=True)
    # to_h3 picks one resolution per call, from the first row's sensor, so a
    # mixed frame would put MODIS's 1 km pixels on VIIRS's r9 grid. Index
    # each sensor at its own resolution.
    df = pd.concat([viirs.to_h3(g) for _, g in df.groupby("sensor")],
                   ignore_index=True)                   # clips to Chile
    df = df[df.acq.between(start, end)]
    if len(df) == 0:
        return []

    # Split into passes wherever the acquisition times gap out.
    df = df.sort_values("acq").reset_index(drop=True)
    gap = df.acq.diff() > dt.timedelta(minutes=PASS_GAP_MIN)
    df["pass_id"] = gap.cumsum()

    order = goes.CONFIDENCE_ORDER
    passes = []
    for pid, grp in df.groupby("pass_id"):
        cells = {}
        for row in grp.itertuples():
            c = cells.setdefault(row.h3, {"h": row.h3, "n": 0, "f": 0.0, "c": None})
            c["n"] += 1
            c["f"] += float(row.frp_mw)
            if c["c"] is None or order.index(row.confidence) > order.index(c["c"]):
                c["c"] = row.confidence
        for c in cells.values():
            c["f"] = round(c["f"], 1)
        # Inferred extent: one ring around the detections, minus the
        # detections themselves, so it renders as a halo underneath.
        # VIIRS only: the ring closes gaps smaller than its 375 m pixel, and
        # a ring of MODIS's r7 cells would claim kilometres nobody observed.
        halo = set()
        for cell in cells:
            if h3.get_resolution(cell) == 9:
                halo |= set(h3.grid_disk(cell, EXTENT_RINGS))
        halo -= set(cells)

        t = grp.acq.min()
        passes.append({
            "halo": sorted(halo),
            "t": t.isoformat().replace("+00:00", "Z"),
            "local": (t + dt.timedelta(hours=utc_offset)).strftime("%H:%M"),
            "sat": ", ".join(sorted(grp.satellite.unique())),
            "sensor": " + ".join(SENSOR_LABEL[s] for s in sorted(grp.sensor.unique())),
            "n": int(len(grp)),
            "cells": list(cells.values()),
        })
    return sorted(passes, key=lambda p: p["t"])


def build(start, end, bbox, utc_offset, res, goes_on=True, **meta):
    lat_min, lat_max, lon_min, lon_max = bbox

    if goes_on:
        scans, cursor = [], start.replace(minute=0, second=0, microsecond=0)
        while cursor <= end:
            scans += goes.list_scans(cursor)
            cursor += dt.timedelta(hours=1)
        scans = [s for s in sorted({s.key: s for s in scans}.values(),
                                   key=lambda s: s.start)
                 if start <= s.start <= end]
        print(f"{len(scans)} barridos", file=sys.stderr)
    else:
        # Empty ticks on GOES's cadence: there is no ABI scan to read.
        scans, t = [], start
        while t <= end:
            scans.append(Tick(t))
            t += dt.timedelta(minutes=10)
        print(f"sin GOES: {len(scans)} cuadros vacíos de 10 min", file=sys.stderr)

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

    frames, skipped = [], []

    map_key = os.environ.get("FIRMS_MAP_KEY", "").strip()
    vpasses = []
    if map_key and meta.get("viirs_products"):
        vpasses = build_viirs(bbox, start, end, meta["viirs_products"],
                              utc_offset, map_key)
        print(f"VIIRS: {len(vpasses)} pasadas, "
              f"{sum(len(p['cells']) for p in vpasses)} celdas r9", file=sys.stderr)
    elif not map_key:
        print("VIIRS omitido: define FIRMS_MAP_KEY para la capa de precisión",
              file=sys.stderr)

    for i, scan in enumerate(scans, 1):
        try:
            got = cached_scan(scan, res, bbox) if goes_on else NO_SCAN
        except Exception as exc:                       # noqa: BLE001
            # One unreachable scan must not lose the other seventy-one.
            skipped.append(scan.start)
            print(f"  ! {scan.start:%H:%M} UTC omitido: {exc}", file=sys.stderr)
            continue

        cells = []
        for c in got["cells"]:
            cells.append({k: c[k] for k in ("h", "n", "f", "c")})

        # The base resolution is `cells` itself; the page falls back to it.
        # Repeating it under "r" doubled a week-long replay's frames.
        by_res = {}
        for lvl in LEVELS:
            if lvl < res:
                by_res[str(lvl)] = roll(cells, lvl)

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

    # Which VIIRS pass, if any, each frame should display.
    for f in frames:
        ft = dt.datetime.fromisoformat(f["t"].replace("Z", "+00:00"))
        idx, age = None, None
        for k, pas in enumerate(vpasses):
            pt = dt.datetime.fromisoformat(pas["t"].replace("Z", "+00:00"))
            if pt <= ft:
                mins = (ft - pt).total_seconds() / 60
                if mins <= VIIRS_MAX_AGE_MIN:
                    idx, age = k, round(mins)
        f["v"] = idx
        f["vage"] = age

    first = next((f for f in frames if f["px"]), None)
    peak = max(frames, key=lambda f: f["frp"])

    return {
        "meta": {
            **{k: v for k, v in meta.items()},
            "goes": goes_on,
            "res": res,
            "levels": sorted({res} | {int(k) for f in frames for k in f["r"]},
                             reverse=True),
            "utc_offset": utc_offset,
            "bbox": list(bbox),
            "satellite": goes.bucket_for(start) if goes_on else None,
            "product": goes.PRODUCT if goes_on else None,
            "cadence_min": 10,
            "pixel_km": 2,
            "first_detection": first and first["local"],
            "first_detection_t": first and first["t"],
            "peak_local": peak["local"] if peak["frp"] else None,
            "peak_t": peak["t"] if peak["frp"] else None,
            "peak_frp": peak["frp"],
            "skipped_scans": len(skipped),
            "viirs_res": 9,
            "viirs_max_age_min": VIIRS_MAX_AGE_MIN,
            "viirs_extent_rings": EXTENT_RINGS,
            "viirs_first_local": vpasses[0]["local"] if vpasses else None,
            "viirs_first_t": vpasses[0]["t"] if vpasses else None,
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
        "viirs": vpasses,
        "frames": frames,
    }


def index_entry(out: Path, data: dict) -> None:
    """Upsert this replay in replays.json, oldest fire first."""
    path = out.parent / "replays.json"
    try:
        entries = json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        entries = []
    m = data["meta"]
    entry = {
        "id": m["id"], "file": out.name,
        "title": m["title"], "subtitle": m["subtitle"],
        "start": data["frames"][0]["t"] if data["frames"] else None,
        "goes": m["goes"],
        "kb": round(out.stat().st_size / 1024),
    }
    entries = [e for e in entries if e["id"] != entry["id"]] + [entry]
    entries.sort(key=lambda e: e["start"] or "")
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=1) + "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--preset", choices=sorted(PRESETS), required=True)
    p.add_argument("-o", "--out", required=True)
    a = p.parse_args()

    cfg = dict(PRESETS[a.preset])
    cfg["start"] = dt.datetime.fromisoformat(cfg["start"]).replace(tzinfo=dt.timezone.utc)
    cfg["end"] = dt.datetime.fromisoformat(cfg["end"]).replace(tzinfo=dt.timezone.utc)
    cfg["goes_on"] = cfg.pop("goes", True)

    data = build(id=a.preset, **cfg)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, separators=(",", ":")))
    index_entry(out, data)

    m = data["meta"]
    print(f"\n{out}  ({out.stat().st_size/1024:.0f} KB)", file=sys.stderr)
    per_lvl = {}
    for f in data["frames"]:
        for r, cs in {str(m["res"]): f["cells"], **f["r"]}.items():
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
