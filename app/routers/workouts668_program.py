"""Release 668: weekly training splits, groups, substitutions and reusable copies.

All handlers use Tracker's authenticated scoped user database, existing
POST CSRF/origin policy and explicit session/equipment ownership checks.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import re

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import services
from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from ..workout_models655 import WorkoutRoutine655, WorkoutRoutineItem655, WorkoutSessionRoutine655
from ..workout_models667 import WorkoutRoutineConfig667, WorkoutRoutineTarget667, WorkoutSetType667
from ..workout_models668 import (
    WorkoutRoutineGroup668, WorkoutSessionSubstitution668,
    WorkoutTrainingDay668,
)
from .workouts654 import active654
from .workouts655 import _routine, _items

router = APIRouter()
WEEKDAYS668 = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
GROUP668 = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,19}\Z")


def scheduled668(db: Session):
    return list(db.execute(
        select(WorkoutTrainingDay668, WorkoutRoutine655.name)
        .join(WorkoutRoutine655, WorkoutTrainingDay668.routine_id == WorkoutRoutine655.id)
        .order_by(WorkoutTrainingDay668.weekday, WorkoutRoutine655.name)
    ).all())


@router.get("/workouts/programs")
def schedule_page668(request: Request, db: Session = Depends(get_scoped_db390)):
    routines = list(db.scalars(
        select(WorkoutRoutine655).order_by(WorkoutRoutine655.name, WorkoutRoutine655.id)
    ))
    today = datetime.now().date()
    plans = scheduled668(db)
    next_scheduled = sorted(plans, key=lambda row: (
        (row[0].weekday - today.weekday()) % 7, row[1]
    ))
    schedules_by_day = {day: [] for day in range(7)}
    for slot, name in plans:
        schedules_by_day[slot.weekday].append((slot, name))
    return render(
        request, "workout_programs668.html", routines=routines,
        schedules=plans, schedules_by_day=schedules_by_day,
        next_scheduled=next_scheduled[:5],
        weekdays=WEEKDAYS668, today_weekday=today.weekday(),
        active=active654(db),
    )


@router.post("/workouts/programs/schedule")
def add_schedule668(
    weekday: int = Form(...), routine_id: int = Form(...),
    note: str = Form(""), db: Session = Depends(get_scoped_db390),
):
    url = "/workouts/programs"
    if not 0 <= weekday <= 6:
        return services.flash_redirect(url, err="Choose Monday through Sunday.")
    routine = db.get(WorkoutRoutine655, routine_id)
    if routine is None:
        raise HTTPException(404, "Routine not found")
    if len(note.strip()) > 120:
        return services.flash_redirect(url, err="Schedule notes must be 120 characters or fewer.")
    entry = db.scalar(select(WorkoutTrainingDay668).where(
        WorkoutTrainingDay668.weekday == weekday,
        WorkoutTrainingDay668.routine_id == routine_id,
    ))
    if entry is None:
        if db.scalar(select(func.count(WorkoutTrainingDay668.id))) >= 60:
            return services.flash_redirect(url, err="Maximum 60 recurring slots.")
        entry = WorkoutTrainingDay668(weekday=weekday, routine_id=routine_id)
        db.add(entry)
    entry.note = note.strip()
    db.commit()
    return services.flash_redirect(url, msg="Recurring training day saved.")


@router.post("/workouts/programs/schedule/{slot_id}/remove")
def remove_schedule668(slot_id: int, db: Session = Depends(get_scoped_db390)):
    slot = db.get(WorkoutTrainingDay668, slot_id)
    if slot is None:
        raise HTTPException(404, "Training slot not found")
    db.delete(slot)
    db.commit()
    return services.flash_redirect("/workouts/programs", msg="Training slot removed.")


@router.post("/workouts/routines/{routine_id}/groups/{item_id}")
def group_item668(
    routine_id: int, item_id: int,
    label: str = Form(""), mode: str = Form("superset"),
    db: Session = Depends(get_scoped_db390),
):
    _routine(db, routine_id)
    item = db.get(WorkoutRoutineItem655, item_id)
    if item is None or item.routine_id != routine_id:
        raise HTTPException(404, "Routine exercise not found")
    url = f"/workouts/routines/{routine_id}"
    label = label.strip()
    if label and (not GROUP668.fullmatch(label) or mode not in ("superset", "circuit")):
        return services.flash_redirect(url, err="Enter a short group label and Superset or Circuit.")
    current = db.get(WorkoutRoutineGroup668, item_id)
    if not label:
        if current:
            db.delete(current)
    else:
        if current is None:
            current = WorkoutRoutineGroup668(routine_item_id=item_id)
            db.add(current)
        current.label, current.mode = label, mode
    db.commit()
    return services.flash_redirect(url, msg="Exercise group saved.")


@router.post("/workouts/quick/substitution")
def substitute668(
    original_equipment_id: int = Form(...),
    alternate_equipment_id: int = Form(...),
    db: Session = Depends(get_scoped_db390),
):
    session = active654(db)
    if session is None:
        return services.flash_redirect("/workouts/quick", err="No active workout.")
    link = db.get(WorkoutSessionRoutine655, session.id)
    if link is None:
        return services.flash_redirect("/workouts/quick", err="Start a saved routine for substitutions.")
    routine_ids = set(db.scalars(
        select(WorkoutRoutineItem655.equipment_id).where(
            WorkoutRoutineItem655.routine_id == link.routine_id
        )
    ))
    if original_equipment_id not in routine_ids:
        raise HTTPException(404, "Original exercise not in active routine")
    url = f"/workouts/quick?machine={original_equipment_id}"
    previous = db.get(WorkoutSessionSubstitution668, (session.id, original_equipment_id))
    # Cannot rewrite substitution meaning once actual sets have been logged.
    locked_ids = {original_equipment_id}
    if previous is not None:
        locked_ids.add(previous.alternate_equipment_id)
    if db.scalar(select(WorkoutSet654.id).where(
        WorkoutSet654.session_id == session.id,
        WorkoutSet654.equipment_id.in_(locked_ids),
    ).limit(1)):
        return services.flash_redirect(url, err="Substitution is locked after recording a set on this exercise.")
    if alternate_equipment_id == 0:
        if previous is not None:
            db.delete(previous)
            db.commit()
        return services.flash_redirect(url, msg="Substitution cleared.")
    if (alternate_equipment_id in routine_ids or
            alternate_equipment_id == original_equipment_id or
            db.get(WorkoutEquipment654, alternate_equipment_id) is None):
        return services.flash_redirect(url, err="Choose a different existing machine outside this routine.")
    if db.scalar(select(WorkoutSet654.id).where(
        WorkoutSet654.session_id == session.id,
        WorkoutSet654.equipment_id == alternate_equipment_id,
    ).limit(1)):
        return services.flash_redirect(url, err="Alternate already has recorded sets in this session.")
    assigned = db.scalar(select(WorkoutSessionSubstitution668.session_id).where(
        WorkoutSessionSubstitution668.session_id == session.id,
        WorkoutSessionSubstitution668.alternate_equipment_id == alternate_equipment_id,
        WorkoutSessionSubstitution668.original_equipment_id != original_equipment_id,
    ).limit(1))
    if assigned is not None:
        return services.flash_redirect(url, err="Alternate already assigned to another exercise.")
    if previous is None:
        previous = WorkoutSessionSubstitution668(
            session_id=session.id, original_equipment_id=original_equipment_id,
            alternate_equipment_id=alternate_equipment_id,
        )
        db.add(previous)
    else:
        previous.alternate_equipment_id = alternate_equipment_id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return services.flash_redirect(url, err="Conflicting substitution. Reload and retry.")
    return services.flash_redirect(
        f"/workouts/quick?machine={alternate_equipment_id}",
        msg="Alternative machine selected. Its load is not considered equivalent to the original goal.",
    )


@router.post("/workouts/routines/{routine_id}/duplicate")
def duplicate_routine668(routine_id: int, db: Session = Depends(get_scoped_db390)):
    source = _routine(db, routine_id)
    items = _items(db, routine_id)
    if not items:
        return services.flash_redirect(
            f"/workouts/routines/{routine_id}", err="Add an exercise first."
        )
    name = ("Copy of " + source.name)[:120]
    copy = WorkoutRoutine655(name=name)
    db.add(copy)
    db.flush()
    config = db.get(WorkoutRoutineConfig667, routine_id)
    if config:
        db.add(WorkoutRoutineConfig667(routine_id=copy.id, rest_seconds=config.rest_seconds))
    for item in items:
        clone = WorkoutRoutineItem655(
            routine_id=copy.id, equipment_id=item.equipment_id, position=item.position
        )
        db.add(clone)
        db.flush()
        target = db.get(WorkoutRoutineTarget667, item.id)
        if target:
            db.add(WorkoutRoutineTarget667(
                routine_item_id=clone.id, target_sets=target.target_sets,
                target_reps=target.target_reps,
                target_weight_lb=target.target_weight_lb,
                setup_note=target.setup_note, rest_seconds=target.rest_seconds,
            ))
        group = db.get(WorkoutRoutineGroup668, item.id)
        if group:
            db.add(WorkoutRoutineGroup668(
                routine_item_id=clone.id, label=group.label, mode=group.mode,
            ))
    db.commit()
    return services.flash_redirect(
        f"/workouts/routines/{copy.id}", msg="Reusable routine copied. Review goals before training."
    )


@router.post("/workouts/sessions/{session_id}/duplicate")
def copy_completed_session668(session_id: int, db: Session = Depends(get_scoped_db390)):
    session = db.get(WorkoutSession654, session_id)
    if session is None:
        raise HTTPException(404, "Workout not found")
    if session.completed_at is None:
        return services.flash_redirect(
            f"/workouts/sessions/{session_id}", err="Finish the workout before copying."
        )
    rows = list(db.scalars(select(WorkoutSet654).where(
        WorkoutSet654.session_id == session_id,
    ).order_by(WorkoutSet654.performed_at, WorkoutSet654.id)))
    if not rows:
        return services.flash_redirect(
            f"/workouts/sessions/{session_id}", err="No actual sets to copy."
        )
    distinct = list(dict.fromkeys(row.equipment_id for row in rows))
    if len(distinct) > 30:
        return services.flash_redirect(
            f"/workouts/sessions/{session_id}", err="Cannot create a routine with over 30 exercises."
        )
    summary = defaultdict(list)
    for row in rows:
        kind = db.get(WorkoutSetType667, row.id)
        if kind is None or kind.set_type != "warmup":
            summary[row.equipment_id].append(row)
    routine = WorkoutRoutine655(
        name=("From " + session.started_at.strftime("%Y-%m-%d %H:%M"))[:120]
    )
    db.add(routine)
    db.flush()
    for position, machine_id in enumerate(distinct):
        item = WorkoutRoutineItem655(
            routine_id=routine.id, equipment_id=machine_id, position=position
        )
        db.add(item)
        db.flush()
        actual = summary[machine_id]
        if actual and len(actual) <= 20:
            last = actual[-1]
            db.add(WorkoutRoutineTarget667(
                routine_item_id=item.id, target_sets=len(actual),
                target_reps=last.reps, target_weight_lb=last.weight_lb,
                setup_note="Copied from actual working sets; review before using.",
            ))
    db.commit()
    return services.flash_redirect(
        f"/workouts/routines/{routine.id}/program",
        msg="Draft routine created from recorded workout. No sets were logged.",
    )
