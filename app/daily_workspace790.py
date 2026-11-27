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


def regimen_stamp790(schedule, plan, day):
    from .idempotency import payload_hash
    tablet = ([plan.tablet_strength_mg, plan.prescribed_dose_mg, plan.tablets_planned]
              if plan else None)
    return payload_hash([schedule.id, schedule.item_id, schedule.item.name,
                         schedule.item.active, schedule.active, schedule.amount,
                         schedule.at_time, schedule.meal, schedule.cadence,
                         schedule.start_on, schedule.end_on, schedule.weekdays,
                         schedule.interval_days, day, tablet])


def regimen790(db, day):
    from datetime import datetime
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from .models import RegimenSchedule, RegimenEntry, RegimenTabletSchedule731
    from .routers.regimen635 import due_on, MEALS
    from .regimen_tablets731 import format_number
    schedules = list(db.scalars(select(RegimenSchedule).options(selectinload(RegimenSchedule.item))))
    due = sorted((s for s in schedules if s.item.active and due_on(s, day)),
                 key=lambda s: (not bool(s.at_time), s.at_time or "", s.item.name.casefold(), s.id))
    start = datetime.combine(day, datetime.min.time())
    entries = list(db.scalars(select(RegimenEntry).where(
        RegimenEntry.logged_at >= start, RegimenEntry.logged_at < start + timedelta(days=1))))
    plans = {p.schedule_id: p for p in db.scalars(select(RegimenTabletSchedule731))}
    return dict(regimen_day=day, regimen_due=due,
                regimen_recorded={e.schedule_id for e in entries if e.schedule_id is not None},
                regimen_entries={e.schedule_id: e for e in entries if e.schedule_id is not None},
                regimen_tablet_plans=plans,
                regimen_snapshots={s.id: regimen_stamp790(s, plans.get(s.id), day) for s in due},
                regimen_meals=MEALS, tablet_fmt=format_number,
                regimen_now=datetime.now().strftime("%H:%M"))
