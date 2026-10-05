"""Fuel is the term the hazard half stands on: without it the index scored
worse than chance. These tests pin down which scenes get read, because a
search that quietly returned the wrong ones cost a whole region its fuel."""

import json

import pytest

from panal_ingest import fuel


def _scene(id_, cloud, bbox, tile=None):
    props = {"eo:cloud_cover": cloud}
    if tile:
        props["grid:code"] = tile
    return {"id": id_, "bbox": bbox, "properties": props}


def test_select_keeps_the_least_cloudy_per_tile():
    """One clear tile must not take every slot while its neighbour gets none."""
    a = [_scene(f"S2A_19HCD_2026030{k}_0_L2A", k, [-72, -34, -71, -33]) for k in range(6)]
    b = [_scene(f"S2A_19HBD_2026030{k}_0_L2A", 10 + k, [-71, -34, -70, -33]) for k in range(6)]
    got = fuel.select(a + b, lats=[-33.5, -33.5], lons=[-71.5, -70.5], per_tile=2)
    ids = [f["id"] for f in got]
    assert ids == ["S2A_19HCD_20260300_0_L2A", "S2A_19HCD_20260301_0_L2A",
                   "S2A_19HBD_20260300_0_L2A", "S2A_19HBD_20260301_0_L2A"]


def test_select_never_reads_a_scene_with_no_cell_in_it():
    """A regional bbox returns mostly scenes over nothing that matters —
    Valparaíso's reaches Rapa Nui. Reading them only spends the budget."""
    ocean = _scene("S2A_12JUN_20260301_0_L2A", 0, [-110, -28, -109, -27])
    land = _scene("S2A_19HCD_20260301_0_L2A", 15, [-72, -34, -71, -33])
    got = fuel.select([ocean, land], lats=[-33.5], lons=[-71.5])
    assert [f["id"] for f in got] == [land["id"]]


def test_select_drops_duplicates_across_searches():
    """Searches run per 1° box, so a scene over two boxes arrives twice."""
    s = _scene("S2A_19HCD_20260301_0_L2A", 5, [-72, -34, -70, -33])
    assert len(fuel.select([s, s], lats=[-33.5], lons=[-71.5])) == 1


class _Pages:
    """Stands in for the STAC endpoint: newest first, a page at a time."""

    def __init__(self, pages):
        self.pages, self.bodies = pages, []

    def __call__(self, req, timeout=None):
        body = json.loads(req.data)
        self.bodies.append(body)
        i = body.get("next", 0)
        page = {"features": self.pages[i], "links": []}
        if i + 1 < len(self.pages):
            page["links"].append({"rel": "next", "method": "POST",
                                  "body": {**body, "next": i + 1}})
        return _Resp(page)


class _Resp:
    def __init__(self, data):
        self.data = json.dumps(data).encode()

    def read(self, *a):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_search_reads_every_page(monkeypatch):
    """The first version read one page of 40 and took it for the window:
    a February-March request came back as 18-30 March."""
    pages = [[_scene(f"late{k}", 5, [0, 0, 1, 1]) for k in range(3)],
             [_scene(f"early{k}", 1, [0, 0, 1, 1]) for k in range(2)]]
    endpoint = _Pages(pages)
    monkeypatch.setattr(fuel, "urlopen", endpoint)
    got = fuel.search((0, 0, 1, 1), 2026)
    assert len(got) == 5 and len(endpoint.bodies) == 2
    assert got[0]["id"].startswith("early"), "least cloudy first"


def test_a_window_across_new_year_starts_the_year_before(monkeypatch):
    """Fuel before a mid-January fire is December and January."""
    endpoint = _Pages([[]])
    monkeypatch.setattr(fuel, "urlopen", endpoint)
    fuel.search((0, 0, 1, 1), 2026, window=("12-01", "01-13"))
    assert endpoint.bodies[0]["datetime"] == "2025-12-01T00:00:00Z/2026-01-13T23:59:59Z"


@pytest.mark.parametrize("ndvi,ndmi,expect", [
    (0.05, -0.3, 0.0),      # bare ground does not burn, however dry
    (0.70, 0.40, 0.0),      # irrigated green does not carry fire
    (0.70, -0.20, 1.0),     # full cover, cured: the dangerous quadrant
])
def test_fuel_factor_needs_biomass_and_dryness(ndvi, ndmi, expect):
    assert fuel.fuel_factor(ndvi, ndmi) == pytest.approx(expect)


# The pre-registered fuel-type rules (docs/preregistro-combustible.md).

TREES = {"arboles": 1.0}
SCRUB = {"matorral": 1.0}
CAMP = {"construido": 1.0}


def test_r1_does_not_punish_a_green_canopy_for_being_green():
    """Plantations burn in a heat wave whatever NDMI says."""
    canopy = (0.75, 0.30)                    # dense, moist-reading
    assert fuel.fuel_factor(*canopy) < 0.2
    assert fuel.fuel_by_type(*canopy, TREES) == pytest.approx(1.0)


def test_r1_leaves_scrub_as_it_was():
    """Where the index already worked, the rule must change nothing."""
    for ndvi, ndmi in [(0.4, -0.05), (0.6, 0.1), (0.2, 0.3)]:
        assert fuel.fuel_by_type(ndvi, ndmi, SCRUB) == pytest.approx(
            fuel.fuel_factor(ndvi, ndmi))


def test_built_up_carries_no_fuel_unless_r2_and_precarious():
    assert fuel.fuel_by_type(0.5, 0.0, CAMP) == 0.0
    assert fuel.fuel_by_type(0.5, 0.0, CAMP, frac_precario=0.0, rule="R2") == 0.0
    assert fuel.fuel_by_type(0.5, 0.0, CAMP, frac_precario=0.6, rule="R2") == pytest.approx(0.6)


def test_missing_land_cover_is_unknown_not_low():
    import math
    assert math.isnan(fuel.fuel_by_type(0.5, 0.0, None))


def test_only_pre_registered_rules_exist():
    with pytest.raises(ValueError):
        fuel.fuel_by_type(0.5, 0.0, SCRUB, rule="R3")
