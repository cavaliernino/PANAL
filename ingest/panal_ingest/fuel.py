"""Fuel — how much there is to burn, and how dry it is.

The missing term that sank the first exposure index. An interface is defined
by adjacency to burnable vegetation, and without this a house beside dense
matorral and the same house surrounded by asphalt score alike.

Source: Sentinel-2 L2A through the Earth Search STAC API on AWS Open Data.
Public, no credentials, 10-20 m bands as cloud-optimised GeoTIFFs.

## More green is not more danger

The obvious reading — high NDVI means fuel — is wrong in exactly the places
that matter. An irrigated orchard in January has the highest NDVI in the
frame and will not carry fire. Cured grassland has moderate NDVI and will.

Fire needs biomass that is **present and dry**, so two indices are used
together:

    NDVI  = (NIR - RED)   / (NIR + RED)      how much vegetation exists
    NDMI  = (NIR - SWIR16)/ (NIR + SWIR16)   how much water is in it

High NDVI with low NDMI is cured fuel: the dangerous quadrant. High NDVI
with high NDMI is green and irrigated. Low NDVI is bare ground, and no
amount of dryness makes bare ground burn.

## Timing is part of the measurement

Imagery is taken from the **late dry season** — February and March in Chile
— because that is when fuel is at its most cured and when the fire season
peaks. A scene from July would describe a landscape that does not exist in
January.

## CONAF is the other half, and it is not here

This measures fuel *state*. CONAF's Catastro de Uso de Suelo y Vegetación
gives fuel *type*, which is what the Kitral models in Cell2Fire actually
consume, and it is the authoritative Chilean source at 1:50,000.

It has no public WFS, ArcGIS REST or direct download that could be reached
here: the SIT CONAF system requires navigating its own web interface. That
makes it an agenda item for the Phase 5 conversation rather than an ingest
module — and a cheap one to ask for, since they publish it already.
"""

from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np

STAC = "https://earth-search.aws.element84.com/v1/search"
COLLECTION = "sentinel-2-l2a"

# Late dry season in Chile: fuel at its most cured, fire season at its peak.
DEFAULT_WINDOW = ("02-01", "03-31")

# Scene Classification Layer codes that are not usable ground.
# 0 nodata, 1 saturated, 3 cloud shadow, 8/9 cloud medium/high, 10 cirrus.
SCL_BAD = frozenset({0, 1, 3, 8, 9, 10})

# Sentinel-2 bands are 10-20 m. An H3 r9 cell is 321 m across, so reading at
# roughly 1/16 scale keeps a handful of pixels per cell while making a whole
# scene cheap to pull — windowed reads per cell cost seconds each in range
# requests and do not scale to tens of thousands of cells.
OVERVIEW_DIVISOR = 16


def search(bbox, year: int, window=DEFAULT_WINDOW, max_cloud: float = 20.0,
           limit: int = 40):
    """Least-cloudy Sentinel-2 scenes over a bbox in the dry-season window."""
    start, end = window
    body = {
        "collections": [COLLECTION],
        "bbox": list(bbox),
        "datetime": f"{year}-{start}T00:00:00Z/{year}-{end}T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": max_cloud}},
        "limit": limit,
    }
    req = Request(STAC, data=json.dumps(body).encode(),
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=90) as resp:
        data = json.load(resp)
    feats = data.get("features", [])
    return sorted(feats, key=lambda f: f["properties"].get("eo:cloud_cover", 100))


