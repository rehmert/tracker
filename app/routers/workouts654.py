"""Release 654 Workout: scoped, server-rendered Nautilus/free-weight logging.

HTML forms inherit Tracker's established session authentication, origin guard
and signed CSRF-token handling; QR values are never fetched from the network.
"""
from datetime import datetime
import math

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import services
from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..workout_models654 import KINDS654, WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from ..workout_models655 import (
    WorkoutRoutine655, WorkoutRoutineItem655, WorkoutSessionRoutine655,
)
from ..workout_models667 import WorkoutSetType667

router = APIRouter()


def active654(db: Session):
    return db.scalar(
        select(WorkoutSession654)
        .where(WorkoutSession654.completed_at.is_(None))
        .order_by(WorkoutSession654.started_at.desc(), WorkoutSession654.id.desc())
        .limit(1)
    )


@router.get("/workouts")
def workouts654(request: Request, db: Session = Depends(get_scoped_db390)):
    equipment = list(db.scalars(
        select(WorkoutEquipment654).order_by(
            WorkoutEquipment654.gym, WorkoutEquipment654.name, WorkoutEquipment654.id
        )
    ))
    active = active654(db)
    active_link = db.get(WorkoutSessionRoutine655, active.id) if active else None
    active_routine = (
        db.get(WorkoutRoutine655, active_link.routine_id)
        if active_link else None
    )
    routine_items = list(db.scalars(
        select(WorkoutRoutineItem655)
        .where(WorkoutRoutineItem655.routine_id == active_routine.id)
        .order_by(WorkoutRoutineItem655.position, WorkoutRoutineItem655.id)
    )) if active_routine else []
    routine_equipment_ids = [item.equipment_id for item in routine_items]
    rank = {equipment_id: i for i, equipment_id in enumerate(routine_equipment_ids)}
    equipment.sort(key=lambda item: (
        0, rank[item.id]
    ) if item.id in rank else (1, item.gym, item.name, item.id))
    routines = list(db.scalars(
        select(WorkoutRoutine655).order_by(
            WorkoutRoutine655.created_at.desc(), WorkoutRoutine655.id.desc()
        )
    ))
    rows = list(db.scalars(
        select(WorkoutSet654)
        .where(WorkoutSet654.session_id == active.id)
        .order_by(WorkoutSet654.performed_at.desc(), WorkoutSet654.id.desc())
    )) if active else []
    recent = list(db.scalars(
        select(WorkoutSession654)
        .order_by(WorkoutSession654.started_at.desc(), WorkoutSession654.id.desc())
        .limit(8)
    ))
    # Routine navigation uses only the current scoped workout's logged sets.
    logged_ids = {entry.equipment_id for entry in rows}
    counts_this_session = {
        item.id: sum(entry.equipment_id == item.id for entry in rows)
        for item in equipment
    }
    next_machine = {
        machine_id: routine_equipment_ids[index + 1]
        for index, machine_id in enumerate(routine_equipment_ids[:-1])
    }
    latest = {
        item.id: db.scalar(
            select(WorkoutSet654)
            .where(WorkoutSet654.equipment_id == item.id)
            .order_by(WorkoutSet654.performed_at.desc(), WorkoutSet654.id.desc())
            .limit(1)
        )
        for item in equipment
    }
    return render(
        request, "workouts654.html", equipment=equipment, active=active,
        rows=rows, recent=recent, latest=latest, kinds=KINDS654,
        equipment_names={item.id: item.name for item in equipment},
        routines=routines, active_routine=active_routine,
        routine_equipment_ids=set(routine_equipment_ids),
        first_routine_equipment_id=(
            routine_equipment_ids[0] if routine_equipment_ids else None
        ),
        next_machine=next_machine, counts_this_session=counts_this_session,
        routine_logged_count=len(logged_ids.intersection(routine_equipment_ids)),
        routine_total=len(routine_equipment_ids),
    )


