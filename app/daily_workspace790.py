"""Shared read-only schedule projection for Today and Overview.

Calendar remains the source of truth for blend, exclusion and Google status.
Never infer an administration or select inventory when showing a summary.
"""
from datetime import timedelta


def summary790(db, day, days_ahead=7):
    from .routers.calendar import _month_events
    end = day + timedelta(days=days_ahead)
    events = {}
    missing = {}
    cursor = day.replace(day=1)
    while cursor <= end:
        _, next_month, month, starts = _month_events(cursor, db, include_vial_choices=False)
        events.update(month)
        missing.update((p["id"], p) for p in starts)
        cursor = next_month
    return {
        "today": events.get(day, []),
        "upcoming": [(d, e) for d in sorted(events) if day < d <= end
                     for e in events[d] if e["status"] in ("upcoming", "pending_review")],
        "missing_start": list(missing.values()),
    }
