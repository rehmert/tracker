"""Release 655: saved workout routines and one-tap repeat of last actual set.

All requests inherit Tracker auth/CSRF policy and use get_scoped_db390.
Only exact known equipment IDs in the authorized database are accepted.
"""
from datetime import datetime
import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import delete, func, or_, select
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
from ..workout_models667 import (
    WorkoutSetType667, WorkoutRoutineConfig667, WorkoutRoutineTarget667,
)
from ..workout_models668 import (
    WorkoutRoutineSchedule668, WorkoutRoutineGroup668, WorkoutRoutineGroupMember668,
)
from ..models import ChangeAudit

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
    used = dict(db.execute(
        select(WorkoutSessionRoutine655.routine_id, func.count())
        .group_by(WorkoutSessionRoutine655.routine_id)
    ).all())
    return render(request, "workout_routines655.html", routines=routines, used=used)


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


def _routine_sessions739(db: Session, routine_id: int) -> int:
    return db.scalar(select(func.count()).select_from(WorkoutSessionRoutine655).where(
        WorkoutSessionRoutine655.routine_id == routine_id
    )) or 0


@router.post("/workouts/routines/{routine_id}/rename")
def rename_routine739(
    routine_id: int, name: str = Form(""), db: Session = Depends(get_scoped_db390),
):
    """Change the name without rebuilding program or workout associations."""
    routine = _routine(db, routine_id)
    name = name.strip()
    if not 1 <= len(name) <= 120:
        return services.flash_redirect(_routine_url(routine_id), err="Routine name must contain 1–120 characters.")
    if routine.name != name:
        db.add(ChangeAudit(
            entity_type="workout_routine", entity_id=routine.id, action="edit",
            before_json=json.dumps({"name": routine.name}),
            after_json=json.dumps({"name": name}),
        ))
        routine.name = name
        db.commit()
    return services.flash_redirect(_routine_url(routine_id), msg="Routine renamed.")