@router.post("/workouts/equipment")
def create_equipment654(
    name: str = Form(""), kind: str = Form("selectorized"),
    gym: str = Form("Merritt Athletic Club - Eldersburg"),
    manufacturer: str = Form(""), model: str = Form(""),
    qr_value: str = Form(""), seat_setting: str = Form(""),
    setup_notes: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    name, gym, qr = name.strip(), gym.strip(), qr_value.strip() or None
    if not name or len(name) > 140 or not gym or len(gym) > 140:
        return services.flash_redirect("/workouts", err="Enter a machine name and gym, up to 140 characters.")
    if kind not in KINDS654:
        return services.flash_redirect("/workouts", err="Invalid equipment type.")
    if (len(manufacturer) > 100 or len(model) > 140 or
            len(seat_setting) > 80 or len(setup_notes) > 1000 or
            (qr and len(qr) > 1024)):
        return services.flash_redirect("/workouts", err="One or more fields are too long.")
    item = WorkoutEquipment654(
        name=name, gym=gym, kind=kind, manufacturer=manufacturer.strip(),
        model=model.strip(), qr_value=qr, seat_setting=seat_setting.strip(),
        setup_notes=setup_notes.strip(),
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return services.flash_redirect("/workouts", err="That QR code is already assigned to equipment.")
    return services.flash_redirect("/workouts", msg="Equipment saved.")


@router.post("/workouts/equipment/{equipment_id}/settings")
def update_settings654(
    equipment_id: int, seat_setting: str = Form(""), setup_notes: str = Form(""),
    qr_value: str = Form(""), db: Session = Depends(get_scoped_db390),
):
    machine = db.get(WorkoutEquipment654, equipment_id)
    if machine is None:
        raise HTTPException(404, "Equipment not found")
    qr = qr_value.strip() or None
    if len(seat_setting) > 80 or len(setup_notes) > 1000 or (qr and len(qr) > 1024):
        return services.flash_redirect("/workouts", err="Settings exceed the allowed length.")
    machine.seat_setting, machine.setup_notes, machine.qr_value = (
        seat_setting.strip(), setup_notes.strip(), qr
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return services.flash_redirect("/workouts", err="QR code belongs to another machine.")
    return services.flash_redirect("/workouts", msg="Machine settings saved.")


@router.get("/workouts/qr")
def lookup_qr654(code: str = "", db: Session = Depends(get_scoped_db390)):
    code = code.strip()
    if not code or len(code) > 1024:
        return services.flash_redirect("/workouts", err="Enter a valid QR code.")
    machine = db.scalar(select(WorkoutEquipment654).where(WorkoutEquipment654.qr_value == code))
    if machine is None:
        return services.flash_redirect("/workouts", err="QR code not mapped. Add it to the equipment catalog.")
    return services.flash_redirect(f"/workouts?machine={machine.id}", msg=f"Matched {machine.name}.")


@router.post("/workouts/start")
def start654(db: Session = Depends(get_scoped_db390)):
    if active654(db) is not None:
        return services.flash_redirect("/workouts", msg="Resumed active workout.")
    db.add(WorkoutSession654(started_at=datetime.now()))
    db.commit()
    return services.flash_redirect("/workouts", msg="Workout started.")


@router.post("/workouts/sets")
def add_set654(
    equipment_id: int = Form(...), weight_lb: float = Form(...),
    reps: int = Form(...), effort: str = Form(""),
    db: Session = Depends(get_scoped_db390),
    set_type: str = "working",
):
    workout = active654(db)
    if workout is None:
        return services.flash_redirect("/workouts", err="Start a workout before logging sets.")
    if set_type not in ("working", "warmup"):
        return services.flash_redirect("/workouts", err="Unknown recorded set type.")
    if db.get(WorkoutEquipment654, equipment_id) is None:
        raise HTTPException(404, "Equipment not found")
    if not math.isfinite(weight_lb) or not (0 <= weight_lb <= 2000):
        return services.flash_redirect("/workouts", err="Weight must be between 0 and 2,000 lb.")
    if not (1 <= reps <= 200):
        return services.flash_redirect("/workouts", err="Repetitions must be 1 to 200.")
    value = None
    if effort.strip():
        try:
            value = int(effort)
        except ValueError:
            return services.flash_redirect("/workouts", err="Effort must be 1 to 10.")
        if not (1 <= value <= 10):
            return services.flash_redirect("/workouts", err="Effort must be 1 to 10.")
    entry = WorkoutSet654(
        session_id=workout.id, equipment_id=equipment_id,
        weight_lb=weight_lb, reps=reps, effort=value,
    )
    db.add(entry)
    if set_type == "warmup":
        # Annotate in the SAME transaction as the actual set. A missing
        # annotation always means a backward-compatible working set.
        db.flush()
        db.add(WorkoutSetType667(set_id=entry.id, set_type="warmup"))
    db.commit()
    return services.flash_redirect(f"/workouts?machine={equipment_id}", msg="Set recorded.")


@router.get("/workouts/sessions/{session_id}")
def workout_history654(
    session_id: int, request: Request, db: Session = Depends(get_scoped_db390),
):
    workout = db.get(WorkoutSession654, session_id)
    if workout is None:
        raise HTTPException(404, "Workout not found")
    rows = list(db.scalars(
        select(WorkoutSet654)
        .where(WorkoutSet654.session_id == session_id)
        .order_by(WorkoutSet654.performed_at.asc(), WorkoutSet654.id.asc())
    ))
    names = {
        item.id: item.name for item in db.scalars(select(WorkoutEquipment654))
    }
    return render(
        request, "workout_history654.html",
        workout=workout, rows=rows, names=names,
    )


@router.post("/workouts/finish")
def finish654(db: Session = Depends(get_scoped_db390)):
    active = active654(db)
    if active is None:
        return services.flash_redirect("/workouts", err="No workout in progress.")
    active.completed_at = datetime.now()
    db.commit()
    return services.flash_redirect("/workouts", msg="Workout completed.")
