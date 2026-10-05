"""Land cover — what kind of fuel a cell holds, from ESA WorldCover.

Sentinel-2 gives fuel *state*: how much biomass and how dry. The hazard
index failed in two fires of four for want of fuel *type* (see
`ingest/scripts/validate_wui.py`): in plantations the dryness term reads a
green canopy as moist, and in dense settlements the fuel is the houses.
CONAF's Catastro is the authoritative type and is not reachable; WorldCover
is the public stand-in being tested, under the rules fixed in
`docs/preregistro-combustible.md` before this module was written.

Source: ESA WorldCover 10 m, 2020 v100, on AWS Open Data. Public, no
credentials, one cloud-optimised GeoTIFF per 3°x3° tile named by its
south-west corner. 2020 predates every validation fire but Rocuant 2019.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

BUCKET = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v100/2020/map"
CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "worldcover"

CLASSES = {
    10: "arboles", 20: "matorral", 30: "pradera", 40: "cultivo",
    50: "construido", 60: "desnudo", 70: "nieve", 80: "agua",
    90: "humedal", 95: "manglar", 100: "musgo",
}

# Read at 1/4 of native: 40 m pixels, about sixty to an r9 cell. Enough to
# estimate a fraction; native would be sixteen times the work for nothing a
# 321 m cell can use.
DIVISOR = 4

# Coarse census cells (r5-r8) hold far more pixels than a fraction needs.
# Sampled down to about this many.
MAX_PIXELS = 3000


def tile_name(lat: float, lon: float) -> str:
    """WorldCover tile for a point: 3° tiles named by their south-west corner."""
    la = math.floor(lat / 3) * 3
    lo = math.floor(lon / 3) * 3
    ns = f"{'N' if la >= 0 else 'S'}{abs(la):02d}"
    ew = f"{'E' if lo >= 0 else 'W'}{abs(lo):03d}"
    return f"ESA_WorldCover_10m_2020_v100_{ns}{ew}_Map"


def fetch_tile(name: str) -> Path | None:
    """Download a tile once. 10-130 MB each; read locally after that."""
    from . import goes

    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{name}.tif"
    if path.exists() and path.stat().st_size > 1_000_000:
        return path
    try:
        goes.download(f"{BUCKET}/{name}.tif", str(path))
        return path
    except Exception:                                   # noqa: BLE001
        path.unlink(missing_ok=True)                    # open ocean: no tile
        return None


def _read(path: Path, divisor: int = DIVISOR):
    import rasterio
    from rasterio.enums import Resampling

    with rasterio.open(path) as ds:
        h, w = ds.height // divisor, ds.width // divisor
        # Nearest, never averaged: these are class codes, and the mean of
        # "tree" and "built" is "shrub".
        arr = ds.read(1, out_shape=(h, w), resampling=Resampling.nearest)
        transform = ds.transform @ ds.transform.scale(ds.width / w, ds.height / h)
    return arr, transform


def fractions_in(arr, transform, cell) -> dict | None:
    """Share of each class among the pixels whose centre lies in the cell.

    Pixels outside the array — a cell straddling a tile edge — are simply
    not counted, so the fraction comes from the part that was read, never
    from a fill value standing in for the rest. Nodata (0) is not counted.
    """
    import h3

    res = h3.get_resolution(cell)
    ring = h3.cell_to_boundary(cell)
    lats = [p[0] for p in ring]
    lons = [p[1] for p in ring]
    inv = ~transform
    c0, r0 = inv @ (min(lons), max(lats))
    c1, r1 = inv @ (max(lons), min(lats))
    r0, c0 = max(0, int(math.floor(r0))), max(0, int(math.floor(c0)))
    r1 = min(arr.shape[0], int(math.ceil(r1)))
    c1 = min(arr.shape[1], int(math.ceil(c1)))
    if r1 <= r0 or c1 <= c0:
        return None

    step = max(1, int(math.sqrt((r1 - r0) * (c1 - c0) / MAX_PIXELS)))
    rows = np.arange(r0, r1, step)
    cols = np.arange(c0, c1, step)
    sub = arr[np.ix_(rows, cols)]
    cc, rr = np.meshgrid(cols + 0.5, rows + 0.5)
    xs, ys = transform @ (cc.ravel(), rr.ravel())
    inside = np.fromiter((h3.latlng_to_cell(y, x, res) == cell
                          for x, y in zip(xs, ys)), bool, count=xs.size)
    vals = sub.ravel()[inside]
    vals = vals[vals != 0]
    if vals.size == 0:
        return None
    codes, counts = np.unique(vals, return_counts=True)
    out = {name: 0.0 for name in CLASSES.values()}
    for code, n in zip(codes, counts):
        if int(code) in CLASSES:
            out[CLASSES[int(code)]] = n / vals.size
    out["px"] = int(vals.size)
    return out


def cells_landcover(cells, progress=True) -> dict:
    """Class fractions per H3 cell: `{h3: {clase: fracción, ..., "px": n}}`."""
    import h3

    by_tile: dict[str, list] = {}
    for c in cells:
        lat, lon = h3.cell_to_latlng(c)
        by_tile.setdefault(tile_name(lat, lon), []).append(c)

    out: dict[str, dict] = {}
    for name, group in sorted(by_tile.items()):
        path = fetch_tile(name)
        if path is None:
            continue
        arr, transform = _read(path)
        for c in group:
            f = fractions_in(arr, transform, c)
            if f is not None:
                out[c] = f
        if progress:
            print(f"  {name}: {len(group):,} celdas", flush=True)
        del arr
    return out
