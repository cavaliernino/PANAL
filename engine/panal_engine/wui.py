"""Wildland-urban interface exposure.

Answers one question: **which neighbourhoods are built in the condition that
turns a small fire into a catastrophe?**

Not where fire is likely — that is the detection stack's job, and burn
probability is Phase 4. This is the standing condition of the built
environment, which does not change between seasons and is therefore
actionable months ahead, for defensible space, fuel breaks and evacuation
planning.

The defining property: **the score is zero where nobody lives.** A steep,
vegetated ravine with no houses is landscape. It becomes wildland-urban
interface only when someone builds there.

## Two questions, kept apart

An earlier version folded these together and the combination scored worse
than chance. They are different questions and only one of them can be
tested against a burn footprint.

**Will fire reach here and run?**

    hazard = sqrt(fuel · slope)        gated on whether anyone lives here

Fuel and slope compound rather than average: steep ground with nothing to
burn is not dangerous, and neither is heavy fuel on the flat. The gate is
**presence, not magnitude** — see below.

**How bad would it be if it did?**

    consequence = fragility (precarious housing, people who cannot leave)
                + deficit   (no mains water, so no hydrants)
                + how many households are behind the cell

Reported alongside, never multiplied into the hazard ranking. A cell with
precarious housing and no hydrants is genuinely worse off when fire
arrives, but that says nothing about whether fire arrives.

## The gate is presence, not magnitude

The single largest error in the first version. Weighting by dwelling count
pushes the index toward dense urban cores, and **the interface is by
definition where settlement is sparse**: measured over Valparaíso, cells in
the fire's interface zone had a 90th-percentile dwelling count of 8 against
36 for the region. Five households on a steep slope against cured matorral
are in real danger; five hundred in a flat city core are not at
wildland-fire risk at all.

So presence gates and magnitude is reported separately, as consequence.

## Status: hazard validated, consequence not

Against the February 2024 Viña del Mar fire
(`ingest/scripts/validate_wui.py`), of 115 inhabited cells in the fire's
interface zone:

| ranked by | in top decile | lift vs chance |
|---|---|---|
| **presence x hazard** | **44** | **3.83x** |
| hazard alone | 39 | 3.39x |
| fuel alone | 35 | 3.04x |
| dryness (NDMI) alone | 27 | 2.35x |
| slope alone | 0 | 0.00x |
| the first version's composite | 4 | 0.35x |

Fuel was the missing term. Slope is useless on its own yet improves the
combination, which is physically right: it amplifies spread where there is
something to spread through.

Two cautions that keep this short of a calibrated model. The sample is 115
cells from one event, so the *ordering* of these terms is more trustworthy
than any coefficient. And the consequence side remains untested — a burn
footprint cannot validate it, structure-loss records can, and those come
from CONAF and SENAPRED.

## What is still missing

**Fuel type.** Sentinel-2 gives fuel *state* — how much biomass and how dry.
CONAF's Catastro de Uso de Suelo y Vegetación gives fuel *type*, which is
what the Kitral models in Cell2Fire consume. It has no reachable public
service, so it is an ask for the Phase 5 conversation.

**Egress.** Roads are not in the consequence term yet. People died in Viña
in narrow dead-end hillside streets, and that geometry is computable from
OpenStreetMap today.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Weights:
    """Consequence weights only. Hazard has no free parameters: it is the
    geometric mean of fuel and slope, and adding knobs there would invite
    fitting to one event."""

    precarious: float = 0.40
    vulnerable: float = 0.35
    no_water: float = 0.25

    def normalised(self) -> "Weights":
        t = self.precarious + self.vulnerable + self.no_water
        return Weights(self.precarious / t, self.vulnerable / t,
                       self.no_water / t)


DEFAULT = Weights()

# A cell counts as inhabited at this many dwellings. A gate, not a ramp:
# see the module docstring on why magnitude belongs in consequence.
PRESENT_DWELLINGS = 1.0

# Where consequence stops scaling. Beyond a few hundred households the
# distinction stops being operationally useful.
FULL_CONSEQUENCE_DWELLINGS = 200.0


def present(dwellings) -> float:
    """1 if anyone lives here, 0 otherwise."""
    if dwellings is None or dwellings < PRESENT_DWELLINGS:
        return 0.0
    return 1.0


def hazard_of(slope_factor, fuel_factor) -> tuple[float | None, bool]:
    """sqrt(fuel * slope), or None when fuel was never observed.

    Compounding rather than averaging keeps either one near zero decisive:
    bare steep ground does not burn, and heavy fuel on the flat does not run.

    **Unobserved fuel returns None, not a slope-only fallback.** A cell with
    no Sentinel-2 observation is unknown, not low-fuel, and slope alone
    scored 0.00x lift against the 2024 fire — ranking on it injects noise.
    Measured: 4,239 Valparaíso cells lacked fuel, 576 of them landed in the
    index's top decile on slope alone, and none were anywhere near the fire.
    Excluding them raised lift from 3.39x to 3.48x.

    This is the same rule the detection layers follow. No observation is not
    an observation of nothing.
    """
    s = _clamp(slope_factor)
    if fuel_factor is None or fuel_factor != fuel_factor:
        return None, False
    return (s * _clamp(fuel_factor)) ** 0.5, True


def consequence_of(*, dwellings, frac_precario, frac_vulnerable,
                   frac_sin_red_agua, weights: Weights = DEFAULT) -> dict:
    """How bad it would be if fire arrived. Untested — see the docstring."""
    w = weights.normalised()
    condition = (w.precarious * _clamp(frac_precario)
                 + w.vulnerable * _clamp(frac_vulnerable)
                 + w.no_water * _clamp(frac_sin_red_agua))
    d = float(dwellings or 0)
    scale = min(1.0, (d / FULL_CONSEQUENCE_DWELLINGS) ** 0.5) if d > 0 else 0.0
    return {"condition": round(condition, 4),
            "scale": round(scale, 4),
            "consequence": round(condition * scale, 4)}


def score_cell(
    *,
    dwellings,
    slope_factor,
    frac_precario=0.0,
    frac_vulnerable=0.0,
    frac_sin_red_agua=0.0,
    fuel_factor=None,
    weights: Weights = DEFAULT,
) -> dict:
    """Score one cell. Pure: no I/O, no globals, no surprises.

    `wui` is the hazard ranking — the part that has been validated. The
    consequence fields ride alongside and are deliberately not multiplied
    into it.
    """
    hazard, has_fuel = hazard_of(slope_factor, fuel_factor)
    gate = present(dwellings)
    cons = consequence_of(dwellings=dwellings, frac_precario=frac_precario,
                          frac_vulnerable=frac_vulnerable,
                          frac_sin_red_agua=frac_sin_red_agua,
                          weights=weights)
    return {
        "wui": None if hazard is None else round(gate * hazard, 4),
        "inhabited": bool(gate),
        "hazard": None if hazard is None else round(hazard, 4),
        "has_fuel": has_fuel,
        **cons,
    }


def score_frame(df, weights: Weights = DEFAULT, fuel_col: str | None = None):
    """Score a DataFrame of cells.

    Expects `n_vp`, `slope_factor` and the `frac_*` columns from
    `census.exposure_terms`. Cells with no terrain data get a slope factor of
    zero rather than being dropped: the census already says people live there.
    """
    import pandas as pd

    rows = []
    for r in df.itertuples():
        fuel = None
        if fuel_col:
            v = getattr(r, fuel_col, None)
            if v is not None and v == v:               # not NaN
                fuel = float(v)
        rows.append(score_cell(
            dwellings=float(getattr(r, "n_vp", 0) or 0),
            slope_factor=float(getattr(r, "slope_factor", 0) or 0),
            frac_precario=float(getattr(r, "frac_precario", 0) or 0),
            frac_vulnerable=float(getattr(r, "frac_vulnerable", 0) or 0),
            frac_sin_red_agua=float(getattr(r, "frac_sin_red_agua", 0) or 0),
            fuel_factor=fuel,
            weights=weights,
        ))
    out = pd.concat([df.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    return out.sort_values("wui", ascending=False).reset_index(drop=True)


def _clamp(v) -> float:
    if v is None or v != v:
        return 0.0
    return float(min(1.0, max(0.0, v)))
