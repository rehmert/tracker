"""Release 664: authenticated read-only workout calendar and consistency counts.

The month grid uses the local date of each completed workout's recorded
started_at (including backdated entries). Only completed sessions with at
least one actual set are shown, matching Release 661 dashboard counting.
No inferred workouts, streak targets, new persistence, or data mutation.
"""
from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, datetime, time, timedelta
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..workout_models654 import WorkoutSession654, WorkoutSet654

router = APIRouter()
CALENDAR664 = calendar.Calendar(firstweekday=calendar.MONDAY)
MIN_YEAR664 = 1900
MAX_YEAR664 = 2100
MONTH664 = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])\Z")


def selected_month664(value: str | None, today: date) -> date:
    """Strict local month selector; omitted means the current month."""
    if value is None:
        return today.replace(day=1)
    if not MONTH664.fullmatch(value):
        raise HTTPException(status_code=400, detail="Month must be YYYY-MM")
    year, month = int(value[:4]), int(value[5:])
    if not MIN_YEAR664 <= year <= MAX_YEAR664:
        raise HTTPException(status_code=400, detail="Month is out of range")
    return date(year, month, 1)


def neighboring_month664(first: date, offset: int) -> str | None:
    index = first.year * 12 + (first.month - 1) + offset
    year, month_zero = divmod(index, 12)
    if not MIN_YEAR664 <= year <= MAX_YEAR664:
        return None
    return f"{year:04d}-{month_zero + 1:02d}"


def workout_calendar_data664(db: Session, first: date, today: date) -> dict:
    """Materialize only recorded, completed, user-scoped month sessions."""
    end_key = neighboring_month664(first, 1)
    end = (
        datetime(int(end_key[:4]), int(end_key[5:]), 1)
        if end_key else datetime(MAX_YEAR664 + 1, 1, 1)
    )
    start = datetime.combine(first, time.min)
    # Do not treat implausibly future-dated records as past training.
    tomorrow = datetime.combine(today + timedelta(days=1), time.min)
    upper = min(end, tomorrow)
    rows = list(db.execute(
        select(
            WorkoutSession654.id.label("session_id"),
            WorkoutSession654.started_at.label("started_at"),
            WorkoutSession654.completed_at.label("completed_at"),
            func.count(WorkoutSet654.id).label("set_count"),
        )
        .select_from(WorkoutSession654)
        .join(
            WorkoutSet654,
            WorkoutSet654.session_id == WorkoutSession654.id,
        )
        .where(
            WorkoutSession654.completed_at.is_not(None),
            WorkoutSession654.started_at >= start,
            WorkoutSession654.started_at < upper,
        )
        .group_by(
            WorkoutSession654.id,
            WorkoutSession654.started_at,
            WorkoutSession654.completed_at,
        )
        .order_by(
            WorkoutSession654.started_at.desc(),
            WorkoutSession654.id.desc(),
        )
    ).all())

    by_date = defaultdict(list)
    for row in rows:
        by_date[row.started_at.date()].append(row)

    weeks = [
        [
            {
                "day": day,
                "in_month": day.year == first.year and day.month == first.month,
                "count": len(by_date.get(day, ())),
                "is_today": day == today,
            }
            for day in week
        ]
        for week in CALENDAR664.monthdatescalendar(first.year, first.month)
    ]
    days = [
        {"day": day, "sessions": by_date[day],
         "sets": sum(int(row.set_count) for row in by_date[day])}
        for day in sorted(by_date, reverse=True)
    ]
    return {
        "month": first,
        "month_label": first.strftime("%B %Y"),
        "previous": neighboring_month664(first, -1),
        "next": neighboring_month664(first, 1),
        "weeks": weeks,
        "days": days,
        "sessions": len(rows),
        "training_days": len(by_date),
        "sets": sum(int(row.set_count) for row in rows),
    }


@router.get("/workouts/calendar")
def workout_calendar664(
    request: Request, month: str | None = None,
    db: Session = Depends(get_scoped_db390),
):
    today = datetime.now().date()
    first = selected_month664(month, today)
    return render(
        request, "workout_calendar664.html",
        workout_calendar=workout_calendar_data664(db, first, today),
    )
