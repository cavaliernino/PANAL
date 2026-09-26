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

## Structure

    exposure   is anything at stake here            dwellings, people
    hazard     how hard fire would run              slope  (+ fuel, Phase 2b)
    fragility  how badly it would go                precarious housing,
                                                    people who cannot leave
    deficit    what is missing to fight it          no mains water
                                                    (+ egress, Phase 2c)

    wui = exposure_gate · (w_h·hazard + w_f·fragility + w_d·deficit)

`exposure_gate` multiplies rather than adds, because no amount of slope or
fragility matters without something to lose.

## Status: no demonstrated skill. Do not ship this as a risk product.

Tested against the February 2024 Viña del Mar fire on 2026-09-25
(`ingest/scripts/validate_wui.py`), the index **failed**. Its top decile
contained 2 of the 115 inhabited cells in the fire's interface zone, where
chance would give 12. Every component alone did no better; slope, the term
with the clearest physical basis, put 0 of 115 in its top decile.

The test is also mis-specified, and the distinction matters more than the
number. **This index does not predict where a fire starts** — it predicts
how bad things would be if one arrived. The 2024 fire burned where it did
because of an ignition point and a wind, not because that hillside was the
region's most dangerous. Ranking the cells that happened to burn conflates
hazard with consequence. The honest validation is against *structure loss*,
which needs CONAF and SENAPRED damage records: a Phase 5 dependency, and now
the blocker on calling this index anything at all.

Two weaknesses stand regardless:

* **No fuel layer.** The interface is defined by adjacency to burnable
  vegetation and this does not measure it.
* **The weights are unvalidated**, and one looks wrong: `deficit` carries
  25% on no-mains-water, yet burned cells had *better* mains coverage than
  the regional median (0.37 against 0.53).

Until validation reports a positive result, this is a research artefact.
Nothing in the interface may imply it ranks danger.

## What is deliberately missing

No fuel layer yet, so a house beside dense matorral and the same house
surrounded by asphalt currently score alike. That is the single largest gap
and it is named in the output as `has_fuel: false`, rather than left for a
reader to assume it was included.
"""

from __future__ import annotations

from dataclasses import dataclass

# Provisional. See the module docstring: these are a hypothesis drawn from
# the shape of one disaster, not a fitted model.
@dataclass(frozen=True)
class Weights:
    hazard: float = 0.40
    fragility: float = 0.35
    deficit: float = 0.25

    # Within fragility.
    precarious: float = 0.55
    vulnerable: float = 0.45

    def normalised(self) -> "Weights":
        total = self.hazard + self.fragility + self.deficit
        return Weights(
            hazard=self.hazard / total,
            fragility=self.fragility / total,
            deficit=self.deficit / total,
            precarious=self.precarious,
            vulnerable=self.vulnerable,
        )


DEFAULT = Weights()

# A cell reaches full exposure at this many dwellings. Below it the score is
# scaled down, so an isolated house does not rank beside a neighbourhood.
# It is a gate on consequence, not on whether the house matters.
FULL_EXPOSURE_DWELLINGS = 50.0


def exposure_gate(dwellings: float) -> float:
    """0-1. How much is at stake, saturating at a neighbourhood's worth.

    Square-root rather than linear: the difference between 1 and 10 dwellings
    matters far more than between 200 and 400, because the first is the
    difference between an outbuilding and a settlement.
    """
    if dwellings is None or dwellings <= 0:
        return 0.0
    return float(min(1.0, (dwellings / FULL_EXPOSURE_DWELLINGS) ** 0.5))


def score_cell(
    *,
    dwellings: float,
    slope_factor: float,
    frac_precario: float,
    frac_vulnerable: float,
    frac_sin_red_agua: float,
    fuel_factor: float | None = None,
    weights: Weights = DEFAULT,
) -> dict:
    """Score one cell. Pure: no I/O, no globals, no surprises.

    Every input is already 0-1 except `dwellings`. `fuel_factor` is accepted
    now so the shape is right when the vegetation layer lands; passing None
    leaves hazard resting on slope alone and marks the result.
    """
    w = weights.normalised()

    gate = exposure_gate(dwellings)

    if fuel_factor is None:
        hazard = _clamp(slope_factor)
        has_fuel = False
    else:
        # Fuel and slope compound rather than average: steep ground with
        # nothing to burn is not dangerous, and neither is heavy fuel on the
        # flat. The geometric mean keeps either one near zero decisive.
        hazard = (_clamp(slope_factor) * _clamp(fuel_factor)) ** 0.5
        has_fuel = True

    fragility = (
        w.precarious * _clamp(frac_precario)
        + w.vulnerable * _clamp(frac_vulnerable)
    ) / (w.precarious + w.vulnerable)

    deficit = _clamp(frac_sin_red_agua)

    raw = w.hazard * hazard + w.fragility * fragility + w.deficit * deficit
    return {
        "wui": round(gate * raw, 4),
        "exposure": round(gate, 4),
        "hazard": round(hazard, 4),
        "fragility": round(fragility, 4),
        "deficit": round(deficit, 4),
        "has_fuel": has_fuel,
    }


def score_frame(df, weights: Weights = DEFAULT, fuel_col: str | None = None):
    """Score a DataFrame of cells.

    Expects `n_vp`, `slope_factor`, and the `frac_*` columns produced by
    `census.exposure_terms`. Cells with no terrain data — the DEM has no
    ocean — get a slope factor of zero rather than being dropped, because
    the census already says people live there.
    """
    import pandas as pd

    rows = []
    for r in df.itertuples():
        rows.append(score_cell(
            dwellings=float(getattr(r, "n_vp", 0) or 0),
            slope_factor=float(getattr(r, "slope_factor", 0) or 0),
            frac_precario=float(getattr(r, "frac_precario", 0) or 0),
            frac_vulnerable=float(getattr(r, "frac_vulnerable", 0) or 0),
            frac_sin_red_agua=float(getattr(r, "frac_sin_red_agua", 0) or 0),
            fuel_factor=(float(getattr(r, fuel_col)) if fuel_col
                         and getattr(r, fuel_col, None) is not None else None),
            weights=weights,
        ))
    out = pd.concat([df.reset_index(drop=True),
                     pd.DataFrame(rows)], axis=1)
    return out.sort_values("wui", ascending=False).reset_index(drop=True)


def _clamp(v) -> float:
    if v is None:
        return 0.0
    return float(min(1.0, max(0.0, v)))
