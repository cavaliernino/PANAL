"""The live GOES layer is the last hour, not the last scan.

A fire hidden by its own smoke for one scan used to vanish from the map,
leaving the same empty hexagon as no fire. These pin down how an hour of
scans becomes one layer.
"""

import datetime as dt

from panal_ingest import pipeline

NOW = dt.datetime(2026, 1, 18, 5, 21, tzinfo=dt.timezone.utc)


def _end(minutes_ago):
    return NOW - dt.timedelta(minutes=minutes_ago)


def _cell(h, f):
    return {"h": h, "n": 1, "f": f, "c": "good"}


def test_the_newest_scan_wins():
    got = pipeline.merge_recent([
        (_end(31), {"7": [_cell("a", 10.0)]}),
        (_end(1), {"7": [_cell("a", 90.0)]}),
    ], NOW)["7"]
    assert got == [{"h": "a", "n": 1, "f": 90.0, "c": "good",
                    "age": 1, "k": 2, "l": 1}]


def test_a_cell_the_newest_scan_missed_stays_and_says_so():
    """Smoke over the fire for one scan is not the fire going out."""
    got = {c["h"]: c for c in pipeline.merge_recent([
        (_end(21), {"7": [_cell("a", 50.0), _cell("b", 5.0)]}),
        (_end(11), {"7": [_cell("a", 60.0)]}),
        (_end(1), {"7": [_cell("b", 7.0)]}),
    ], NOW)["7"]}
    assert got["a"]["l"] == 0 and got["a"]["age"] == 11 and got["a"]["k"] == 2
    assert got["b"]["l"] == 1 and got["b"]["age"] == 1 and got["b"]["k"] == 2


def test_order_of_arrival_does_not_matter():
    scans = [(_end(1), {"7": [_cell("a", 2.0)]}),
             (_end(41), {"7": [_cell("a", 1.0)]})]
    assert (pipeline.merge_recent(scans, NOW)
            == pipeline.merge_recent(scans[::-1], NOW))


def test_levels_merge_independently():
    got = pipeline.merge_recent([
        (_end(11), {"7": [_cell("a", 1.0)], "6": [_cell("A", 1.0)]}),
        (_end(1), {"7": [], "6": []}),
    ], NOW)
    assert [c["h"] for c in got["7"]] == ["a"]
    assert [c["h"] for c in got["6"]] == ["A"]
    assert got["7"][0]["l"] == 0


def test_nothing_in_the_hour_is_empty_not_missing():
    got = pipeline.merge_recent([(_end(1), {"7": [], "6": [], "5": []})], NOW)
    assert got == {"7": [], "6": [], "5": []}
