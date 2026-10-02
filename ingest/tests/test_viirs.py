"""The continental feed is cut down while parsing. That cut must lose nothing."""

import pandas as pd

from panal_ingest import chile, viirs

HEADER = ("latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,"
          "satellite,instrument,confidence,version,bright_ti5,frp,daynight\n")


def _row(lat, lon, frp=5.0):
    return (f"{lat},{lon},330.0,0.4,0.4,2026-01-15,1830,N20,VIIRS,n,2.0NRT,"
            f"290.0,{frp},D\n")


POINTS = {
    "valparaiso": (-33.05, -71.60),
    "rapa_nui": (-27.12, -109.35),     # the far corner of the bbox
    "mato_grosso": (-12.60, -55.70),   # where the Amazon season actually is
    "mendoza": (-32.89, -68.83),       # inside the bbox, outside Chile
}
TEXT = HEADER + "".join(_row(lat, lon) for lat, lon in POINTS.values())


def test_bbox_cut_keeps_everything_clip_would_keep():
    whole = chile.clip(viirs._parse(TEXT, "viirs", "t"))
    cut = chile.clip(viirs._parse(TEXT, "viirs", "t", bbox=chile.BBOX))
    pd.testing.assert_frame_equal(whole.reset_index(drop=True),
                                  cut.reset_index(drop=True))
    assert len(cut) == 2                   # Valparaíso and Rapa Nui


def test_bbox_cut_drops_the_continent_early():
    df = viirs._parse(TEXT, "viirs", "t", bbox=chile.BBOX)
    assert len(df) == 3                    # Mendoza survives; clip removes it


def test_nothing_in_chile_is_an_empty_frame_with_columns():
    df = viirs._parse(HEADER + _row(-12.6, -55.7), "viirs", "t",
                      bbox=chile.BBOX)
    assert len(df) == 0
    assert {"lat", "lon", "acq"} <= set(df.columns)
