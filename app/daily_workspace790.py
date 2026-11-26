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


def regimen790(db, day):
    from datetime import datetime
    from sqlalchemy import select
    from .models import RegimenSchedule, RegimenEntry, RegimenTabletSchedule731
    from .routers.regimen635 import due_on, MEALS
    from .regimen_tablets731 import format_number
    schedules = list(db.scalars(select(RegimenSchedule)))
    due = sorted((s for s in schedules if s.item.active and due_on(s, day)),
                 key=lambda s: (not bool(s.at_time), s.at_time or "", s.item.name.casefold(), s.id))
    start = datetime.combine(day, datetime.min.time())
    entries = list(db.scalars(select(RegimenEntry).where(
        RegimenEntry.logged_at >= start, RegimenEntry.logged_at < start + timedelta(days=1))))
    return dict(regimen_day=day, regimen_due=due,
                regimen_recorded={e.schedule_id for e in entries if e.schedule_id is not None},
                regimen_entries={e.schedule_id: e for e in entries if e.schedule_id is not None},
                regimen_tablet_plans={p.schedule_id: p for p in db.scalars(select(RegimenTabletSchedule731))},
                regimen_meals=MEALS, tablet_fmt=format_number,
                regimen_now=datetime.now().strftime("%H:%M"))
