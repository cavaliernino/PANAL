"""Band-wise extraction must give exactly what reading the whole disk gave.

It runs every ten minutes on a server that hosts other things, so it reads
the full disk in row bands instead of whole. The bands are an optimisation;
nothing about the output is allowed to depend on where they fall.
"""

import numpy as np
import pytest

from panal_ingest import goes

nc = pytest.importorskip("netCDF4")

N = 10                    # a 10x10 "disk"
# GOES-19 fixed grid, scan angles in radians — small, so every pixel hits Earth.
XY = np.linspace(-0.01, 0.01, N)


def _scan(path, mask, power, area=None):
    ds = nc.Dataset(path, "w")
    ds.createDimension("y", N)
    ds.createDimension("x", N)
    ds.time_coverage_start = "2026-01-15T18:00:20.4Z"
    ds.time_coverage_end = "2026-01-15T18:09:51.3Z"
    ds.createVariable("x", "f8", ("x",))[:] = XY
    ds.createVariable("y", "f8", ("y",))[:] = XY[::-1]
    proj = ds.createVariable("goes_imager_projection", "i4")
    proj.perspective_point_height = 35786023.0
    proj.semi_major_axis = 6378137.0
    proj.semi_minor_axis = 6356752.31414
    proj.longitude_of_projection_origin = -75.2

    m = ds.createVariable("Mask", "i2", ("y", "x"), fill_value=-99)
    m[:] = mask
    p = ds.createVariable("Power", "f4", ("y", "x"), fill_value=-1.0)
    p[:] = power
    if area is not None:
        # Packed like the real product: uint16 with a scale factor.
        a = ds.createVariable("Area", "u2", ("y", "x"), fill_value=65535)
        a.scale_factor = 60.98
        a.add_offset = 0.0
        a[:] = area              # unpacked values; netCDF4 packs on write
    ds.close()


def test_band_edges_do_not_change_the_result(tmp_path, monkeypatch):
    """Same detections, same values, same order, whatever the band size."""
    mask = np.full((N, N), 40, dtype=np.int16)        # 40: not a fire code
    mask[0, 9] = 10      # first row
    mask[3, 2] = 33      # last row of a 4-row band
    mask[4, 2] = 34      # first row of the next band
    mask[9, 0] = 14      # last row, short final band
    power = np.arange(N * N, dtype=np.float32).reshape(N, N)
    area = np.ma.masked_array(np.full((N, N), 7 * 60.98))
    area[4, 2] = np.ma.masked   # missing in the file: must come back as NaN
    path = str(tmp_path / "scan.nc")
    _scan(path, mask, power, area)

    results = []
    for band in (N, 4, 3, 1):
        monkeypatch.setattr(goes, "BAND_ROWS", band)
        results.append(goes.extract_detections(path))

    whole = results[0]
    assert list(whole["mask_code"]) == [10, 33, 34, 14]   # row-major, as before
    assert list(whole["frp_mw"]) == [9.0, 32.0, 42.0, 90.0]
    assert np.isnan(whole["area_m2"].iloc[2])
    assert whole["area_m2"].iloc[0] == pytest.approx(7 * 60.98)
    assert list(whole["temporally_filtered"]) == [False, True, True, False]
    assert list(whole["confidence"]) == [
        "good", "high_probability", "medium_probability", "medium_probability"]
    assert whole["temp_k"].isna().all()                 # variable absent

    for other in results[1:]:
        assert other.equals(whole)


def test_no_fire_is_an_empty_frame_not_an_error(tmp_path):
    """For eight months of the year this is the normal answer."""
    path = str(tmp_path / "scan.nc")
    _scan(path, np.full((N, N), 40, dtype=np.int16),
          np.zeros((N, N), dtype=np.float32))
    out = goes.extract_detections(path)
    assert len(out) == 0
    assert "frp_mw" in out.columns
