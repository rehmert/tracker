"""Release 758: read-only, vial-specific printed target and U-100 markings.

Only an unambiguous CURRENT active mass-based plan is suggested. A user may
explicitly choose a different positive mg target for one label preview.
Derived markings use exactly the same vial view as Dose Log/Calendar and
never change a protocol, vial, administration or inventory balance.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from math import isfinite

from sqlalchemy import select

from . import units as U
from .models import Protocol, ProtocolItem


def _short758(value: float, digits: int = 3) -> str:
    """Printed values have bounded precision, without scientific notation."""
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def _valid_target758(value) -> float:
    try:
        val = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Target dose must be a positive mg amount.") from exc
    if not isfinite(val) or not 0 < val <= 1_000_000:
        raise ValueError("Target dose must be a finite positive mg amount.")
    return val


def active_targets758(db, compound_ids, *, today: date | None = None):
    """Distinct active, CURRENT mass-stage mg targets for compounds.

    Never pick arbitrarily between conflicting protocol amounts. Protocols
    with unspecified start dates or noncurrent stages are not suggestions.
    """
    ids = set(compound_ids)
    if not ids:
        return {}
    today = today or date.today()
    query = (
        select(ProtocolItem, Protocol)
        .join(Protocol, Protocol.id == ProtocolItem.protocol_id)
        .where(Protocol.is_active.is_(True),
               ProtocolItem.compound_id.in_(ids))
        .order_by(Protocol.id, ProtocolItem.position, ProtocolItem.id)
    )
    doses = defaultdict(set)
    for item, plan in db.execute(query):
        if (plan.start_date is None or plan.start_date > today or
                plan.end_date is not None and plan.end_date < today):
            continue
        stage = ((today - plan.start_date).days // 7) + 1
        if ((item.start_week or 1) > stage or
                (item.end_week is not None and stage > item.end_week)):
            continue
        try:
            amount = float(item.amount_value)
            unit = U.parse_unit(item.amount_unit)
            if unit.dim != "mass" or not isfinite(amount):
                continue
            value = _valid_target758(amount * unit.factor / 1000)
        except (ValueError, TypeError, OverflowError):
            continue
        doses[item.compound_id].add(round(value, 8))
    return {key: sorted(vals) for key, vals in doses.items()}


def resolve_target758(candidates, user_target=None):
    """Single active target is a suggestion; explicit GET target overrides it."""
    if user_target not in (None, ""):
        return _valid_target758(user_target), "explicit label target"
    if len(candidates) == 1:
        return candidates[0], "single current active protocol target"
    return None, "multiple active targets" if candidates else "no active mg target"


def dose_line758(view, target_mg):
    """Compute one bounded label line using the selected vial only.

    Returned concentration and U-100 markings must agree with the existing
    server-side Dose Log preview. 'U100' is syringe-volume markings, NOT IU.
    """
    target = _valid_target758(target_mg)
    if view is None or view.dim != "mass":
        raise ValueError("This vial is not recorded in mass units; mg conversion is unavailable.")
    conc = view.conc_per_ml
    if conc is None or not isfinite(conc) or conc <= 0:
        raise ValueError("Record a valid vial liquid volume and concentration before printing target and U-100 units.")
    base = target * 1000
    if (not isfinite(view.remaining_base) or
            view.remaining_base < base - 1e-7):
        raise ValueError("The recorded remaining vial content is insufficient for the target dose.")
    volume_ml = base / conc
    markings = U.ml_to_syringe_units(volume_ml)
    if not isfinite(markings) or not isfinite(volume_ml) or markings <= 0:
        raise ValueError("Unable to calculate a finite positive withdrawal from this vial.")
    target_display = _short758(target, 4)
    marks_display = _short758(markings, 3)
    if target_display == "0" or marks_display == "0":
        raise ValueError(
            "Target or U-100 syringe markings are too small to print "
            "accurately on this label."
        )
    text = f"TARGET:{target_display}MG U100:{marks_display}"
    if len(text) > 34:
        raise ValueError("Target and syringe-unit values are too long for the printed label.")
    return {
        "line": text,
        "target_mg": target,
        "concentration_mg_ml": conc / 1000,
        "withdrawal_ml": volume_ml,
        "syringe_units": markings,
        "basis": "recorded vial effective concentration",
    }


def validate_label_fit758(lines, layout, rotation):
    """Never silently truncate critical target/marking text in SVG or PNG."""
    target = next((s for s in lines if s.startswith("TARGET:")), None)
    if target is None:
        return
    from . import vial_labels423 as base
    from . import vial_label_rotation431 as rotated
    w, h, _, _ = base._panel_size(layout)
    if rotation in (90, 270):
        selected = rotated._selected_rotated(lines, h, w)
    else:
        selected = base._selected(lines, w, h)
    if target not in selected:
        raise ValueError(
            "This sticker layout/rotation cannot print the full target "
            "and U-100 markings. Choose 40x20 mm (normal orientation)."
        )
