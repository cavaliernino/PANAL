"""The exposure index decides which neighbourhoods get named as dangerous.

Its defining property is negative: no houses, no score. Everything else is
weighting, and the weights are an unvalidated hypothesis — but the shape has
to be right regardless of where they land.
"""

import pytest

from panal_engine import wui


def test_landscape_is_not_interface():
    """The property the whole index exists to express.

    A steep, precarious-looking, waterless cell with nobody in it scores
    zero. It is landscape. It becomes wildland-urban interface only when
    someone builds there.
    """
    s = wui.score_cell(dwellings=0, slope_factor=1.0, frac_precario=1.0,
                       frac_vulnerable=1.0, frac_sin_red_agua=1.0)
    assert s["wui"] == 0.0


def test_the_same_place_with_houses_scores_high():
    s = wui.score_cell(dwellings=60, slope_factor=0.9, frac_precario=0.9,
                       frac_vulnerable=0.9, frac_sin_red_agua=1.0)
    assert s["wui"] > 0.85


def test_safe_neighbourhood_scores_low():
    """Same number of houses, flat, solid, on the mains."""
    s = wui.score_cell(dwellings=60, slope_factor=0.02, frac_precario=0.02,
                       frac_vulnerable=0.2, frac_sin_red_agua=0.0)
    assert s["wui"] < 0.1


def test_exposure_gate_is_concave():
    """1 to 10 dwellings must matter more than 200 to 400: the first is the
    difference between an outbuilding and a settlement."""
    low = wui.exposure_gate(10) - wui.exposure_gate(1)
    high = wui.exposure_gate(400) - wui.exposure_gate(200)
    assert low > high


def test_exposure_gate_saturates():
    assert wui.exposure_gate(50) == pytest.approx(1.0)
    assert wui.exposure_gate(5000) == 1.0
    assert wui.exposure_gate(0) == 0.0
    assert wui.exposure_gate(None) == 0.0


def test_fuel_and_slope_compound_rather_than_average():
    """Steep ground with nothing to burn is not dangerous, and neither is
    heavy fuel on the flat. Either one near zero must dominate."""
    steep_bare = wui.score_cell(dwellings=60, slope_factor=1.0,
                                frac_precario=0, frac_vulnerable=0,
                                frac_sin_red_agua=0, fuel_factor=0.05)
    flat_heavy = wui.score_cell(dwellings=60, slope_factor=0.05,
                                frac_precario=0, frac_vulnerable=0,
                                frac_sin_red_agua=0, fuel_factor=1.0)
    both = wui.score_cell(dwellings=60, slope_factor=0.6,
                          frac_precario=0, frac_vulnerable=0,
                          frac_sin_red_agua=0, fuel_factor=0.6)
    assert both["hazard"] > steep_bare["hazard"]
    assert both["hazard"] > flat_heavy["hazard"]


def test_missing_fuel_is_declared_not_assumed():
    """The largest gap in the current index must be visible in its output,
    not left for a reader to assume it was included."""
    without = wui.score_cell(dwellings=60, slope_factor=0.5, frac_precario=0,
                             frac_vulnerable=0, frac_sin_red_agua=0)
    with_fuel = wui.score_cell(dwellings=60, slope_factor=0.5, frac_precario=0,
                               frac_vulnerable=0, frac_sin_red_agua=0,
                               fuel_factor=0.5)
    assert without["has_fuel"] is False
    assert with_fuel["has_fuel"] is True


def test_no_mains_water_moves_the_score():
    """The term a firefighter reads first must actually matter."""
    dry = wui.score_cell(dwellings=60, slope_factor=0.3, frac_precario=0.3,
                         frac_vulnerable=0.3, frac_sin_red_agua=1.0)
    wet = wui.score_cell(dwellings=60, slope_factor=0.3, frac_precario=0.3,
                         frac_vulnerable=0.3, frac_sin_red_agua=0.0)
    assert dry["wui"] - wet["wui"] > 0.15


def test_inputs_out_of_range_are_clamped_not_trusted():
    s = wui.score_cell(dwellings=60, slope_factor=5.0, frac_precario=-2.0,
                       frac_vulnerable=1.4, frac_sin_red_agua=9.0)
    assert 0.0 <= s["wui"] <= 1.0
    for k in ("hazard", "fragility", "deficit", "exposure"):
        assert 0.0 <= s[k] <= 1.0


def test_none_inputs_do_not_crash():
    s = wui.score_cell(dwellings=None, slope_factor=None, frac_precario=None,
                       frac_vulnerable=None, frac_sin_red_agua=None)
    assert s["wui"] == 0.0


def test_weights_are_normalised():
    w = wui.Weights(hazard=2, fragility=2, deficit=1).normalised()
    assert w.hazard + w.fragility + w.deficit == pytest.approx(1.0)


def test_score_is_bounded_at_one():
    s = wui.score_cell(dwellings=100_000, slope_factor=1, frac_precario=1,
                       frac_vulnerable=1, frac_sin_red_agua=1,
                       fuel_factor=1.0)
    assert s["wui"] == pytest.approx(1.0)
