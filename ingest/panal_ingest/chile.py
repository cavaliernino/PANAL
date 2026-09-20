"""Chilean territory clipping.

A bounding box over Chile is about 90% Argentina and Bolivia — the country is
narrow and the Andes run its entire length — so every detection is tested
against real geometry before it is allowed onto the map.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

# Includes the insular territories: Chiloé, Tierra del Fuego, Juan Fernández,
# Desventuradas and Rapa Nui.
BOUNDARY = Path(__file__).parent / "reference" / "chile_boundary.geojson"

# Generous pre-filter. Cheap rejection before the expensive polygon test;
# wide enough to keep Rapa Nui (lon -109.5) and Cape Horn (lat -56).
BBOX = (-110.0, -56.5, -66.0, -17.0)  # lon_min, lat_min, lon_max, lat_max


@lru_cache(maxsize=1)
def _rings() -> list[np.ndarray]:
    """Every exterior ring of Chilean territory, as (n, 2) lon/lat arrays."""
    data = json.loads(BOUNDARY.read_text())
    feats = data["features"] if data.get("type") == "FeatureCollection" else [data]

    rings: list[np.ndarray] = []
    for feat in feats:
        geom = feat.get("geometry", feat)
        polys = (
            [geom["coordinates"]]
            if geom["type"] == "Polygon"
            else geom["coordinates"]
        )
        for poly in polys:
            rings.append(np.asarray(poly[0], dtype=float))  # exterior ring
    return rings


def _in_ring(lon: np.ndarray, lat: np.ndarray, ring: np.ndarray) -> np.ndarray:
    """Vectorised ray-casting point-in-polygon."""
    x1, y1 = ring[:-1, 0], ring[:-1, 1]
    x2, y2 = ring[1:, 0], ring[1:, 1]

    lon = lon[:, None]
    lat = lat[:, None]

    straddles = (y1 > lat) != (y2 > lat)
    with np.errstate(divide="ignore", invalid="ignore"):
        x_cross = (x2 - x1) * (lat - y1) / (y2 - y1) + x1
    return (straddles & (lon < x_cross)).sum(axis=1) % 2 == 1


def in_chile(lon, lat) -> np.ndarray:
    """Boolean mask: is each point inside Chilean territory?"""
    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)

    lon_min, lat_min, lon_max, lat_max = BBOX
    inside = (
        (lon >= lon_min) & (lon <= lon_max)
        & (lat >= lat_min) & (lat <= lat_max)
    )
    if not inside.any():
        return inside

    idx = np.flatnonzero(inside)
    hit = np.zeros(idx.size, dtype=bool)
    for ring in _rings():
        # Skip rings whose own bbox cannot contain any remaining candidate.
        r_lon, r_lat = ring[:, 0], ring[:, 1]
        maybe = (
            (lon[idx] >= r_lon.min()) & (lon[idx] <= r_lon.max())
            & (lat[idx] >= r_lat.min()) & (lat[idx] <= r_lat.max())
            & ~hit
        )
        if not maybe.any():
            continue
        sub = idx[maybe]
        hit[maybe] |= _in_ring(lon[sub], lat[sub], ring)

    out = np.zeros(lon.shape, dtype=bool)
    out[idx] = hit
    return out


def clip(df, lon_col: str = "lon", lat_col: str = "lat"):
    """Keep only the rows inside Chilean territory."""
    if len(df) == 0:
        return df
    return df[in_chile(df[lon_col].to_numpy(), df[lat_col].to_numpy())].copy()
