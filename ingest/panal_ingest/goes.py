"""GOES-East ABI Level 2 Fire/Hot Spot Characterization ingest.

The tempo layer of PANAL's detection stack: a new full-disk look every 10
minutes, published to a public AWS bucket about a minute after the scan
closes. Coarse (2 km) and officially provisional, so it answers "something is
happening near here", never "here is exactly where".

No credentials are required for any of this.
"""

from __future__ import annotations

import datetime as dt
import re
import time
from datetime import date as dt_date
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import numpy as np

PRODUCT = "ABI-L2-FDCF"  # F = full disk, the only sector that covers Chile

# GOES-East changed satellites on 2025-04-07. Historical backfill before that
# date has to read GOES-16, so the bucket is chosen by date rather than fixed.
GOES19_FROM = dt_date(2025, 4, 7)


def bucket_for(when) -> str:
    """Which public bucket held GOES-East on this date."""
    d = when.date() if hasattr(when, "date") else when
    return "noaa-goes19" if d >= GOES19_FROM else "noaa-goes16"


BUCKET = "noaa-goes19"  # default for live ingest

# Mask codes that count as a detection. The `temporally_filtered_*` variants
# (30-35) are the same categories after the algorithm's multi-scan filter and
# are generally the more trustworthy of the two.
FIRE_CODES: dict[int, str] = {
    10: "good",
    11: "saturated",
    12: "cloud_contaminated",
    13: "high_probability",
    14: "medium_probability",
    15: "low_probability",
    30: "good",
    31: "saturated",
    32: "cloud_contaminated",
    33: "high_probability",
    34: "medium_probability",
    35: "low_probability",
}
TEMPORALLY_FILTERED = {30, 31, 32, 33, 34, 35}

# Ranked worst to best, for thresholding.
CONFIDENCE_ORDER = [
    "low_probability",
    "cloud_contaminated",
    "medium_probability",
    "high_probability",
    "saturated",
    "good",
]

# Non-detection mask codes worth surfacing rather than silently dropping:
# a blocked-out pixel is not the same as a pixel with no fire.
BLOCKED_CODES = {
    50: "lza_block_out",  # viewing angle too oblique — matters in the far south
    60: "sza_or_glint_block_out",
    40: "off_earth",
}


@dataclass(frozen=True)
class Scan:
    """One ABI full-disk scan."""

    key: str
    start: dt.datetime
    end: dt.datetime
    bucket: str = BUCKET

    @property
    def url(self) -> str:
        return f"https://{self.bucket}.s3.amazonaws.com/{self.key}"


_KEY_RE = re.compile(
    r"_s(?P<s>\d{14})_e(?P<e>\d{14})_c\d{14}\.nc$"
)


def _parse_stamp(raw: str) -> dt.datetime:
    """GOES timestamps are YYYYDDDHHMMSSf (day-of-year, tenths of a second)."""
    year, doy = int(raw[0:4]), int(raw[4:7])
    hour, minute, sec, tenth = (
        int(raw[7:9]),
        int(raw[9:11]),
        int(raw[11:13]),
        int(raw[13]),
    )
    base = dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(days=doy - 1)
    return base + dt.timedelta(
        hours=hour, minutes=minute, seconds=sec, milliseconds=tenth * 100
    )


def list_scans(when: dt.datetime) -> list[Scan]:
    """List the scans published for the UTC hour containing `when`."""
    bucket = bucket_for(when)
    prefix = f"{PRODUCT}/{when.year}/{when.strftime('%j')}/{when.strftime('%H')}/"
    url = (
        f"https://{bucket}.s3.amazonaws.com/"
        f"?list-type=2&prefix={prefix}&max-keys=1000"
    )
    with urlopen(url, timeout=60) as resp:
        body = resp.read().decode()

    scans = []
    for key in re.findall(r"<Key>([^<]+)</Key>", body):
        m = _KEY_RE.search(key)
        if m:
            scans.append(
                Scan(
                    key,
                    _parse_stamp(m.group("s")),
                    _parse_stamp(m.group("e")),
                    bucket,
                )
            )
    return sorted(scans, key=lambda s: s.start)


def latest_scan(now: dt.datetime | None = None) -> Scan:
    """Most recent published scan, falling back to the previous hour."""
    now = now or dt.datetime.now(dt.timezone.utc)
    scans = list_scans(now)
    if not scans:
        scans = list_scans(now - dt.timedelta(hours=1))
    if not scans:
        raise RuntimeError("no GOES scans published in the last two hours")
    return scans[-1]


def download(url: str, dest: str, attempts: int = 4, backoff: float = 1.5) -> str:
    """Fetch a file, retrying transient network failures.

    S3 resets connections often enough that a single reset must not kill an
    ingest that is meant to run every ten minutes, or a backfill that is
    sixty files deep.
    """
    import shutil

    last: Exception | None = None
    for attempt in range(attempts):
        try:
            with urlopen(url, timeout=120) as resp, open(dest, "wb") as fh:
                shutil.copyfileobj(resp, fh)
            return dest
        except (ConnectionResetError, TimeoutError, URLError, HTTPError, OSError) as exc:
            last = exc
            if isinstance(exc, HTTPError) and 400 <= exc.code < 500 and exc.code != 429:
                raise  # not transient: a missing key will never appear
            if attempt < attempts - 1:
                time.sleep(backoff * (2 ** attempt))
    raise RuntimeError(f"download failed after {attempts} attempts: {url}") from last


