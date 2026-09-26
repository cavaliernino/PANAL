"""The exposure index decides which neighbourhoods get named as dangerous.

Two questions are kept apart here, and the tests enforce that separation:
hazard (will fire reach and run) has been validated against the February
2024 Viña fire; consequence (how bad if it does) has not.
"""

import pytest

from panal_engine import wui


# ── the gate ────────────────────────────────────────────────────────────

def test_landscape_is_not_interface():
    """A cell with nobody in it scores zero however dangerous it looks."""
    s = wui.score_cell(dwellings=0, slope_factor=1.0, fuel_factor=1.0)
    assert s["wui"] == 0.0
    assert s["inhabited"] is False


def test_the_gate_is_presence_not_magnitude():
    """The largest error in the first version.

    Weighting by dwelling count pushes the index toward dense urban cores,
    and the interface is by definition where settlement is sparse: measured
    over Valparaíso, interface cells had a 90th-percentile dwelling count of
    8 against 36 for the region. Five households against cured matorral on a
    slope are in real danger; five hundred in a flat core are not.
    """
    few = wui.score_cell(dwellings=3, slope_factor=0.8, fuel_factor=0.8)
    many = wui.score_cell(dwellings=500, slope_factor=0.8, fuel_factor=0.8)
    assert few["wui"] == many["wui"]


def test_single_dwelling_counts():
    assert wui.present(1) == 1.0
    assert wui.present(0.4) == 0.0
    assert wui.present(None) == 0.0


# ── hazard ──────────────────────────────────────────────────────────────

def test_fuel_and_slope_compound():
    """Bare steep ground does not burn; heavy fuel on the flat does not run."""
    steep_bare, _ = wui.hazard_of(1.0, 0.04)
    flat_heavy, _ = wui.hazard_of(0.04, 1.0)
    both, _ = wui.hazard_of(0.6, 0.6)
    assert both > steep_bare
    assert both > flat_heavy


def test_unobserved_fuel_is_not_low_fuel():
    """A cell with no Sentinel-2 observation is unknown, not safe.

    Slope alone scored 0.00x lift against the 2024 fire, so ranking on it
    injects noise: 576 such cells reached the index's top decile and none
    were near the fire. Excluding them took lift from 3.39x to 3.83x.
    """
    hazard, has_fuel = wui.hazard_of(0.9, None)
    assert hazard is None
    assert has_fuel is False
    assert wui.score_cell(dwellings=10, slope_factor=0.9)["wui"] is None


def test_nan_fuel_is_treated_as_unobserved():
    assert wui.hazard_of(0.9, float("nan"))[0] is None


def test_hazard_has_no_free_parameters():
    """Deliberate: the sample is 115 cells from one event, so knobs here
    would invite fitting to it."""
    import inspect
    sig = inspect.signature(wui.hazard_of)
    assert list(sig.parameters) == ["slope_factor", "fuel_factor"]


# ── consequence ─────────────────────────────────────────────────────────

def test_consequence_is_reported_not_multiplied_in():
    """Precarious housing with no hydrants is genuinely worse off when fire
    arrives — but that says nothing about whether fire arrives, and folding
    it in scored worse than chance."""
    bad = wui.score_cell(dwellings=10, slope_factor=0.5, fuel_factor=0.5,
                         frac_precario=1.0, frac_vulnerable=1.0,
                         frac_sin_red_agua=1.0)
    good = wui.score_cell(dwellings=10, slope_factor=0.5, fuel_factor=0.5)
    assert bad["wui"] == good["wui"]
    assert bad["consequence"] > good["consequence"]


def test_consequence_scales_with_households():
    small = wui.consequence_of(dwellings=5, frac_precario=1.0,
                               frac_vulnerable=0, frac_sin_red_agua=0)
    large = wui.consequence_of(dwellings=200, frac_precario=1.0,
                               frac_vulnerable=0, frac_sin_red_agua=0)
    assert large["consequence"] > small["consequence"]
    assert large["scale"] == pytest.approx(1.0)


def test_consequence_weights_normalise():
    w = wui.Weights(precarious=2, vulnerable=2, no_water=1).normalised()
    assert w.precarious + w.vulnerable + w.no_water == pytest.approx(1.0)


# ── robustness ──────────────────────────────────────────────────────────

def test_out_of_range_inputs_are_clamped():
    s = wui.score_cell(dwellings=10, slope_factor=5.0, fuel_factor=-3.0,
                       frac_precario=9.0, frac_vulnerable=-1.0,
                       frac_sin_red_agua=4.0)
    assert 0.0 <= s["wui"] <= 1.0
    assert 0.0 <= s["consequence"] <= 1.0


def test_all_none_does_not_crash():
    s = wui.score_cell(dwellings=None, slope_factor=None)
    assert s["wui"] is None
    assert s["consequence"] == 0.0


def test_score_is_bounded_at_one():
    s = wui.score_cell(dwellings=10, slope_factor=1, fuel_factor=1)
    assert s["wui"] == pytest.approx(1.0)
