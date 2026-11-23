"""Release 756: non-persisting, vial-specific Calendar withdrawal calculations.

No vial is assumed or selected. The logged mass amount remains authoritative;
volume and U-100 markings are derived only from that specific vial's recorded
effective content and liquid volume. Never infer concentrations from another vial.
"""
from __future__ import annotations

from math import isfinite

from . import units as U


def _display(number: float, decimals: int = 3) -> str:
    return f"{number:.{decimals}f}".rstrip("0").rstrip(".")


def vial_choices756(item, scheduled_on, vials, views):
    """Return (choices, reason) for an injection planned in MASS units.

    A returned candidate has a calculable conversion and adequate recorded
    *current* remaining mass. No doses/inventory are written or reserved.
    """
    try:
        dose = float(item.amount_value)
        u = U.parse_unit(item.amount_unit)
        target = dose * u.factor
        if u.dim != "mass" or not isfinite(target) or target <= 0:
            return [], None
    except (ValueError, TypeError, OverflowError):
        return [], None

    choices = []
    invalid = 0
    for vial in vials:
        if vial.compound_id != item.compound_id:
            continue
        if (vial.status not in ("sealed", "in_use") or
                vial.closed_on or
                (vial.expires_on and vial.expires_on < scheduled_on) or
                (vial.beyond_use_on and vial.beyond_use_on < scheduled_on)):
            continue
        view = views.get(vial.id)
        if view is None or view.dim != "mass":
            continue
        concentration = view.conc_per_ml
        if (concentration is None or not isfinite(concentration)
                or concentration <= 0 or
                not isfinite(view.remaining_base) or
                view.remaining_base < target - 1e-7):
            invalid += 1
            continue
        withdrawal_ml = target / concentration
        units = U.ml_to_syringe_units(withdrawal_ml)
        if (not isfinite(withdrawal_ml) or not isfinite(units) or
                withdrawal_ml <= 0 or units <= 0):
            invalid += 1
            continue
        choices.append({
            "id": vial.id,
            "label": vial.label or f"#{vial.id}",
            "status": vial.status,
            "target_mg": _display(target / 1000, 3),
            "concentration_mg_ml": _display(concentration / 1000, 3),
            "withdrawal_ml": _display(withdrawal_ml, 4),
            "syringe_units": _display(units, 3),
        })
    choices.sort(key=lambda c: (c["status"] != "in_use", c["id"]))
    reason = ("Some vials cannot be converted or lack enough recorded stock."
              if invalid else None)
    if not choices:
        reason = ("No eligible vial with a known concentration and sufficient "
                  "recorded stock; review vial details before logging.")
    return choices, reason
