"""Census aggregation decides who the exposure map says is at risk.

The rules worth pinning: nobody is dropped, resolution follows density, and
the derived shares behave at the edges.
"""

import numpy as np
import pandas as pd
import pytest

from panal_ingest import census


def test_res_for_block_keeps_dense_blocks_fine():
    """A city block with 80 dwellings in 0.02 km² stays at the asked-for
    resolution."""
    assert census.res_for_block(0.02, 80, 9) == 9


def test_res_for_block_coarsens_sparse_rural():
    """A rural entity of 50 dwellings over 40 km² cannot support r9.

    Spreading it there gives fractions of a dwelling per cell, which is both
    false and useless. It must step out until density is meaningful.
    """
    r = census.res_for_block(40.0, 50, 9)
    assert r < 9
    import h3
    cells = 40.0 / h3.average_hexagon_area(r, unit="km^2")
    assert 50 / max(cells, 1) >= census.MIN_DWELLINGS


def test_res_for_block_never_exceeds_request():
    assert census.res_for_block(0.0001, 10_000, 7) == 7


def test_res_for_block_handles_empty():
    assert census.res_for_block(10.0, 0, 9) == 9
    assert census.res_for_block(0.0, 5, 9) == 9


def test_diagonal_matches_known_distance():
    """One degree of latitude is about 110.5 km."""
    d = census._diagonal_m(np.array([-71.0]), np.array([-33.0]),
                           np.array([-71.0]), np.array([-32.0]))
    assert d[0] == pytest.approx(110_540, rel=0.01)


def test_diagonal_shrinks_with_latitude():
    """A degree of longitude is narrower far south."""
    north = census._diagonal_m(np.array([-71.0]), np.array([-20.0]),
                               np.array([-70.0]), np.array([-20.0]))[0]
    south = census._diagonal_m(np.array([-71.0]), np.array([-53.0]),
                               np.array([-70.0]), np.array([-53.0]))[0]
    assert south < north * 0.7


def _frame(**over):
    base = {v: [0.0] for v in census.VARIABLES}
    base.update({"n_per": [100.0], "n_vp": [30.0]})
    base.update({k: [v] for k, v in over.items()})
    return pd.DataFrame(base)


def test_vulnerable_share_counts_who_needs_help():
    df = census.exposure_terms(_frame(n_edad_0_5=10, n_edad_60_mas=20,
                                      n_dificultad_mover=5))
    assert df.loc[0, "frac_vulnerable"] == pytest.approx(0.35)


def test_shares_are_clipped_to_one():
    """Overlapping categories can exceed the denominator; a share cannot."""
    df = census.exposure_terms(_frame(n_edad_0_5=60, n_edad_60_mas=60,
                                      n_dificultad_mover=40))
    assert df.loc[0, "frac_vulnerable"] == 1.0


def test_no_mains_water_is_the_inverse_of_coverage():
    """The term a firefighter reads first: no network means no hydrants."""
    full = census.exposure_terms(_frame(n_fuente_agua_publica=30))
    none = census.exposure_terms(_frame(n_fuente_agua_publica=0))
    assert full.loc[0, "frac_sin_red_agua"] == 0.0
    assert none.loc[0, "frac_sin_red_agua"] == 1.0


def test_empty_cell_does_not_divide_by_zero():
    df = census.exposure_terms(_frame(n_per=0, n_vp=0))
    for col in ("frac_vulnerable", "frac_precario", "frac_ignicion",
                "frac_sin_red_agua"):
        assert df.loc[0, col] == 0.0


def test_curated_variables_are_all_real_columns():
    """Guards against a typo silently zeroing a term."""
    import pyarrow.parquet as pq

    path = census.CACHE / census.FILES["manzanas"]
    if not path.exists():
        pytest.skip("censo cartography not downloaded")
    have = {f.name for f in pq.ParquetFile(path).schema_arrow}
    missing = [v for v in census.VARIABLES if v not in have]
    assert not missing, f"not in the census file: {missing}"
