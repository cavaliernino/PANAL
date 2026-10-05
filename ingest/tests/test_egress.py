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
    assert got["cells"] == 4
    assert got["cells_with_roads"] == 2
    assert got["cell_coverage"] == 0.5


def test_coverage_must_be_weighted_by_people():
    """Cell coverage alone is misleading and was, badly.

    Over Valparaíso the raw figure is 44.2% and the population-weighted one
    is 95.7%, because the unmapped cells are nearly empty: 24,601 of them
    hold 79,945 people against 1,786,955 in the mapped ones.
    """
    stats = {"dense": {}}
    dwellings = {"dense": 156.0, "empty1": 1.0, "empty2": 1.0, "empty3": 1.0}
    got = egress.coverage_check(list(dwellings), stats, dwellings=dwellings)
    assert got["cell_coverage"] == 0.25
    assert got["dwelling_coverage"] > 0.97


def _osm(path, nodes, ways):
    """A minimal .osm file: nodes as {id: (lat, lon)}, ways as [[ids]]."""
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<osm version="0.6">']
    for i, (lat, lon) in nodes.items():
        xml.append(f'<node id="{i}" version="1" lat="{lat:.7f}" lon="{lon:.7f}"/>')
    for k, refs in enumerate(ways, 1):
        xml.append(f'<way id="{k}" version="1">')
        xml += [f'<nd ref="{r}"/>' for r in refs]
        xml += ['<tag k="highway" v="residential"/>', "</way>"]
    xml.append("</osm>")
    path.write_text("\n".join(xml))
    return path


def test_drawing_a_curve_does_not_change_connectivity(tmp_path):
    """The same T-junction, with the side street drawn straight or as a
    curve of eight shape vertices, is the same network.

    Counting shape vertices as nodes put 72% of Valparaíso's nodes on curves,
    pulled the ratio toward 1.0 everywhere and made curvy hillside streets
    look as if they had fewer dead ends than flat ones.
    """
    h3 = pytest.importorskip("h3")
    pytest.importorskip("osmium")
    lat0, lon0 = h3.cell_to_latlng(h3.latlng_to_cell(-33.045, -71.62, 9))
    d = 0.0003                              # ~33 m: all in one r9 cell

    def at(dy, dx):
        return (lat0 + dy * d, lon0 + dx * d)

    main = {1: at(0, -1), 2: at(0, 0), 3: at(0, 1)}
    straight = _osm(tmp_path / "straight.osm",
                    {**main, 4: at(1, 0)}, [[1, 2, 3], [2, 4]])
    curve = {10 + k: at(0.1 * (k + 1), 0.15 * ((-1) ** k)) for k in range(8)}
    curvy = _osm(tmp_path / "curvy.osm",
                 {**main, **curve, 4: at(1, 0)},
                 [[1, 2, 3], [2, *curve, 4]])

    a = egress.cells_egress(res=9, pbf=straight, progress=False)
    b = egress.cells_egress(res=9, pbf=curvy, progress=False)
    assert len(a) == len(b) == 1, "the fixture must sit in one cell"
    (sa,), (sb,) = a.values(), b.values()
    for key in ("nodes", "links", "dead_ends", "link_node_ratio"):
        assert sa[key] == sb[key], key
    # One junction of degree 3 and three street ends.
    assert sa["nodes"] == 4 and sa["dead_ends"] == 3


def test_a_cell_with_no_junction_has_unknown_connectivity():
    """A road crossing a cell with no junction inside says nothing about how
    connected that cell is. Its weight goes to what was measured."""
    through = dict(link_node_ratio=None, dead_ends=0, nodes=0, road_rank=3)
    got = egress.egress_deficit(through)
    assert got is not None
    assert got == pytest.approx(0.25 * 0.25 / 0.55, abs=1e-4)


def test_road_rank_orders_by_evacuation_capacity():
    assert egress.ROAD_RANK["motorway"] > egress.ROAD_RANK["primary"]
    assert egress.ROAD_RANK["primary"] > egress.ROAD_RANK["residential"]
    assert egress.ROAD_RANK["residential"] > egress.ROAD_RANK["track"]
