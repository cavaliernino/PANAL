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
    """A box spanning two latitude bands and three longitude bands needs six
    tiles. Getting this wrong silently drops terrain at a region edge."""
    tiles = terrain.tiles_for((-72.5, -33.5, -70.5, -32.5))
    assert terrain.tile_name(-34, -73) in tiles     # south-west corner
    assert terrain.tile_name(-33, -71) in tiles     # north-east corner
    assert len(tiles) == 6


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


def test_smoothing_suppresses_urban_texture_more_than_terrain():
    """The measured artefact, as a test.

    Dense urban fabric at 30 m is high-frequency texture, not a few isolated
    blocks — many overlapping roof edges within one cell. That distinction
    matters: smoothing an *isolated* step spreads it into a ramp and raises
    the mean, which is the opposite of what happens on real urban DSM. Noise
    on a plane is the faithful model, and it reproduces the field
    measurement (Santiago 7.3° → 3.6°, hillside 20.7° → 18.4°).
    """
    rng = np.random.default_rng(7)
    noise = rng.normal(0, 8, (24, 24)).astype("float32")
    urban = np.full((24, 24), 500.0, dtype="float32") + noise
    hill = np.repeat(np.arange(24, dtype="float32")[:, None] * 10.0, 24, axis=1)

    u_raw = terrain.slope_degrees(urban, -33, smooth=False).mean()
    u_sm = terrain.slope_degrees(urban, -33, smooth=True).mean()
    h_raw = terrain.slope_degrees(hill, -33, smooth=False).mean()
    h_sm = terrain.slope_degrees(hill, -33, smooth=True).mean()

    assert u_sm < u_raw * 0.4, "smoothing must cut urban texture hard"
    assert h_sm == pytest.approx(h_raw, rel=0.02), "real terrain must survive"


def test_smoothing_recovers_true_slope_under_noise():
    """A real hillside seen through urban texture should smooth back toward
    its actual gradient, not away from it."""
    rng = np.random.default_rng(7)
    hill = np.repeat(np.arange(24, dtype="float32")[:, None] * 10.0, 24, axis=1)
    noisy = hill + rng.normal(0, 8, (24, 24)).astype("float32")

    truth = terrain.slope_degrees(hill, -33, smooth=False).mean()
    raw = terrain.slope_degrees(noisy, -33, smooth=False).mean()
    sm = terrain.slope_degrees(noisy, -33, smooth=True).mean()

    assert abs(sm - truth) < abs(raw - truth)


def _write_tile(path, west, north, cols, rows, value):
    """A flat GeoTIFF at GLO-30's 1 arc-second, with no nodata — like GLO-30."""
    import rasterio
    from rasterio.transform import from_origin

    px = 1 / 3600
    with rasterio.open(path, "w", driver="GTiff", width=cols, height=rows,
                       count=1, dtype="float32", crs="EPSG:4326",
                       transform=from_origin(west, north, px, px)) as dst:
        dst.write(np.full((rows, cols), value, dtype="float32"), 1)


def test_a_cell_on_a_tile_edge_reads_both_tiles(tmp_path, monkeypatch):
    """Flat ground at 500 m on both sides of the -33° parallel must stay flat.

    Read from one tile with the rest filled in, the half of the cell beyond
    the edge came back at 0 m — a 500 m cliff that does not exist. The -33°
    line runs through Reñaca and Viña, so this was inflating slope in exactly
    the hills the exposure map is about.
    """
    h3 = pytest.importorskip("h3")
    pytest.importorskip("rasterio")

    cell = next(
        c for c in h3.grid_disk(h3.latlng_to_cell(-33.0, -71.55, 9), 3)
        if min(p[0] for p in h3.cell_to_boundary(c)) < -33.0
        < max(p[0] for p in h3.cell_to_boundary(c)))

    tiles = {
        terrain.tile_name(-34, -72): tmp_path / "south.tif",
        terrain.tile_name(-33, -72): tmp_path / "north.tif",
    }
    # 0.1° of longitude, 0.03° either side of the edge: enough for one cell.
    _write_tile(tiles[terrain.tile_name(-34, -72)], -71.6, -33.0, 360, 108, 500)
    _write_tile(tiles[terrain.tile_name(-33, -72)], -71.6, -32.97, 360, 108, 500)
    monkeypatch.setattr(terrain, "fetch_tile", lambda name: tiles.get(name))

    got = terrain.cells_terrain([cell])[cell]
    assert got["relief_m"] == pytest.approx(0, abs=0.5)
    assert got["slope_deg"] == pytest.approx(0, abs=0.1)
    assert got["elev_m"] == pytest.approx(500, abs=0.5)


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
