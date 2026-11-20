"""One physical dose source: ordinary Vial or previously prepared Blend.

A Blend holds one destination container, even if its components were
transferred from several vials of one compound or from different compounds.
Keep physical blend draw inventory in BlendDose; never create one DoseLog per
constituent or double-charge a transferred source vial.
"""
from __future__ import annotations

from math import isfinite
import re

from . import units as U


def source_identity710(raw: str) -> tuple[str, int]:
    """Legacy positive integer selects Vial; explicit blend:<id> selects Blend."""
    value = str(raw).strip()
    if re.fullmatch(r"[1-9][0-9]*", value):
        return "vial", int(value)
    if re.fullmatch(r"blend:[1-9][0-9]*", value):
        return "blend", int(value.split(":", 1)[1])
    raise ValueError("Choose a stocked vial or prepared blend.")


def remaining_blend_ml710(blend) -> float:
    if not isfinite(blend.final_volume_ml) or blend.final_volume_ml <= 0:
        raise ValueError("Prepared blend has no valid recorded liquid volume.")
    remaining = blend.final_volume_ml - sum(draw.volume_ml for draw in blend.doses)
    if not isfinite(remaining):
        raise ValueError("Prepared blend inventory is invalid.")
    return max(0.0, remaining)


def constituent_concentrations710(blend) -> list[dict]:
    """Group source transfers by compound, not by the number of source vials."""
    if not blend.components:
        raise ValueError("Prepared blend has no recorded compound composition.")
    rows = {}
    for component in blend.components:
        if component.source_vial is None or component.compound is None:
            raise ValueError("Prepared blend source information is incomplete.")
        if not isfinite(component.transferred_base) or component.transferred_base <= 0:
            raise ValueError("Prepared blend contains an invalid transfer amount.")
        dim = U.parse_unit(component.source_vial.content_unit).dim
        current = rows.get(component.compound_id)
        if current is not None and current["dim"] != dim:
            raise ValueError("Same compound is recorded using incompatible unit dimensions.")
        if current is None:
            current = {
                "compound_id": component.compound_id,
                "name": component.compound.name,
                "dim": dim,
                "base_per_ml": 0.0,
            }
            rows[component.compound_id] = current
        current["base_per_ml"] += component.transferred_base / blend.final_volume_ml
    return sorted(rows.values(), key=lambda x: (x["name"].casefold(), x["compound_id"]))


def resolve_blend_draw710(blend, value: float, unit: str, use_remaining=False) -> dict:
    """Convert one physical draw, without applying clinical dose assumptions.

    Volume entries always work when sufficient stock exists. Single-compound
    blends additionally accept that compound's native mass/IU units.
    Different compounds cannot share an ambiguous mass/IU amount.
    """
    if blend.status != "in_use":
        raise ValueError("Selected prepared blend is not available.")
    remaining = remaining_blend_ml710(blend)
    constituents = constituent_concentrations710(blend)
    if use_remaining:
        volume = remaining
        entered_value, entered_unit = volume, "mL"
    else:
        if not isfinite(value) or value <= 0:
            raise ValueError("Dose amount must be positive and finite.")
        parsed = U.parse_unit(unit)
        if parsed.dim == "volume":
            volume = value * parsed.factor
        else:
            if len(constituents) != 1:
                raise ValueError(
                    "A mixed-compound blend must be logged by its actual "
                    "withdrawn volume (mL or uL), not one compound amount."
                )
            component = constituents[0]
            if parsed.dim != component["dim"]:
                raise ValueError("Dose units do not match the compound in this blend.")
            volume = value * parsed.factor / component["base_per_ml"]
        entered_value, entered_unit = value, parsed.name
    if not isfinite(volume) or volume <= 0:
        raise ValueError("Draw volume must be positive and finite.")
    if volume > remaining + 1e-8:
        raise ValueError("Dose exceeds remaining prepared blend volume.")
    # Surface meaningful mg amounts as mg (1,000 mcg = 1 mg).  The global
    # unit formatter deliberately favors mcg in other Tracker contexts.
    def display_amount(base: float, dim: str) -> str:
        if dim == "mass" and 1000 <= abs(base) < 1_000_000:
            return f"{U._num(base / 1000)} mg"
        return U.fmt_amount(base, dim)

    components = [
        {**row, "amount_base": volume * row["base_per_ml"],
         "display": display_amount(volume * row["base_per_ml"], row["dim"])}
        for row in constituents
    ]
    return {
        "volume_ml": volume,
        "remaining_before_ml": remaining,
        "remaining_after_ml": max(0.0, remaining - volume),
        "entered_value": entered_value,
        "entered_unit": entered_unit,
        "components": components,
        "u100_marks": U.ml_to_syringe_units(volume),
    }