@router.post("/workouts/routines/{routine_id}/delete")
def delete_routine739(
    routine_id: int, confirm_delete: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    """Delete a draft routine only; never unlink actual completed/active workouts.

    Retain historic session links and frozen workout snapshots by refusing
    deletion whenever a session references this routine. Otherwise remove
    scheduled plans, goals, grouping and equipment rows in FK-safe order.
    """
    routine = _routine(db, routine_id)
    target = _routine_url(routine_id)
    if confirm_delete != "delete":
        return services.flash_redirect(target, err="Confirm routine deletion.")
    if _routine_sessions739(db, routine_id):
        return services.flash_redirect(target, err="Routine has workout history. Keep it to preserve past sessions.")

    routine_items = select(WorkoutRoutineItem655.id).where(
        WorkoutRoutineItem655.routine_id == routine_id
    )
    groups = select(WorkoutRoutineGroup668.id).where(
        WorkoutRoutineGroup668.routine_id == routine_id
    )
    # Fail closed if corrupt legacy group-item associations cross routines.
    mismatched_group = db.scalar(
        select(WorkoutRoutineGroupMember668.id)
        .join(WorkoutRoutineGroup668,
              WorkoutRoutineGroupMember668.group_id == WorkoutRoutineGroup668.id)
        .join(WorkoutRoutineItem655,
              WorkoutRoutineGroupMember668.routine_item_id == WorkoutRoutineItem655.id)
        .where(or_(
            (WorkoutRoutineGroup668.routine_id == routine_id)
            & (WorkoutRoutineItem655.routine_id != routine_id),
            (WorkoutRoutineGroup668.routine_id != routine_id)
            & (WorkoutRoutineItem655.routine_id == routine_id),
        )).limit(1)
    )
    if mismatched_group is not None:
        return services.flash_redirect(target, err="Routine has conflicting group links; deletion blocked.")
    item_count = db.scalar(select(func.count()).select_from(WorkoutRoutineItem655).where(
        WorkoutRoutineItem655.routine_id == routine_id
    )) or 0
    try:
        db.execute(delete(WorkoutRoutineGroupMember668).where(
            WorkoutRoutineGroupMember668.group_id.in_(groups)
        ))
        db.execute(delete(WorkoutRoutineGroup668).where(
            WorkoutRoutineGroup668.routine_id == routine_id
        ))
        db.execute(delete(WorkoutRoutineTarget667).where(
            WorkoutRoutineTarget667.routine_item_id.in_(routine_items)
        ))
        db.execute(delete(WorkoutRoutineItem655).where(
            WorkoutRoutineItem655.routine_id == routine_id
        ))
        db.execute(delete(WorkoutRoutineSchedule668).where(
            WorkoutRoutineSchedule668.routine_id == routine_id
        ))
        db.execute(delete(WorkoutRoutineConfig667).where(
            WorkoutRoutineConfig667.routine_id == routine_id
        ))
        db.add(ChangeAudit(
            entity_type="workout_routine", entity_id=routine_id, action="delete",
            before_json=json.dumps({"name": routine.name, "exercises_deleted": item_count}),
            after_json="{}",
        ))
        db.delete(routine)
        db.commit()
    except IntegrityError:
        db.rollback()
        return services.flash_redirect(target, err="Routine has other linked records; deletion blocked.")
    return services.flash_redirect("/workouts/routines", msg="Unused routine permanently deleted; audit retained.")


@router.post("/workouts/routines/{routine_id}/items/{item_id}/substitute")
def substitute_routine_item668(
    routine_id: int, item_id: int, equipment_id: int = Form(...),
    db: Session = Depends(get_scoped_db390),
):
    """Replace a future routine machine without rewriting historical workouts."""
    target = _routine_url(routine_id)
    _routine(db, routine_id)
    item = db.get(WorkoutRoutineItem655, item_id)
    if item is None or item.routine_id != routine_id:
        raise HTTPException(404, "Routine item not found")
    replacement = db.get(WorkoutEquipment654, equipment_id)
    if replacement is None:
        raise HTTPException(404, "Equipment not found")
    if item.equipment_id == equipment_id:
        return services.flash_redirect(target, msg="No substitution needed.")
    # Existing active-session navigation must not shift during a workout.
    active = active654(db)
    link = db.get(WorkoutSessionRoutine655, active.id) if active else None
    if link is not None and link.routine_id == routine_id:
        return services.flash_redirect(target, err="Finish the active routine before changing machines.")
    occupied = db.scalar(select(WorkoutRoutineItem655.id).where(
        WorkoutRoutineItem655.routine_id == routine_id,
        WorkoutRoutineItem655.equipment_id == equipment_id,
    ))
    if occupied is not None:
        return services.flash_redirect(target, err="That machine is already in this routine.")
    from ..workout_models667 import WorkoutRoutineTarget667
    goal = db.get(WorkoutRoutineTarget667, item.id)
    if goal is not None:
        # Machine loads cannot be assumed equivalent. Preserve only
        # non-numeric setup/rest preferences; clear machine-specific goals.
        goal.target_sets = None
        goal.target_reps = None
        goal.target_weight_lb = None
        goal.setup_note = ""
        goal.updated_at = datetime.now()
    item.equipment_id = equipment_id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return services.flash_redirect(target, err="Substitution conflicts with this routine.")
    return services.flash_redirect(
        target, msg="Machine substituted. Set new goals for the replacement equipment.",
    )


@router.post("/workouts/routines/{routine_id}/duplicate")
def duplicate_routine668(
    routine_id: int, db: Session = Depends(get_scoped_db390),
):
    """Copy the editable program, never recorded sets or historical snapshots."""
    source = _routine(db, routine_id)
    items = _items(db, routine_id)
    from ..workout_models667 import WorkoutRoutineConfig667, WorkoutRoutineTarget667

    proposed = f"{source.name} (Copy)"
    if len(proposed) > 120:
        proposed = source.name[:113].rstrip() + " (Copy)"
    clone = WorkoutRoutine655(name=proposed)
    db.add(clone)
    db.flush()
    config = db.get(WorkoutRoutineConfig667, source.id)
    if config is not None:
        db.add(WorkoutRoutineConfig667(
            routine_id=clone.id, rest_seconds=config.rest_seconds,
        ))
    for item in items:
        new_item = WorkoutRoutineItem655(
            routine_id=clone.id, equipment_id=item.equipment_id,
            position=item.position,
        )
        db.add(new_item)
        db.flush()
        goal = db.get(WorkoutRoutineTarget667, item.id)
        if goal is not None:
            db.add(WorkoutRoutineTarget667(
                routine_item_id=new_item.id, target_sets=goal.target_sets,
                target_reps=goal.target_reps,
                target_weight_lb=goal.target_weight_lb,
                setup_note=goal.setup_note, rest_seconds=goal.rest_seconds,
            ))
    # Preserve future scheduling and grouping in cloned routines, remapping
    # all group members to the clone's NEW item IDs.
    from ..workout_models668 import (
        WorkoutRoutineSchedule668, WorkoutRoutineGroup668,
        WorkoutRoutineGroupMember668,
    )
    prior_schedule = db.get(WorkoutRoutineSchedule668, source.id)
    if prior_schedule is not None:
        db.add(WorkoutRoutineSchedule668(
            routine_id=clone.id, weekdays=prior_schedule.weekdays,
            start_on=prior_schedule.start_on, end_on=prior_schedule.end_on,
        ))
    old_members = list(db.scalars(
        select(WorkoutRoutineGroupMember668)
        .join(WorkoutRoutineGroup668,
              WorkoutRoutineGroup668.id == WorkoutRoutineGroupMember668.group_id)
        .where(WorkoutRoutineGroup668.routine_id == source.id)
    ))
    remap = {
        old.equipment_id: new.id
        for old, new in zip(items, list(db.scalars(
            select(WorkoutRoutineItem655).where(
                WorkoutRoutineItem655.routine_id == clone.id
            ).order_by(WorkoutRoutineItem655.position, WorkoutRoutineItem655.id)
        )))
    }
    for previous in db.scalars(
        select(WorkoutRoutineGroup668)
        .where(WorkoutRoutineGroup668.routine_id == source.id)
        .order_by(WorkoutRoutineGroup668.id)
    ):
        copied = WorkoutRoutineGroup668(
            routine_id=clone.id, group_name=previous.group_name,
            group_type=previous.group_type, rounds=previous.rounds,
        )
        db.add(copied)
        db.flush()
        for member in old_members:
            if member.group_id != previous.id:
                continue
            old_item = db.get(WorkoutRoutineItem655, member.routine_item_id)
            if old_item and old_item.equipment_id in remap:
                db.add(WorkoutRoutineGroupMember668(
                    group_id=copied.id,
                    routine_item_id=remap[old_item.equipment_id],
                    position=member.position,
                ))
    db.commit()
    return services.flash_redirect(
        _routine_url(clone.id),
        msg="Routine, schedule, groups and future goals duplicated; no recorded sets copied.",
    )


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
        linked_sessions=_routine_sessions739(db, routine_id),
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
