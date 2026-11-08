"""Release 511: read-only, recent dose shortcuts for the scoped workspace.

Only surface historical administrations whose exact vial is still offered and
whose entered quantity can still fit its current inventory. This is a
navigation shortcut, not an automatic administration or a recommended dose.
"""
from sqlalchemy import select

from . import units as U
from .models import DoseLog, Vial


def recent_preparations(db, available_vials, views, limit: int = 5) -> list[dict]:
    available = {v.id: v for v in available_vials}
    if not available:
        return []
    items = db.scalars(
        select(DoseLog)
        .where(DoseLog.kind == "dose", DoseLog.vial_id.in_(available))
        .order_by(DoseLog.taken_at.desc(), DoseLog.id.desc())
        .limit(250)
    )
    selected = []
    seen_compounds = set()
    for dose in items:
        vial = available.get(dose.vial_id)
        if vial is None or vial.status not in ("in_use", "sealed"):
            continue
        if vial.compound_id in seen_compounds:
            continue
        detail = views.get(vial.id)
        if detail is None:
            continue
        try:
            requested = U.amount_to_vial_base(
                dose.entered_value, dose.entered_unit,
                detail.dim, detail.conc_per_ml,
            )
            if not 0 < requested <= detail.remaining_base + 1e-7:
                continue
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        selected.append({
            "id": dose.id,
            "name": vial.compound.name,
            "vial_name": vial.label or f"Vial #{vial.id}",
            "vial_id": vial.id,
            "amount": dose.entered_value,
            "unit": dose.entered_unit,
            "taken_at": dose.taken_at,
        })
        seen_compounds.add(vial.compound_id)
        if len(selected) >= limit:
            break
    return selected