def geolocate(x: np.ndarray, y: np.ndarray, proj) -> tuple[np.ndarray, np.ndarray]:
    """ABI fixed-grid scan angles (radians) to geodetic lat/lon (degrees).

    Implements the GOES-R Product Definition and Users' Guide navigation, as
    published in the file's own `goes_imager_projection` variable rather than
    hardcoded, so this keeps working if the satellite is repositioned.
    """
    h = proj.perspective_point_height + proj.semi_major_axis
    r_eq = proj.semi_major_axis
    r_pol = proj.semi_minor_axis
    lon_origin = np.deg2rad(proj.longitude_of_projection_origin)
    ratio = (r_eq * r_eq) / (r_pol * r_pol)

    sin_x, cos_x = np.sin(x), np.cos(x)
    sin_y, cos_y = np.sin(y), np.cos(y)

    a = sin_x**2 + cos_x**2 * (cos_y**2 + ratio * sin_y**2)
    b = -2.0 * h * cos_x * cos_y
    c = h * h - r_eq * r_eq

    disc = b * b - 4.0 * a * c
    # Negative discriminant means the ray misses the Earth entirely.
    with np.errstate(invalid="ignore"):
        r_s = (-b - np.sqrt(disc)) / (2.0 * a)

    s_x = r_s * cos_x * cos_y
    s_y = -r_s * sin_x
    s_z = r_s * cos_x * sin_y

    lat = np.arctan(ratio * s_z / np.sqrt((h - s_x) ** 2 + s_y**2))
    lon = lon_origin - np.arctan(s_y / (h - s_x))

    lat = np.where(disc < 0, np.nan, np.rad2deg(lat))
    lon = np.where(disc < 0, np.nan, np.rad2deg(lon))
    return lat, lon


def extract_detections(path: str):
    """Read one FDCF file and return fire detections as a DataFrame.

    Geolocation is computed only for the detected pixels — a few hundred out
    of 29 million — so this stays fast enough to run every 10 minutes.
    """
    import netCDF4 as nc
    import pandas as pd

    ds = nc.Dataset(path)
    mask = np.asarray(ds.variables["Mask"][:].filled(-1), dtype=np.int32)

    rows, cols = np.where(np.isin(mask, list(FIRE_CODES)))
    if rows.size == 0:
        return pd.DataFrame(
            columns=[
                "lat", "lon", "mask_code", "confidence", "temporally_filtered",
                "frp_mw", "area_m2", "temp_k", "dqf", "scan_start", "scan_end",
            ]
        )

    x = np.asarray(ds.variables["x"][:])[cols]
    y = np.asarray(ds.variables["y"][:])[rows]
    lat, lon = geolocate(x, y, ds.variables["goes_imager_projection"])

    def pull(name):
        if name not in ds.variables:
            return np.full(rows.size, np.nan)
        return np.asarray(
            ds.variables[name][:].astype("float64").filled(np.nan)
        )[rows, cols]

    codes = mask[rows, cols]
    start = dt.datetime.fromisoformat(ds.time_coverage_start.replace("Z", "+00:00"))
    end = dt.datetime.fromisoformat(ds.time_coverage_end.replace("Z", "+00:00"))

    return pd.DataFrame(
        {
            "lat": lat,
            "lon": lon,
            "mask_code": codes,
            "confidence": [FIRE_CODES[int(c)] for c in codes],
            "temporally_filtered": np.isin(codes, list(TEMPORALLY_FILTERED)),
            "frp_mw": pull("Power"),
            "area_m2": pull("Area"),
            "temp_k": pull("Temp"),
            "dqf": pull("DQF"),
            "scan_start": start,
            "scan_end": end,
        }
    ).dropna(subset=["lat", "lon"])


def blocked_fraction(path: str, lat_min: float, lat_max: float,
                     lon_min: float, lon_max: float) -> dict:
    """How much of a lat/lon window GOES cannot see this scan.

    Coverage is not uniform: at oblique viewing angles the algorithm blocks
    pixels out entirely, and a blocked pixel reports no fire for the same
    reason a closed eye does. Anything built on GOES has to know where its
    own blind spots are.
    """
    import netCDF4 as nc

    ds = nc.Dataset(path)
    mask = np.asarray(ds.variables["Mask"][:].filled(-1), dtype=np.int32)
    x = np.asarray(ds.variables["x"][:])
    y = np.asarray(ds.variables["y"][:])
    xx, yy = np.meshgrid(x, y)
    lat, lon = geolocate(xx, yy, ds.variables["goes_imager_projection"])

    window = (
        (lat >= lat_min) & (lat <= lat_max)
        & (lon >= lon_min) & (lon <= lon_max)
    )
    total = int(window.sum())
    if total == 0:
        return {"total": 0}

    out = {"total": total}
    for code, name in BLOCKED_CODES.items():
        out[name] = int(((mask == code) & window).sum())
    out["usable"] = total - sum(
        out[n] for n in BLOCKED_CODES.values()
    )
    return out
