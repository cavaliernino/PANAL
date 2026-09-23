"""The mask decides what a human never sees. Its rule needs pinning down."""

import datetime as dt

import pandas as pd
import pytest

from panal_ingest import anomaly


def _dets(cell, days, start=dt.datetime(2025, 7, 1, tzinfo=dt.timezone.utc),
          step_days=1, frp=3.0):
    """`days` detections in one cell, one per day from `start`."""
    return pd.DataFrame({
        "h3": [cell] * days,
        "acq": [start + dt.timedelta(days=i * step_days) for i in range(days)],
        "frp_mw": [frp] * days,
    })


def test_smelter_is_flagged():
    """Many days, many months, deep into the off-season: no fire does this."""
    df = _dets("smelter", days=120, step_days=3)     # ~12 months of coverage
    out = anomaly.summarise(df)
    assert out.loc[0, "industrial"]


def test_two_week_wildfire_is_not_flagged():
    """Even a long megafire is bounded: one place, a couple of weeks."""
    df = _dets("fire", days=16,
               start=dt.datetime(2026, 1, 10, tzinfo=dt.timezone.utc))
    out = anomaly.summarise(df)
    assert not out.loc[0, "industrial"]


def test_agricultural_burning_is_not_flagged():
    """The false positive that months-alone produced.

    Recurring burns in one field: spread across months and into the
    off-season, but never many days in the same cell. Masking these would
    suppress real fire in the central valley.
    """
    days = [dt.datetime(2025, m, d, tzinfo=dt.timezone.utc)
            for m in (4, 5, 9, 10, 11) for d in (5, 12)]
    df = pd.DataFrame({"h3": ["field"] * len(days), "acq": days,
                       "frp_mw": [4.0] * len(days)})
    out = anomaly.summarise(df)
    assert out.loc[0, "months"] >= anomaly.MIN_MONTHS
    assert out.loc[0, "offseason_days"] >= anomaly.MIN_OFFSEASON_DAYS
    assert out.loc[0, "days"] < anomaly.MIN_DAYS
    assert not out.loc[0, "industrial"], "days threshold must save this cell"


def test_summer_only_persistence_is_not_flagged():
    """Off-season evidence is required, not optional."""
    df = _dets("summer", days=40, step_days=2,
               start=dt.datetime(2025, 12, 1, tzinfo=dt.timezone.utc))
    out = anomaly.summarise(df)
    assert out.loc[0, "days"] >= anomaly.MIN_DAYS
    assert not out.loc[0, "industrial"]


def test_flag_marks_and_never_drops(tmp_path, monkeypatch):
    """A real fire can start at a mine. The mask must not delete."""
    monkeypatch.setattr(anomaly, "_cache",
                        {"meta": {}, "cells": {"smelter": {"d": 300}}})
    df = pd.DataFrame({"h3": ["smelter", "elsewhere"], "frp_mw": [3.0, 900.0]})
    out = anomaly.flag(df)
    assert len(out) == 2, "flagged rows must survive"
    assert list(out["industrial"]) == [True, False]


def test_empty_input():
    out = anomaly.summarise(pd.DataFrame(columns=["h3", "acq", "frp_mw"]))
    assert len(out) == 0