def _read_scaled(url: str, divisor: int):
    """Read a whole COG band at reduced resolution, using its overviews."""
    import rasterio

    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                      CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF"):
        with rasterio.open(f"/vsicurl/{url}") as ds:
            h = max(1, ds.height // divisor)
            w = max(1, ds.width // divisor)
            arr = ds.read(1, out_shape=(h, w)).astype("float32")
            transform = ds.transform * ds.transform.scale(
                ds.width / w, ds.height / h)
            return arr, transform, ds.crs


def scene_indices(feature, divisor: int = OVERVIEW_DIVISOR):
    """NDVI and NDMI for one scene, cloud-masked, at reduced resolution."""
    assets = feature["assets"]
    red, transform, crs = _read_scaled(assets["red"]["href"], divisor)
    nir, _, _ = _read_scaled(assets["nir"]["href"], divisor)
    swir, _, _ = _read_scaled(assets["swir16"]["href"], divisor)
    scl, _, _ = _read_scaled(assets["scl"]["href"], divisor)

    # swir16 is a 20 m band; its array can differ by a pixel after scaling.
    shape = red.shape
    if swir.shape != shape:
        swir = _resize_nearest(swir, shape)
    if scl.shape != shape:
        scl = _resize_nearest(scl, shape)

    bad = np.isin(scl.astype("int16"), list(SCL_BAD))
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir - red) / (nir + red)
        ndmi = (nir - swir) / (nir + swir)
    ndvi[bad] = np.nan
    ndmi[bad] = np.nan
    return ndvi, ndmi, transform, crs


def _resize_nearest(a, shape):
    yi = (np.linspace(0, a.shape[0] - 1, shape[0])).round().astype(int)
    xi = (np.linspace(0, a.shape[1] - 1, shape[1])).round().astype(int)
    return a[yi][:, xi]


def fuel_factor(ndvi: float, ndmi: float) -> float:
    """0-1 fuel hazard from biomass and dryness.

    Multiplicative, because both conditions are necessary. Bare ground
    cannot burn however dry it is, and saturated vegetation will not carry
    fire however much of it there is.

    `biomass` ramps from bare (NDVI 0.15) to full cover (0.6); above that
    extra greenness adds nothing, since the ground is already continuous
    fuel. `dryness` inverts NDMI over the range where Chilean vegetation
    actually sits in late summer, roughly 0.35 (moist) down to -0.1 (cured).
    """
    if ndvi is None or ndmi is None or not np.isfinite(ndvi) or not np.isfinite(ndmi):
        return float("nan")
    biomass = np.clip((ndvi - 0.15) / (0.60 - 0.15), 0.0, 1.0)
    dryness = np.clip((0.35 - ndmi) / (0.35 - (-0.10)), 0.0, 1.0)
    return float(biomass * dryness)


def cells_fuel(cells, year: int, window=DEFAULT_WINDOW, max_cloud: float = 20.0,
               divisor: int = OVERVIEW_DIVISOR, progress=True) -> dict:
    """NDVI, NDMI and a fuel factor per H3 cell.

    Scenes are read whole at reduced resolution and sampled per cell, rather
    than one windowed read per cell: the latter costs seconds apiece in HTTP
    range requests, which does not survive tens of thousands of cells.
    Where scenes overlap, the **driest** observation wins — a cell that was
    cured in any dry-season pass is cured fuel.
    """
    import h3
    from pyproj import Transformer

    if not cells:
        return {}

    lats, lons = zip(*(h3.cell_to_latlng(c) for c in cells))
    bbox = (min(lons), min(lats), max(lons), max(lats))
    scenes = search(bbox, year, window, max_cloud)
    if progress:
        print(f"  {len(scenes)} escenas Sentinel-2 en {year} "
              f"({window[0]}..{window[1]}, nubes <{max_cloud:.0f}%)", flush=True)
    if not scenes:
        return {}

    out: dict[str, dict] = {}
    for i, feat in enumerate(scenes, 1):
        try:
            ndvi, ndmi, transform, crs = scene_indices(feat, divisor)
        except Exception as exc:                        # noqa: BLE001
            if progress:
                print(f"    ! {feat['id']}: {str(exc)[:60]}", flush=True)
            continue

        to_scene = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        inv = ~transform
        h, w = ndvi.shape
        hit = 0
        for cell, lat, lon in zip(cells, lats, lons):
            x, y = to_scene.transform(lon, lat)
            col, row = inv * (x, y)
            r, c = int(row), int(col)
            if not (0 <= r < h and 0 <= c < w):
                continue
            v, m = ndvi[r, c], ndmi[r, c]
            if not (np.isfinite(v) and np.isfinite(m)):
                continue
            hit += 1
            prev = out.get(cell)
            # Driest wins: cured in any pass means cured fuel.
            if prev is None or m < prev["ndmi"]:
                out[cell] = {"ndvi": round(float(v), 4),
                             "ndmi": round(float(m), 4),
                             "fuel_factor": round(fuel_factor(v, m), 4),
                             "scene": feat["id"]}
        if progress:
            print(f"    [{i}/{len(scenes)}] {feat['id'][:34]} "
                  f"→ {hit:,} celdas", flush=True)
    return out
