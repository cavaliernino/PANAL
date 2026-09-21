"""NASA POWER — hourly weather, and the Chilean 30-30-30 pre-alert factor.

POWER is MERRA-2 reanalysis served as a keyless point API. It gives PANAL
the three variables the Chilean fire services watch: air temperature,
relative humidity and wind.

**Resolution caveat, which matters operationally.** MERRA-2 is a global
reanalysis on a roughly 50 km grid. In terrain like Valparaíso's ravines the
local wind can differ sharply from the grid cell average, so POWER is right
for regional context and for replaying past events, and wrong as the sole
input to an operational alert. Local stations — DMC, or a corps' own — are
what an alert should eventually read.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from urllib.parse import urlencode

from . import goes  # reuse the retrying downloader

BASE = "https://power.larc.nasa.gov/api/temporal/hourly/point"

# T2M   air temperature at 2 m          (C)
# RH2M  relative humidity at 2 m        (%)
# WS10M wind speed at 10 m              (m/s)  — 10 m is the fire-weather standard
# WD10M wind direction at 10 m          (degrees)
PARAMETERS = ("T2M", "RH2M", "WS10M", "WD10M")

MS_TO_KMH = 3.6
MS_TO_KNOTS = 1.94384


@dataclass(frozen=True)
class Factor30:
    """The 30-30-30 pre-alert factor.

    Chile's fire services use it as an early-warning heuristic: temperature
    above 30 °C, relative humidity below 30%, wind above 30 — conditions
    considered extreme for fire spread.

    The published Chilean definition uses **30 km/h**. Some services state
    the wind limit in knots instead, which is nearly double (30 kt =
    55.6 km/h) and trips far less often, so the unit is configurable rather
    than assumed. Defaults follow the documented standard.

    It is a heuristic, not a physical model — academics have criticised it as
    insufficient for the severity Chile now sees. PANAL shows it because it is
    what the services actually act on; Cell2Fire + Kitral is the physics.
    """

    temp_c: float = 30.0
    rh_pct: float = 30.0
    wind: float = 30.0
    wind_unit: str = "kmh"  # "kmh" or "knots"

    def wind_ms(self) -> float:
        return self.wind / (MS_TO_KNOTS if self.wind_unit == "knots" else MS_TO_KMH)

    def evaluate(self, t2m, rh2m, ws10m) -> dict:
        """Which of the three legs are met, and whether all three are."""
        if t2m is None or rh2m is None or ws10m is None:
            return {"temp": None, "rh": None, "wind": None, "all": None}
        legs = {
            "temp": t2m >= self.temp_c,
            "rh": rh2m <= self.rh_pct,
            "wind": ws10m >= self.wind_ms(),
        }
        legs["all"] = all(legs.values())
        legs["met"] = sum(1 for k in ("temp", "rh", "wind") if legs[k])
        return legs


def fetch_hourly(lat: float, lon: float, start: dt.date, end: dt.date,
                 parameters=PARAMETERS) -> dict:
    """Hourly weather for one point, keyed by 'YYYYMMDDHH' in UTC."""
    import tempfile
    from pathlib import Path

    url = BASE + "?" + urlencode({
        "parameters": ",".join(parameters),
        "community": "RE",
        "latitude": lat,
        "longitude": lon,
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
        "time-standard": "UTC",
    })

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        path = goes.download(url, tmp.name)
    try:
        raw = json.loads(Path(path).read_text())
    finally:
        Path(path).unlink(missing_ok=True)

    series = raw.get("properties", {}).get("parameter", {})
    if not series:
        raise RuntimeError(f"POWER returned no parameters: {str(raw)[:200]}")

    # POWER marks missing values with -999.
    out: dict[str, dict] = {}
    for name, by_hour in series.items():
        for stamp, value in by_hour.items():
            out.setdefault(stamp, {})[name] = None if value <= -998 else value
    return out


def at(hourly: dict, when: dt.datetime) -> dict:
    """The weather record covering a UTC instant, with derived units.

    POWER is hourly and PANAL's fire frames are every 10 minutes, so a frame
    takes the value of the hour containing it. Stepped rather than
    interpolated, because inventing intermediate values would imply a
    temporal precision the reanalysis does not have.
    """
    rec = hourly.get(when.strftime("%Y%m%d%H"))
    if not rec:
        return {}
    ws = rec.get("WS10M")
    return {
        "t2m": rec.get("T2M"),
        "rh2m": rec.get("RH2M"),
        "ws_ms": ws,
        "ws_kmh": None if ws is None else round(ws * MS_TO_KMH, 1),
        "ws_knots": None if ws is None else round(ws * MS_TO_KNOTS, 1),
        "wd": rec.get("WD10M"),
    }
