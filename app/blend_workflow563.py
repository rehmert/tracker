"""Release 563: validate read-only sequential waterfall inventory calculations.

No inventory mutations take place in this module. All intermediate liquid
and powder displacement volumes are nominal, not verified physical volumes.
"""
from math import isfinite

from . import services, units as U
from .models import Vial


def positive(raw, label):
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{label}: enter a number.")
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{label}: enter a positive finite number.")
    return value


def calculate_waterfall(form, db):
    raw_ids = form.getlist("waterfall_source_id")
    if not 2 <= len(raw_ids) <= 6:
        raise ValueError("Choose between 2 and 6 source vials in transfer order.")
    try:
        ids = [int(value) for value in raw_ids]
    except (ValueError, TypeError):
        raise ValueError("Select valid source vials.")
    if any(value < 1 for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("Each source vial must be selected exactly once.")

    vials = [db.get(Vial, ident) for ident in ids]
    if any(vial is None or vial.status not in ("sealed", "in_use") for vial in vials):
        raise ValueError("One or more source vials are unavailable.")
    if len({vial.compound_id for vial in vials}) != 1:
        raise ValueError("Waterfall requires source vials of the same compound.")
    if any(vial.volume_ml is not None for vial in vials):
        raise ValueError("Waterfall requires dry source vials. Liquid vials belong in the normal blend workflow.")

    views = services.vial_views(db, vials)
    for vial in vials:
        view = views[vial.id]
        if view.remaining_base <= 0 or abs(view.content_base - view.remaining_base) > max(1e-6, view.content_base * 1e-8):
            raise ValueError(f"Vial #{vial.id} must be dry and unused.")
    if len({views[v.id].dim for v in vials}) != 1:
        raise ValueError("Selected vials have incompatible content units.")

    bac = positive(form.get("waterfall_bac_ml"), "Initial BAC water volume")
    capacity = positive(form.get("waterfall_capacity_ml"), "Final vial capacity")
    if bac > capacity + 1e-8:
        raise ValueError("Nominal final volume exceeds the final vial capacity.")

    unit = str(form.get("waterfall_target_unit", "")).strip()
    target_base, target_dim = U.to_base(
        positive(form.get("waterfall_target_amount"), "Target amount per draw"), unit
    )
    if target_dim != views[vials[0].id].dim:
        raise ValueError("Target unit is incompatible with source-vial units.")

    total = sum(views[v.id].remaining_base for v in vials)
    if target_base > total + 1e-6:
        raise ValueError("Target amount per draw exceeds total available content.")
    draw = target_base * bac / total
    label = str(form.get("label", "")).strip()
    if not label or len(label) > 160:
        raise ValueError("Enter a destination label (up to 160 characters).")

    return {
        "vials": vials, "views": views, "label": label, "target_base": target_base,
        "target_unit": unit, "volume": bac, "capacity": capacity,
        "total": total, "draw_ml": draw,
        "unit": U.BASE_UNIT[views[vials[0].id].dim],
        "note": str(form.get("notes", "")).strip(),
    }
