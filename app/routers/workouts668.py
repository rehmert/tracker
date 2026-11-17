"""Release 668: authenticated, user-scoped routine scheduling and group plans.

Schedules represent intentions only, not fabricated workout sessions.
Superset/circuit groups are planning metadata; sets are still logged manually
through validated existing routes. No automatic sets are created.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import re

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import services
from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..workout_models655 import WorkoutRoutine655, WorkoutRoutineItem655
from ..workout_models668 import (
    WorkoutRoutineSchedule668, WorkoutRoutineGroup668,
    WorkoutRoutineGroupMember668,
)

router = APIRouter()
DAYS668 = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
WEEKDAY_RE668 = re.compile(r"[0-6](?:,[0-6])*\Z")
MAX_PREVIEW_DAYS668 = 56


def parse_weekdays668(raw: str) -> str:
    if not WEEKDAY_RE668.fullmatch(raw):
        raise ValueError("Choose weekdays 0–6 as comma-separated values.")
    days = [int(part) for part in raw.split(",")]
    if len(set(days)) != len(days) or not 1 <= len(days) <= 7:
        raise ValueError("Weekdays must be unique.")
    return ",".join(str(day) for day in sorted(days))


def next_occurrences668(days: str, start: date, end: date | None,
                        *, today: date, horizon: int = MAX_PREVIEW_DAYS668) -> list[date]:
    selected = {int(part) for part in parse_weekdays668(days).split(",")}
    first = max(start, today)
    return [
        day for n in range(horizon)
        if (day := first + timedelta(days=n)).weekday() in selected
        and (end is None or day <= end)
    ]


def _routine668(db: Session, routine_id: int) -> WorkoutRoutine655:
    routine = db.get(WorkoutRoutine655, routine_id)
    if routine is None:
        raise HTTPException(404, "Routine not found")
    return routine


@router.get("/workouts/routines/{routine_id}/schedule")
def schedule_page668(
    routine_id: int, request: Request,
    db: Session = Depends(get_scoped_db390),
):
    routine = _routine668(db, routine_id)
    schedule = db.get(WorkoutRoutineSchedule668, routine_id)
    groups = list(db.scalars(select(WorkoutRoutineGroup668)
        .where(WorkoutRoutineGroup668.routine_id == routine_id)
        .order_by(WorkoutRoutineGroup668.id)))
    items = list(db.scalars(select(WorkoutRoutineItem655)
        .where(WorkoutRoutineItem655.routine_id == routine_id)
        .order_by(WorkoutRoutineItem655.position, WorkoutRoutineItem655.id)))
    from ..workout_models654 import WorkoutEquipment654
    names = {
        item.id: (db.get(WorkoutEquipment654, item.equipment_id).name
                  if db.get(WorkoutEquipment654, item.equipment_id)
                  else "Unknown equipment")
        for item in items
    }
    memberships = {
        group.id: list(db.scalars(select(WorkoutRoutineGroupMember668)
            .where(WorkoutRoutineGroupMember668.group_id == group.id)
            .order_by(WorkoutRoutineGroupMember668.position,
                      WorkoutRoutineGroupMember668.id)))
        for group in groups
    }
    today = date.today()
    upcoming = next_occurrences668(schedule.weekdays, schedule.start_on,
                                   schedule.end_on, today=today) if schedule else []
    return render(
        request, "workout_schedule668.html", routine=routine,
        schedule=schedule, groups=groups, items=items, names=names,
        memberships=memberships, days=DAYS668, today=today,
        upcoming=upcoming[:16],
    )


@router.post("/workouts/routines/{routine_id}/schedule")
def save_schedule668(
    routine_id: int, weekdays: str = Form(""),
    start_on: date = Form(...), end_on: date | None = Form(None),
    db: Session = Depends(get_scoped_db390),
):
    _routine668(db, routine_id)
    url = f"/workouts/routines/{routine_id}/schedule"
    try:
        normalized = parse_weekdays668(weekdays)
        if not 2000 <= start_on.year <= 2100:
            raise ValueError("Schedule start year is out of range.")
        if end_on is not None and (end_on < start_on or end_on.year > 2100):
            raise ValueError("Schedule end must be on or after start.")
    except ValueError as exc:
        return services.flash_redirect(url, err=str(exc))
    saved = db.get(WorkoutRoutineSchedule668, routine_id)
    if saved is None:
        saved = WorkoutRoutineSchedule668(routine_id=routine_id)
        db.add(saved)
    saved.weekdays, saved.start_on, saved.end_on = normalized, start_on, end_on
    saved.updated_at = datetime.now()
    db.commit()
    return services.flash_redirect(url, msg="Workout schedule saved; no sessions were created.")


@router.post("/workouts/routines/{routine_id}/schedule/clear")
def clear_schedule668(routine_id: int, db: Session = Depends(get_scoped_db390)):
    _routine668(db, routine_id)
    current = db.get(WorkoutRoutineSchedule668, routine_id)
    if current is not None:
        db.delete(current)
        db.commit()
    return services.flash_redirect(
        f"/workouts/routines/{routine_id}/schedule",
        msg="Planned schedule cleared; historical sessions preserved.",
    )


@router.post("/workouts/routines/{routine_id}/groups")
def add_group668(
    routine_id: int, group_name: str = Form(""),
    group_type: str = Form("superset"), rounds: int = Form(3),
    item_ids: list[int] = Form([]),
    db: Session = Depends(get_scoped_db390),
):
    _routine668(db, routine_id)
    url = f"/workouts/routines/{routine_id}/schedule"
    name = group_name.strip()
    if (not 1 <= len(name) <= 100 or group_type not in ("superset", "circuit")
            or not 1 <= rounds <= 20 or not 2 <= len(item_ids) <= 10
            or len(set(item_ids)) != len(item_ids)):
        return services.flash_redirect(url, err="Choose 2–10 distinct exercises, a group name, and 1–20 rounds.")
    valid = set(db.scalars(select(WorkoutRoutineItem655.id)
        .where(WorkoutRoutineItem655.routine_id == routine_id)))
    if not set(item_ids) <= valid:
        raise HTTPException(404, "Exercise not in routine")
    occupied = db.scalars(select(WorkoutRoutineGroupMember668.routine_item_id)
        .where(WorkoutRoutineGroupMember668.routine_item_id.in_(item_ids)))
    if any(True for _ in occupied):
        return services.flash_redirect(url, err="Each exercise may belong to only one group.")
    if db.scalar(select(WorkoutRoutineGroup668.id).where(
        WorkoutRoutineGroup668.routine_id == routine_id,
        WorkoutRoutineGroup668.group_name == name,
    )) is not None:
        return services.flash_redirect(url, err="This group name already exists.")
    group = WorkoutRoutineGroup668(
        routine_id=routine_id, group_name=name,
        group_type=group_type, rounds=rounds,
    )
    db.add(group)
    db.flush()
    for position, item_id in enumerate(item_ids):
        db.add(WorkoutRoutineGroupMember668(
            group_id=group.id, routine_item_id=item_id, position=position,
        ))
    db.commit()
    return services.flash_redirect(url, msg="Training group saved; no sets logged.")


@router.post("/workouts/routines/{routine_id}/groups/{group_id}/remove")
def remove_group668(
    routine_id: int, group_id: int,
    db: Session = Depends(get_scoped_db390),
):
    _routine668(db, routine_id)
    group = db.get(WorkoutRoutineGroup668, group_id)
    if group is None or group.routine_id != routine_id:
        raise HTTPException(404, "Training group not found")
    members = list(db.scalars(select(WorkoutRoutineGroupMember668)
        .where(WorkoutRoutineGroupMember668.group_id == group_id)))
    for member in members:
        db.delete(member)
    db.delete(group)
    db.commit()
    return services.flash_redirect(
        f"/workouts/routines/{routine_id}/schedule",
        msg="Training group removed; recorded workouts unchanged.",
    )
