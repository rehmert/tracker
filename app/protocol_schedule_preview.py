"""Upcoming protocol schedule previews for the read-only protocol index.

All projected dates are generated with the same staged occurrence and
hidden-projection rules as /calendar. Previews do not reconcile recorded
administrations or imply that any dose should be taken.
"""
from __future__ import annotations

from datetime import date, timedelta
from math import isfinite

from .calendar import occurrence_time, staged_occurrences
from .projection_exclusions import excluded

LOOKAHEAD_DAYS = 60


def preview(protocol, on: date, rules: dict | None = None,
            days: int = LOOKAHEAD_DAYS) -> dict:
    """Return the closest non-hidden projected item, or why none is shown.

    The lookahead includes today and *days* future days. No writes and no
    invented fallback dates or doses. This is a projection, not a log.
    """
    rules = rules or {}
    if not protocol.is_active:
        return {"state": "what_if", "detail": "What-if (not scheduled)",
                "next": None}
    if protocol.start_date is None:
        return {"state": "missing_start", "detail": "Set a start date",
                "next": None}
    if protocol.end_date is not None and protocol.end_date < on:
        return {"state": "ended", "detail": "Protocol end date passed",
                "next": None}
    if not protocol.items:
        return {"state": "no_items", "detail": "No scheduled items",
                "next": None}
    if protocol.start_date > on + timedelta(days=days):
        return {"state": "later", "detail": f"Starts {protocol.start_date.isoformat()}",
                "next": None}

    span = (on - protocol.start_date).days + days + 1
    candidates = []
    for item in protocol.items:
        amount = item.amount_value
        if not isinstance(amount, (float, int)) or not isfinite(amount) or amount <= 0:
            continue
        for day in staged_occurrences(item, protocol.start_date, span):
            if day < on or day > on + timedelta(days=days):
                continue
            if protocol.end_date is not None and day > protocol.end_date:
                continue
            if excluded(rules, item.id, day):
                continue
            clock = occurrence_time(item, protocol.start_date, day)
            candidates.append({
                "date": day,
                "time": clock,
                "compound_id": item.compound_id,
                "compound": item.compound.name,
                "amount": amount,
                "unit": item.amount_unit,
                "item_id": item.id,
                "position": item.position,
            })
    if not candidates:
        return {"state": "none_soon",
                "detail": f"No visible projection in next {days} days",
                "next": None}
    earliest = min(
        candidates,
        key=lambda entry: (entry["date"], entry["time"] or "",
                           entry["position"], entry["item_id"]),
    )
    return {
        "state": "today" if earliest["date"] == on else "upcoming",
        "detail": "Projected today" if earliest["date"] == on
                  else "Upcoming projection",
        "next": earliest,
    }
