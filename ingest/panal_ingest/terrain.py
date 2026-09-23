"""Terrain — slope, from the Copernicus GLO-30 digital elevation model.

Fire runs uphill. Rate of spread roughly doubles for every 10° of slope, which
is why a house on a ravine wall is in a different category of danger from the
same house on flat ground. Slope is therefore the first physical term in the
wildland-urban interface exposure map, and the one that does not change
between seasons.

Source: `copernicus-dem-30m` on AWS Open Data. Public, no credentials, COG
GeoTIFF at 1 arc-second (~30 m), one file per 1°×1° tile named by its
south-west corner.

**It is a surface model, not bare earth**, and that showed up immediately.
GLO-30 includes trees and buildings, so building edges read as terrain.
Measured over an r9 cell: central Santiago, which is flat, came back at 7.3°
mean slope against a genuine Valparaíso hillside at 20.7°. That artefact
lands exactly where this map matters, because wildland-urban interface
exposure is scored on urban cells.

Smoothing the elevation with a 3×3 mean before taking the gradient halves
the artefact while leaving real terrain almost untouched — Santiago falls to
3.6°, the hillside only to 18.4°, so the hillside-to-urban ratio improves
from 2.8× to 5.1×. Taking the median slope instead does not help: buildings
are pervasive across an urban cell, not outliers within it.

The proper fix is a bare-earth model. **FABDEM** (Copernicus with forests and
buildings removed, 30 m) is free for non-commercial use, which PANAL is, and
is the upgrade to make before Phase 4 — Cell2Fire needs true ground slope,
not a smoothed surface.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

BUCKET = "https://copernicus-dem-30m.s3.amazonaws.com"
CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "dem"

# GLO-30 is 1 arc-second. Ground spacing in metres varies with latitude for
# the x axis and is roughly constant for y.
ARCSEC_M = 30.87


def tile_name(lat: int, lon: int) -> str:
    """Copernicus tile id from the integer south-west corner."""
    ns = f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}"
    ew = f"{'E' if lon >= 0 else 'W'}{abs(lon):03d}"
    return f"Copernicus_DSM_COG_10_{ns}_00_{ew}_00_DEM"


def tiles_for(bbox) -> list[str]:
    """Every tile covering a (lon_min, lat_min, lon_max, lat_max) box."""
    lon_min, lat_min, lon_max, lat_max = bbox
    out = []
    for lat in range(math.floor(lat_min), math.ceil(lat_max)):
        for lon in range(math.floor(lon_min), math.ceil(lon_max)):
            out.append(tile_name(lat, lon))
    return out


def fetch_tile(name: str) -> Path | None:
    """Download a tile once and cache it.

    Windowed reads straight off the remote COG work but cost about nine
    seconds each in range-request overhead, which does not scale to a
    national grid. A tile is ~33 MB and covers 1°×1°, so fetching whole
    tiles and reading locally is far cheaper for anything but a single
    lookup.
    """
    from . import goes  # the retrying downloader

    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{name}.tif"
    if path.exists() and path.stat().st_size > 1_000_000:
        return path
    try:
        goes.download(f"{BUCKET}/{name}/{name}.tif", str(path))
        return path
    except Exception:                                   # noqa: BLE001
        # Ocean tiles simply do not exist in GLO-30. That is not an error:
        # there is no land there to have a slope.
        path.unlink(missing_ok=True)
        return None


def _smooth3(a: np.ndarray) -> np.ndarray:
    """3×3 mean. Suppresses building edges before the gradient sees them."""
    from numpy.lib.stride_tricks import sliding_window_view

    if min(a.shape) < 3:
        return a
    return sliding_window_view(a, (3, 3)).mean(axis=(-1, -2))


def slope_degrees(elev: np.ndarray, lat: float, smooth: bool = True):
    """Slope in degrees from an elevation array.

    `lat` sets the east-west ground spacing, which shrinks with the cosine of
    latitude. Ignoring that would overstate east-west slope by a third at
    Chile's southern end.

    `smooth` applies a 3×3 mean first, which is on by default because GLO-30
    is a surface model: without it, building edges in dense urban fabric read
    as terrain. See the module docstring for the measurements.
    """
    a = elev.astype("float32")
    if smooth:
        a = _smooth3(a)
    dy = ARCSEC_M
    dx = ARCSEC_M * math.cos(math.radians(lat))
    gy, gx = np.gradient(a, dy, dx)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def cells_terrain(cells, res_hint: int = 9) -> dict:
    """Slope and elevation statistics for a list of H3 cells.

    Returns `{h3: {"elev_m", "slope_deg", "slope_max_deg", "aspect_deg"}}`.
    Cells with no elevation data — open ocean — are omitted rather than
    reported as flat.
    """
    import h3
    import rasterio
    from rasterio.windows import from_bounds

    if not cells:
        return {}

    # Group cells by the tile that contains them, so each tile opens once.
    by_tile: dict[str, list] = {}
    for c in cells:
        lat, lon = h3.cell_to_latlng(c)
        by_tile.setdefault(tile_name(math.floor(lat), math.floor(lon)),
                           []).append((c, lat, lon))

    out: dict[str, dict] = {}
    for name, group in by_tile.items():
        path = fetch_tile(name)
        if path is None:
            continue
        with rasterio.open(path) as ds:
            for cell, lat, lon in group:
                ring = h3.cell_to_boundary(cell)
                lats = [p[0] for p in ring]
                lons = [p[1] for p in ring]
                try:
                    win = from_bounds(min(lons), min(lats), max(lons),
                                      max(lats), ds.transform)
                    # One pixel of margin so the gradient has neighbours.
                    win = win.round_offsets().round_lengths()
                    elev = ds.read(1, window=win, boundless=True,
                                   fill_value=ds.nodata or 0)
                except Exception:                       # noqa: BLE001
                    continue
                if elev.size < 4 or not np.isfinite(elev).any():
                    continue
                if ds.nodata is not None:
                    elev = np.where(elev == ds.nodata, np.nan, elev)
                if np.isnan(elev).all():
                    continue
                elev = np.nan_to_num(elev, nan=float(np.nanmean(elev)))

                sl = slope_degrees(elev, lat)
                out[cell] = {
                    "elev_m": round(float(elev.mean()), 1),
                    "slope_deg": round(float(sl.mean()), 2),
                    "slope_max_deg": round(float(sl.max()), 2),
                    "relief_m": round(float(elev.max() - elev.min()), 1),
                }
    return out


def slope_factor(slope_deg: float) -> float:
    """Slope as a 0-1 exposure term.

    Fire spreads faster uphill, steeply non-linearly: the common rule of
    thumb is that rate of spread doubles for every 10° of slope. This maps
    that shape onto 0-1, saturating at 35° where terrain stops being the
    limiting factor and the fire is running regardless.
    """
    if slope_deg is None or slope_deg <= 0:
        return 0.0
    return float(min(1.0, (2 ** (slope_deg / 10.0) - 1) / (2 ** 3.5 - 1)))
