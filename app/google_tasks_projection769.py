"""Deterministic, read-only scheduling for medication, supplement and protocol tasks.

This only projects existing Tracker schedules: it does not recommend a dose,
log an administration, or select vial inventory.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .calendar import occurrence_time, staged_occurrences
from .models import Protocol, RegimenItem, RegimenSchedule
from .projection_exclusions import excluded, exclusions_for
from .routers.regimen635 import due_on

KINDS = ("medication", "supplement", "protocol")
MAX_DAYS = 14


@dataclass(frozen=True)
class Occurrence769:
    key: str
    kind: str
    source_id: int
    day: date
    at_time: str
    title: str
    notes: str

    def task_body(self):
        # Google's public Tasks API only persists a due DATE, not a time.
        return {
            "title": self.title,
            "notes": self.notes + "\nTracker ID: " + self.key,
            "due": self.day.isoformat() + "T00:00:00.000Z",
            "status": "needsAction",
        }


def _key(kind, source_id, day, clock):
    return f"t769:{kind}:{source_id}:{day.isoformat()}:{clock or 'any'}"


def schedule_sources769(db):
    schedules = list(db.scalars(
        select(RegimenSchedule).options(selectinload(RegimenSchedule.item))
        .order_by(RegimenSchedule.id)
    ))
    protocols = list(db.scalars(
        select(Protocol).options(selectinload(Protocol.items))
        .order_by(Protocol.id)
    ))
    return schedules, protocols


def projected769(db, today=None, days=MAX_DAYS):
    if not isinstance(days, int) or not 1 <= days <= MAX_DAYS:
        raise ValueError("Task projection horizon must be 1–14 days")
    today = today or date.today()
    until = today + timedelta(days=days)
    schedules = list(db.scalars(
        select(RegimenSchedule).options(selectinload(RegimenSchedule.item))
    ))
    protocols = list(db.scalars(
        select(Protocol).options(selectinload(Protocol.items))
    ))
    from .models import Compound
    compounds = {c.id: c.name for c in db.scalars(select(Compound))}
    rules = exclusions_for(
        db, [i.id for p in protocols if p.is_active for i in p.items]
    )
    out = {}
    for schedule in schedules:
        item = schedule.item
        if not (item and item.active and schedule.active and item.kind in ("medication", "supplement")):
            continue
        for offset in range(days):
            day = today + timedelta(days=offset)
            if not due_on(schedule, day):
                continue
            clock = (schedule.at_time or "").strip()
            key = _key(item.kind, schedule.id, day, clock)
            title = f"{clock + ' · ' if clock else ''}{item.name} — {schedule.amount}"
            notes = f"Tracker {item.kind}; scheduled dose. Mark complete only after taking."
            out[key] = Occurrence769(key, item.kind, schedule.id, day, clock, title, notes)
    for protocol in protocols:
        if not protocol.is_active or not protocol.start_date:
            continue
        if protocol.end_date is not None and protocol.end_date < today:
            continue
        if protocol.start_date >= until:
            continue
        total = (until - protocol.start_date).days
        if not 0 < total <= 36500:
            continue
        for item in protocol.items:
            try:
                occurrence_days = staged_occurrences(item, protocol.start_date, total)
            except (ValueError, TypeError, OverflowError):
                continue
            for day in occurrence_days:
                if day < today or day >= until:
                    continue
                if protocol.end_date is not None and day > protocol.end_date:
                    continue
                if excluded(rules, item.id, day):
                    continue
                clock = occurrence_time(item, protocol.start_date, day)
                key = _key("protocol", item.id, day, clock)
                compound = compounds.get(item.compound_id, "Compound")
                title = (f"{clock + ' · ' if clock else ''}{compound} — "
                         f"{item.amount_value:g} {item.amount_unit}")
                notes = (f"Tracker protocol: {protocol.name}. "
                         "Completion requires vial/blend reconciliation in Tracker; "
                         "it does not automatically withdraw inventory.")
                out[key] = Occurrence769(key, "protocol", item.id, day, clock, title, notes)
    return dict(sorted(out.items(), key=lambda kv: (kv[1].day, kv[1].at_time, kv[1].title)))
