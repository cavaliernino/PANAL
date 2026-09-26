"""Egress decides whether a neighbourhood is called a trap.

The property that matters most is negative: an unmapped cell must never
score as well-connected. OSM is volunteered and thinnest exactly where the
danger is highest — the passages of informal hillside settlements.
"""

import pytest

from panal_ingest import egress


def test_unmapped_is_unknown_not_good():
    """The worst possible failure mode would be scoring an unmapped toma as
    having good egress."""
    assert egress.egress_deficit(None) is None
    assert egress.egress_deficit({}) is None


def test_connected_grid_scores_low():
    grid = dict(link_node_ratio=1.5, dead_ends=0, nodes=40, road_rank=6)
    assert egress.egress_deficit(grid) < 0.1


def test_dead_end_hillside_scores_high():
    """The geometry people died in."""
    trap = dict(link_node_ratio=0.95, dead_ends=8, nodes=30, road_rank=3)
    assert egress.egress_deficit(trap) > 0.55


def test_single_access_is_worse_than_dead_ends_alone():
    dead = dict(link_node_ratio=0.95, dead_ends=8, nodes=30, road_rank=3)
    single = dict(link_node_ratio=0.90, dead_ends=10, nodes=25, road_rank=2)
    assert egress.egress_deficit(single) > egress.egress_deficit(dead)


def test_deficit_is_monotonic_in_connectivity():
    def d(lnr):
        return egress.egress_deficit(
            dict(link_node_ratio=lnr, dead_ends=2, nodes=30, road_rank=3))
    vals = [d(x) for x in (1.6, 1.4, 1.2, 1.0, 0.8)]
    assert vals == sorted(vals)


def test_road_class_matters_independently():
    """A neighbourhood whose only link is a service lane is worse off than
    the same layout on a secondary."""
    lane = dict(link_node_ratio=1.2, dead_ends=2, nodes=30, road_rank=2)
    road = dict(link_node_ratio=1.2, dead_ends=2, nodes=30, road_rank=6)
    assert egress.egress_deficit(lane) > egress.egress_deficit(road)


def test_deficit_is_bounded():
    worst = dict(link_node_ratio=0.0, dead_ends=99, nodes=1, road_rank=0)
    best = dict(link_node_ratio=5.0, dead_ends=0, nodes=99, road_rank=9)
    assert egress.egress_deficit(worst) == pytest.approx(1.0)
    assert egress.egress_deficit(best) == 0.0


def test_footways_are_not_egress():
    """An evacuation on foot up a burning ravine is not egress, so paths are
    excluded from the drivable graph."""
    assert "footway" not in egress.DRIVABLE
    assert "path" not in egress.DRIVABLE
    assert "steps" not in egress.DRIVABLE
    assert "residential" in egress.DRIVABLE
    assert "track" in egress.DRIVABLE


def test_coverage_check_counts_the_gap():
    stats = {"a": {}, "b": {}}
    got = egress.coverage_check(["a", "b", "c", "d"], stats)
    assert got["inhabited_cells"] == 4
    assert got["with_roads"] == 2
    assert got["without_roads"] == 2
    assert got["coverage"] == 0.5


def test_road_rank_orders_by_evacuation_capacity():
    assert egress.ROAD_RANK["motorway"] > egress.ROAD_RANK["primary"]
    assert egress.ROAD_RANK["primary"] > egress.ROAD_RANK["residential"]
    assert egress.ROAD_RANK["residential"] > egress.ROAD_RANK["track"]
