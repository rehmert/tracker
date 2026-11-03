"""Read-only inventory quantity and recorded-date preview for a planned event.

This evaluates recorded stock, unit conversion, and recorded expiry/BUD
at the projected date. It does not establish suitability, sterility,
administration readiness, or a future inventory guarantee.
"""
from __future__ import annotations

from math import isfinite

from . import units as U
from .vial_recommendation import date_warnings, rank_vials


def assess_planned_vials(event: dict, vials: list, views: dict) -> dict:
    """Summarize stock for exactly one projected compound/amount/date."""
    matching = [
        v for v in vials
        if v.compound_id == event["compound_id"]
        and v.status in ("in_use", "sealed")
    ]
    result = {
        "state": "none",
        "detail": "No active vials recorded",
        "matching_count": len(matching),
        "candidate_count": 0,
        "date_flagged_count": 0,
        "suggested_id": None,
        "suggested_label": "",
        "suggested_status": "",
    }
    if not matching:
        return result

    stocked = [
        v for v in matching
        if v.id in views and views[v.id].remaining_base > 0
    ]
    if not stocked:
        result.update(state="empty", detail="No remaining quantity in active vials")
        return result

    guidance = {}
    convertible = 0
    amount_sufficient = 0
    for vial in stocked:
        view = views[vial.id]
        try:
            required = U.amount_to_vial_base(
                float(event["amount"]),
                event["unit"],
                view.dim,
                view.conc_per_ml,
            )
        except (ValueError, TypeError, ArithmeticError):
            continue
        if not isfinite(required) or required <= 0:
            continue
        convertible += 1
        if required <= view.remaining_base + 1e-7:
            amount_sufficient += 1
            guidance[vial.id] = {"eligible": True}

    scheduled = event["date"]
    suggested_id, warnings = rank_vials(stocked, guidance, today=scheduled)
    flagged = sum(bool(warnings.get(v.id)) for v in stocked)
    result["date_flagged_count"] = flagged
    qualifying = [
        v for v in stocked
        if guidance.get(v.id, {}).get("eligible", False)
        and not warnings.get(v.id)
    ]
    result["candidate_count"] = len(qualifying)

    if suggested_id is not None and qualifying:
        candidate = next(v for v in qualifying if v.id == suggested_id)
        count = len(qualifying)
        detail = f"{count} vial{'s' if count != 1 else ''} cover planned quantity"
        if flagged:
            detail += f"; {flagged} other vial{'s' if flagged != 1 else ''} date-flagged"
        result.update(
            state="candidate",
            detail=detail,
            suggested_id=candidate.id,
            suggested_label=candidate.label or f"#{candidate.id}",
            suggested_status=candidate.status,
        )
    elif amount_sufficient and flagged:
        result.update(
            state="dates",
            detail="Quantity exists, but matching vials have recorded date warnings",
        )
    elif not convertible:
        result.update(
            state="units",
            detail="Check vial units or missing concentration",
        )
    else:
        result.update(
            state="insufficient",
            detail="No single vial has sufficient unflagged quantity",
        )
    return result
