"""Slope is the first physical term in the exposure map, and the DEM lies in
a specific way: it includes buildings. These tests pin down both the geometry
and the mitigation."""

import math

import numpy as np
import pytest

from panal_ingest import terrain


def test_tile_naming():
    assert terrain.tile_name(-34, -72) == "Copernicus_DSM_COG_10_S34_00_W072_00_DEM"
    assert terrain.tile_name(-21, -70) == "Copernicus_DSM_COG_10_S21_00_W070_00_DEM"
    assert terrain.tile_name(0, 0) == "Copernicus_DSM_COG_10_N00_00_E000_00_DEM"


def test_tiles_for_box_covers_corners():
    tiles = terrain.tiles_for((-72.5, -33.5, -70.5, -32.5))
    assert terrain.tile_name(-34, -73) in tiles
    assert terrain.tile_name(-33, -71) in tiles
    assert len(tiles) == 4


def test_flat_ground_is_flat():
    flat = np.full((12, 12), 250.0, dtype="float32")
    assert terrain.slope_degrees(flat, -33).max() == pytest.approx(0, abs=1e-6)


def test_known_gradient_recovers_its_angle():
    """A 30 m rise per 30.87 m of northward run is 44.2 degrees."""
    rows = np.arange(12, dtype="float32")[:, None] * terrain.ARCSEC_M
    ramp = np.repeat(rows, 12, axis=1)
    got = terrain.slope_degrees(ramp, 0.0, smooth=False).mean()
    assert got == pytest.approx(45.0, abs=0.5)


def test_longitude_spacing_is_corrected_for_latitude():
    """East-west ground spacing shrinks with cos(lat).

    The same east-west elevation ramp must read as a steeper slope far south,
    because those pixels cover less ground. Ignoring this would understate
    Magallanes, which is where the terrain is roughest.
    """
    cols = np.arange(12, dtype="float32")[None, :] * 10.0
    ramp = np.repeat(cols, 12, axis=0)
    near_eq = terrain.slope_degrees(ramp, 0.0, smooth=False).mean()
    far_south = terrain.slope_degrees(ramp, -54.0, smooth=False).mean()
    assert far_south > near_eq
    assert math.cos(math.radians(54)) < 0.6


def test_smoothing_suppresses_building_edges_more_than_terrain():
    """The measured artefact, as a test.

    A flat plateau with block-shaped buildings on it must lose far more
    apparent slope to smoothing than a genuine constant hillside does.
    """
    urban = np.full((15, 15), 500.0, dtype="float32")
    urban[3:6, 3:6] = 530.0          # a building
    urban[9:12, 8:11] = 525.0        # another
    hill = np.repeat(np.arange(15, dtype="float32")[:, None] * 10.0, 15, axis=1)

    u_raw = terrain.slope_degrees(urban, -33, smooth=False).mean()
    u_sm = terrain.slope_degrees(urban, -33, smooth=True).mean()
    h_raw = terrain.slope_degrees(hill, -33, smooth=False).mean()
    h_sm = terrain.slope_degrees(hill, -33, smooth=True).mean()

    assert u_sm < u_raw * 0.75, "smoothing must cut the building artefact"
    assert h_sm > h_raw * 0.9, "smoothing must leave real terrain alone"


def test_slope_factor_is_monotonic_and_bounded():
    vals = [terrain.slope_factor(s) for s in range(0, 50, 5)]
    assert vals == sorted(vals)
    assert vals[0] == 0.0
    assert all(0.0 <= v <= 1.0 for v in vals)
    assert terrain.slope_factor(45) == 1.0


def test_slope_factor_is_convex_not_linear():
    """Rate of spread doubles per 10 degrees, so 20 must be worth much more
    than twice 10 — a linear term would badly understate a ravine wall."""
    assert terrain.slope_factor(20) > 2.5 * terrain.slope_factor(10)


def test_slope_factor_handles_missing():
    assert terrain.slope_factor(None) == 0.0
    assert terrain.slope_factor(-5) == 0.0
