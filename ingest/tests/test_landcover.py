"""Land-cover fractions per cell, the input to the pre-registered fuel-type
rules. The class codes are categories, so nothing here may average them."""

import numpy as np
import pytest

from panal_ingest import landcover

h3 = pytest.importorskip("h3")


def test_tile_names_are_three_degree_south_west_corners():
    assert landcover.tile_name(-33.02, -71.55).endswith("_S36W072_Map")
    assert landcover.tile_name(-32.99, -71.55).endswith("_S33W072_Map")
    assert landcover.tile_name(-36.8, -72.9).endswith("_S39W075_Map")


def _raster(cell, fill):
    """A 40 m raster around a cell, filled by a function of (lat, lon)."""
    from rasterio.transform import from_origin

    lat, lon = h3.cell_to_latlng(cell)
    px = 40 / 111_320
    n = 40
    west, north = lon - n / 2 * px, lat + n / 2 * px
    t = from_origin(west, north, px, px)
    arr = np.zeros((n, n), dtype="uint8")
    for r in range(n):
        for c in range(n):
            x, y = t @ (c + 0.5, r + 0.5)
            arr[r, c] = fill(y, x)
    return arr, t


def test_fractions_count_only_pixels_inside_the_cell():
    cell = h3.latlng_to_cell(-33.05, -71.55, 9)
    lat0, _ = h3.cell_to_latlng(cell)
    # Trees north of the cell's centre, built-up south; scrub outside it.
    def fill(y, x):
        if h3.latlng_to_cell(y, x, 9) != cell:
            return 20
        return 10 if y > lat0 else 50
    arr, t = _raster(cell, fill)
    f = landcover.fractions_in(arr, t, cell)
    assert f["matorral"] == 0.0, "pixels outside the hexagon must not count"
    assert f["arboles"] + f["construido"] == pytest.approx(1.0)
    assert 0.35 < f["arboles"] < 0.65


def test_nodata_is_not_a_class():
    cell = h3.latlng_to_cell(-33.05, -71.55, 9)
    arr, t = _raster(cell, lambda y, x: 0)
    assert landcover.fractions_in(arr, t, cell) is None
