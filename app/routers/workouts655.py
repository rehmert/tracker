"""Release 655: saved workout routines and one-tap repeat of last actual set.

All requests inherit Tracker auth/CSRF policy and use get_scoped_db390.
Only exact known equipment IDs in the authorized database are accepted.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import services
from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from ..workout_models655 import (
    WorkoutRoutine655, WorkoutRoutineItem655, WorkoutSessionRoutine655,
)
from .workouts654 import active654
from ..workout_program667 import snapshots667
from ..workout_models667 import WorkoutSetType667

router = APIRouter()
MAX_ROUTINE_ITEMS655 = 30


def _routine(db: Session, routine_id: int) -> WorkoutRoutine655:
    routine = db.get(WorkoutRoutine655, routine_id)
    if routine is None:
        raise HTTPException(404, "Routine not found")
    return routine


def _items(db: Session, routine_id: int) -> list[WorkoutRoutineItem655]:
    return list(db.scalars(
        select(WorkoutRoutineItem655)
        .where(WorkoutRoutineItem655.routine_id == routine_id)
        .order_by(WorkoutRoutineItem655.position, WorkoutRoutineItem655.id)
    ))


def _routine_url(routine_id: int) -> str:
    return f"/workouts/routines/{routine_id}"


@router.get("/workouts/routines")
def routines_index655(request: Request, db: Session = Depends(get_scoped_db390)):
    routines = list(db.scalars(
        select(WorkoutRoutine655).order_by(
            WorkoutRoutine655.created_at.desc(), WorkoutRoutine655.id.desc()
        )
    ))
    return render(request, "workout_routines655.html", routines=routines)


@router.post("/workouts/routines")
def create_routine655(
    name: str = Form(""), db: Session = Depends(get_scoped_db390),
):
    name = name.strip()
    if not name or len(name) > 120:
        return services.flash_redirect("/workouts/routines", err="Routine name must contain 1–120 characters.")
    routine = WorkoutRoutine655(name=name)
    db.add(routine)
    db.commit()
    return services.flash_redirect(_routine_url(routine.id), msg="Routine created. Add equipment in workout order.")


@router.get("/workouts/routines/{routine_id}")
def routine_detail655(
    routine_id: int, request: Request, db: Session = Depends(get_scoped_db390),
):
    routine = _routine(db, routine_id)
    items = _items(db, routine_id)
    equipment = list(db.scalars(
        select(WorkoutEquipment654).order_by(WorkoutEquipment654.name, WorkoutEquipment654.id)
    ))
    names = {item.id: item.name for item in equipment}
    selected = {item.equipment_id for item in items}
    active = active654(db)
    active_link = db.get(WorkoutSessionRoutine655, active.id) if active else None
    can_resume = active_link is not None and active_link.routine_id == routine_id
    return render(
        request, "workout_routine_detail655.html",
        routine=routine, items=items, names=names,
        available=[item for item in equipment if item.id not in selected],
        active=active, can_resume=can_resume, maximum=MAX_ROUTINE_ITEMS655,
    )


@router.post("/workouts/routines/{routine_id}/equipment")
def add_routine_item655(
    routine_id: int, equipment_id: int = Form(...),
    db: Session = Depends(get_scoped_db390),
):
    _routine(db, routine_id)
    target = _routine_url(routine_id)
    if db.get(WorkoutEquipment654, equipment_id) is None:
        raise HTTPException(404, "Equipment not found")
    items = _items(db, routine_id)
    if len(items) >= MAX_ROUTINE_ITEMS655:
        return services.flash_redirect(target, err="Limit of 30 exercises per routine.")
    if any(item.equipment_id == equipment_id for item in items):
        return services.flash_redirect(target, err="Machine already belongs to this routine.")
    next_position = max((item.position for item in items), default=-1) + 1
    db.add(WorkoutRoutineItem655(
        routine_id=routine_id, equipment_id=equipment_id, position=next_position,
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return services.flash_redirect(target, err="Unable to add duplicate equipment.")
    return services.flash_redirect(target, msg="Equipment added to routine.")


@router.post("/workouts/routines/{routine_id}/items/{item_id}/move")
def move_routine_item655(
    routine_id: int, item_id: int, direction: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    _routine(db, routine_id)
    target = _routine_url(routine_id)
    if direction not in ("up", "down"):
        return services.flash_redirect(target, err="Invalid move direction.")
    items = _items(db, routine_id)
    index = next((i for i, item in enumerate(items) if item.id == item_id), None)
    if index is None:
        raise HTTPException(404, "Routine exercise not found")
    neighbor = index + (-1 if direction == "up" else 1)
    if not 0 <= neighbor < len(items):
        return services.flash_redirect(target, msg="Exercise already at the end.")
    items[index].position, items[neighbor].position = (
        items[neighbor].position, items[index].position
    )
    db.commit()
    return services.flash_redirect(target, msg="Exercise order updated.")


@router.post("/workouts/routines/{routine_id}/items/{item_id}/remove")
def remove_routine_item655(
    routine_id: int, item_id: int, db: Session = Depends(get_scoped_db390),
):
    _routine(db, routine_id)
    item = db.get(WorkoutRoutineItem655, item_id)
    if item is None or item.routine_id != routine_id:
        raise HTTPException(404, "Routine exercise not found")
    db.delete(item)
    db.commit()
    return services.flash_redirect(_routine_url(routine_id), msg="Exercise removed from routine.")


@router.post("/workouts/routines/{routine_id}/start")
def start_routine655(routine_id: int, db: Session = Depends(get_scoped_db390)):
    _routine(db, routine_id)
    items = _items(db, routine_id)
    target = _routine_url(routine_id)
    if not items:
        return services.flash_redirect(target, err="Add at least one exercise before starting.")
    active = active654(db)
    if active is not None:
        link = db.get(WorkoutSessionRoutine655, active.id)
        if link is not None and link.routine_id == routine_id:
            return services.flash_redirect(
                f"/workouts?machine={items[0].equipment_id}", msg="Routine resumed."
            )
        return services.flash_redirect(
            target, err="Finish the current workout before starting this routine."
        )
    workout = WorkoutSession654(started_at=datetime.now())
    db.add(workout)
    db.flush()
    db.add(WorkoutSessionRoutine655(session_id=workout.id, routine_id=routine_id))
    snapshots667(db, routine_id, workout.id)
    db.commit()
    return services.flash_redirect(
        f"/workouts?machine={items[0].equipment_id}", msg="Routine started."
    )


@router.post("/workouts/sets/repeat")
def repeat_last_set655(
    equipment_id: int = Form(...),
    source_set_id: int = Form(...),
    db: Session = Depends(get_scoped_db390),
):
    """Repeat one actual prior set with no caller-supplied load/repetition values.

    The source must still be the latest set for that exact equipment. This
    also rejects ordinary sequential double submits of the same repeat form.
    """
    workout = active654(db)
    if workout is None:
        return services.flash_redirect("/workouts", err="Start a workout first.")
    if db.get(WorkoutEquipment654, equipment_id) is None:
        raise HTTPException(404, "Equipment not found")
    last = db.scalar(
        select(WorkoutSet654)
        .where(WorkoutSet654.equipment_id == equipment_id)
        .order_by(WorkoutSet654.performed_at.desc(), WorkoutSet654.id.desc())
        .limit(1)
    )
    if last is None or last.id != source_set_id:
        return services.flash_redirect(
            f"/workouts?machine={equipment_id}",
            err="Previous set changed. Reload before repeating.",
        )
    repeated = WorkoutSet654(
        session_id=workout.id, equipment_id=equipment_id,
        weight_lb=last.weight_lb, reps=last.reps, effort=last.effort,
        performed_at=datetime.now(),
    )
    db.add(repeated)
    # A repeated warm-up must remain a warm-up, never silently become working.
    prior_kind = db.get(WorkoutSetType667, last.id)
    if prior_kind is not None and prior_kind.set_type == "warmup":
        db.flush()
        db.add(WorkoutSetType667(set_id=repeated.id, set_type="warmup"))
    db.commit()
    return services.flash_redirect(
        f"/workouts?machine={equipment_id}", msg="Previous set repeated."
    )
