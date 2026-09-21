"""NASA FIRMS VIIRS / MODIS — the precision layer of the detection stack.

GOES carries tempo: a look every ten minutes at 2 km. VIIRS carries
precision: 375 m, but only three or four passes a day. They are not
redundant, and PANAL renders each at the resolution it actually has — VIIRS
at H3 r9, whose 402 m cell diameter matches a 375 m pixel almost exactly
(ratio 1.07), against GOES at r7.

Two access paths:

* **Recent, no credentials.** Regional CSVs covering the last 24 h, 48 h or
  7 days. Enough for live operation.
* **Archive, needs a free MAP_KEY.** The area API serves arbitrary dates.
  Register at https://firms.modaps.eosdis.nasa.gov/api/map_key/ — free and
  instant. Needed to backfill past fire seasons.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import tempfile
from pathlib import Path

from . import goes

BASE = "https://firms.modaps.eosdis.nasa.gov"

# H3 resolution per sensor, chosen so a cell never claims more precision than
# the pixel it came from.
RESOLUTION = {"viirs": 9, "modis": 7}

# Regional near-real-time products, no key required.
REGIONAL = {
    "VIIRS_NOAA20_NRT": "noaa-20-viirs-c2/csv/J1_VIIRS_C2_South_America_{w}.csv",
    "VIIRS_NOAA21_NRT": "noaa-21-viirs-c2/csv/J2_VIIRS_C2_South_America_{w}.csv",
    "VIIRS_SNPP_NRT": "suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_South_America_{w}.csv",
    "MODIS_NRT": "modis/csv/MODIS_C6_1_South_America_{w}.csv",
}
WINDOWS = ("24h", "48h", "7d")


def _confidence(raw: str, sensor: str) -> str:
    """Normalise to the shared vocabulary the UI maps to opacity.

    VIIRS reports low/nominal/high; MODIS reports 0-100. Both collapse onto
    the same scale used for GOES so one legend covers every source.
    """
    v = (raw or "").strip().lower()
    if sensor == "modis":
        try:
            n = float(v)
        except ValueError:
            return "low_probability"
        return ("high_probability" if n >= 80
                else "medium_probability" if n >= 30
                else "low_probability")
    return {
        "h": "high_probability", "high": "high_probability",
        "n": "medium_probability", "nominal": "medium_probability",
        "l": "low_probability", "low": "low_probability",
    }.get(v, "low_probability")


def _parse(text: str, sensor: str, source: str):
    """FIRMS CSV to a DataFrame shaped like the GOES detections."""
    import pandas as pd

    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        return pd.DataFrame(columns=[
            "lat", "lon", "confidence", "frp_mw", "acq", "sensor", "source",
        ])

    out = []
    for r in rows:
        try:
            lat, lon = float(r["latitude"]), float(r["longitude"])
        except (KeyError, ValueError):
            continue
        # acq_time is HHMM, sometimes without the leading zero.
        hhmm = str(r.get("acq_time", "0")).zfill(4)
        try:
            acq = dt.datetime.strptime(
                f"{r['acq_date']} {hhmm}", "%Y-%m-%d %H%M"
            ).replace(tzinfo=dt.timezone.utc)
        except (KeyError, ValueError):
            continue
        out.append({
            "lat": lat, "lon": lon,
            "confidence": _confidence(r.get("confidence", ""), sensor),
            "frp_mw": float(r.get("frp") or 0),
            "acq": acq,
            "satellite": r.get("satellite", ""),
            "daynight": r.get("daynight", ""),
            "sensor": sensor,
            "source": source,
        })
    return pd.DataFrame(out)


def fetch_recent(product: str = "VIIRS_NOAA20_NRT", window: str = "24h"):
    """Recent detections over South America. No credentials required."""
    if product not in REGIONAL:
        raise ValueError(f"unknown product {product!r}; try {sorted(REGIONAL)}")
    if window not in WINDOWS:
        raise ValueError(f"window must be one of {WINDOWS}")

    url = f"{BASE}/data/active_fire/{REGIONAL[product].format(w=window)}"
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        path = goes.download(url, tmp.name)
    try:
        text = Path(path).read_text()
    finally:
        Path(path).unlink(missing_ok=True)

    sensor = "modis" if product.startswith("MODIS") else "viirs"
    return _parse(text, sensor, product)


def fetch_archive(map_key: str, bbox, day: dt.date, days: int = 1,
                  product: str = "VIIRS_SNPP_SP"):
    """Detections for a past date. Needs a free FIRMS MAP_KEY.

    `bbox` is (lon_min, lat_min, lon_max, lat_max); `days` is 1-10.
    Use the `_SP` (standard processing) products for archive dates and the
    `_NRT` ones for the last couple of months.
    """
    west, south, east, north = bbox
    url = (f"{BASE}/api/area/csv/{map_key}/{product}/"
           f"{west},{south},{east},{north}/{days}/{day:%Y-%m-%d}")

    from urllib.error import HTTPError

    NO_KEY = ("FIRMS rejected the request — usually a missing or invalid "
              "MAP_KEY. Register a free one, instantly, at "
              "https://firms.modaps.eosdis.nasa.gov/api/map_key/")

    try:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            path = goes.download(url, tmp.name)
    except HTTPError as exc:
        # FIRMS answers a bad key with 400, not a readable body, so the
        # generic downloader cannot tell this apart from a malformed query.
        if exc.code in (400, 401, 403):
            raise RuntimeError(NO_KEY) from exc
        raise
    try:
        text = Path(path).read_text()
    finally:
        Path(path).unlink(missing_ok=True)

    head = text.lstrip()[:80].lower()
    if head.startswith("invalid") or "map_key" in head:
        raise RuntimeError(NO_KEY)
    sensor = "modis" if product.startswith("MODIS") else "viirs"
    return _parse(text, sensor, product)


def to_h3(df, res: int | None = None):
    """Clip to Chile and index at the sensor's honest H3 resolution."""
    import h3

    from . import chile

    df = chile.clip(df)
    if len(df) == 0:
        return df

    sensor = df["sensor"].iloc[0]
    r = res if res is not None else RESOLUTION.get(sensor, 8)
    df = df.copy()
    df["h3"] = [h3.latlng_to_cell(a, o, r) for a, o in zip(df["lat"], df["lon"])]
    df["h3_res"] = r
    return df
