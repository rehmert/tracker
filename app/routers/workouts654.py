"""Release 654 Workout: scoped, server-rendered Nautilus/free-weight logging.

HTML forms inherit Tracker's established session authentication, origin guard
and signed CSRF-token handling. Retired QR mappings remain stored unchanged.
"""
from collections import Counter
from datetime import datetime
from hashlib import sha256
import json
import math

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import services
from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..workout_models654 import KINDS654, WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from ..workout_models655 import (
    WorkoutRoutine655, WorkoutRoutineItem655, WorkoutSessionRoutine655,
)
from ..workout_models667 import WorkoutSetType667, WorkoutSessionTarget667
from ..workout_models668 import WorkoutEquipmentLoad668
from ..models import ChangeAudit

router = APIRouter()


def _equipment_version740(machine: WorkoutEquipment654) -> str:
    """Optimistic concurrency for identifying fields, excluding setup notes."""
    payload = [
        machine.id, machine.name, machine.gym, machine.kind,
        machine.manufacturer or "", machine.model or "",
    ]
    return sha256(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _equipment_links740(db: Session) -> dict[int, dict[str, int]]:
    """Compute logged/routine/target references in three grouped queries."""
    links: dict[int, dict[str, int]] = {}
    for key, model in (
        ("sets", WorkoutSet654),
        ("routines", WorkoutRoutineItem655),
        ("targets", WorkoutSessionTarget667),
    ):
        counts = db.execute(
            select(model.equipment_id, func.count())
            .group_by(model.equipment_id)
        )
        for equipment_id, count in counts:
            links.setdefault(equipment_id, {"sets": 0, "routines": 0, "targets": 0})[key] = count
    return links



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
    # Optional Release 667 kind annotations; unannotated historic sets are working.
    set_types667 = {
        value.set_id: value.set_type
        for value in db.scalars(
            select(WorkoutSetType667).where(
                WorkoutSetType667.set_id.in_([row.id for row in rows])
            )
        )
    } if rows else {}
    recent = list(db.scalars(
        select(WorkoutSession654)
        .order_by(WorkoutSession654.started_at.desc(), WorkoutSession654.id.desc())
        .limit(8)
    ))
    # Routine navigation uses only the current scoped workout's logged sets.
    logged_ids = {entry.equipment_id for entry in rows}
    # Count active sets once, rather than rescanning them for each machine.
    set_counts = Counter(entry.equipment_id for entry in rows)
    counts_this_session = {item.id: set_counts[item.id] for item in equipment}
    next_machine = {
        machine_id: routine_equipment_ids[index + 1]
        for index, machine_id in enumerate(routine_equipment_ids[:-1])
    }
    # One query for the most recent recorded set of each machine.
    # Preserve the prior performed_at DESC / id DESC tie-break.
    ranked = (
        select(
            WorkoutSet654.id.label("set_id"),
            func.row_number().over(
                partition_by=WorkoutSet654.equipment_id,
                order_by=(
                    WorkoutSet654.performed_at.desc(),
                    WorkoutSet654.id.desc(),
                ),
            ).label("set_rank"),
        )
        .subquery()
    )
    latest_by_equipment = {
        entry.equipment_id: entry
        for entry in db.scalars(
            select(WorkoutSet654)
            .join(ranked, WorkoutSet654.id == ranked.c.set_id)
            .where(ranked.c.set_rank == 1)
        )
    }
    # Jinja uses latest[id] even for machines with no prior sets.
    latest = {item.id: latest_by_equipment.get(item.id) for item in equipment}
    return render(
        request, "workouts654.html", equipment=equipment, active=active,
        rows=rows, recent=recent, latest=latest, kinds=KINDS654,
        set_types667=set_types667,
        equipment_names={item.id: item.name for item in equipment},
        routines=routines, active_routine=active_routine,
        routine_equipment_ids=set(routine_equipment_ids),
        first_routine_equipment_id=(
            routine_equipment_ids[0] if routine_equipment_ids else None
        ),
        next_machine=next_machine, counts_this_session=counts_this_session,
        routine_logged_count=len(logged_ids.intersection(routine_equipment_ids)),
        routine_total=len(routine_equipment_ids),
        equipment_versions740={item.id: _equipment_version740(item) for item in equipment},
        equipment_links740=_equipment_links740(db),
    )


@router.post("/workouts/equipment")
def create_equipment654(
    name: str = Form(""), kind: str = Form("selectorized"),
    gym: str = Form("Merritt Athletic Club - Eldersburg"),
    manufacturer: str = Form(""), model: str = Form(""),
    seat_setting: str = Form(""), setup_notes: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    name, gym = name.strip(), gym.strip()
    if not name or len(name) > 140 or not gym or len(gym) > 140:
        return services.flash_redirect("/workouts", err="Enter a machine name and gym, up to 140 characters.")
    if kind not in KINDS654:
        return services.flash_redirect("/workouts", err="Invalid equipment type.")
    if (len(manufacturer) > 100 or len(model) > 140 or
            len(seat_setting) > 80 or len(setup_notes) > 1000):
        return services.flash_redirect("/workouts", err="One or more fields are too long.")
    item = WorkoutEquipment654(
        name=name, gym=gym, kind=kind, manufacturer=manufacturer.strip(),
        model=model.strip(), seat_setting=seat_setting.strip(),
        setup_notes=setup_notes.strip(),
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return services.flash_redirect("/workouts", err="Equipment could not be saved.")
    return services.flash_redirect("/workouts", msg="Equipment saved.")


@router.post("/workouts/equipment/{equipment_id}/edit")
def edit_equipment740(
    equipment_id: int, version: str = Form(""),
    name: str = Form(""), gym: str = Form(""),
    manufacturer: str = Form(""), model: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    """Edit identifying fields while preserving historical sets, type and QR."""
    machine = db.get(WorkoutEquipment654, equipment_id)
    if machine is None:
        raise HTTPException(404, "Equipment not found")
    target = f"/workouts?machine={equipment_id}"
    name, gym = name.strip(), gym.strip()
    manufacturer, model = manufacturer.strip(), model.strip()
    if not (1 <= len(name) <= 140 and 1 <= len(gym) <= 140):
        return services.flash_redirect(target, err="Machine name and gym must be 1–140 characters.")
    if len(manufacturer) > 100 or len(model) > 140:
        return services.flash_redirect(target, err="Manufacturer or model exceeds allowed length.")
    if version != _equipment_version740(machine):
        return services.flash_redirect(target, err="Equipment changed. Reload before saving.")
    before = {
        "name": machine.name, "gym": machine.gym,
        "manufacturer": machine.manufacturer or "", "model": machine.model or "",
    }
    after = {"name": name, "gym": gym, "manufacturer": manufacturer, "model": model}
    if before == after:
        return services.flash_redirect(target, msg="Equipment unchanged.")
    machine.name, machine.gym = name, gym
    machine.manufacturer, machine.model = manufacturer, model
    db.add(ChangeAudit(
        entity_type="workout_equipment", entity_id=equipment_id,
        action="edit", before_json=json.dumps(before, ensure_ascii=False),
        after_json=json.dumps(after, ensure_ascii=False),
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return services.flash_redirect(target, err="Equipment could not be updated.")
    return services.flash_redirect(target, msg="Equipment updated; workout history retained.")


@router.post("/workouts/equipment/{equipment_id}/delete")
def delete_equipment740(
    equipment_id: int, version: str = Form(""),
    confirm_delete: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    """Delete only equipment with zero sets, routine links or session targets."""
    machine = db.get(WorkoutEquipment654, equipment_id)
    if machine is None:
        raise HTTPException(404, "Equipment not found")
    target = f"/workouts?machine={equipment_id}"
    if confirm_delete != "delete":
        return services.flash_redirect(target, err="Confirm equipment deletion.")
    if version != _equipment_version740(machine):
        return services.flash_redirect(target, err="Equipment changed. Reload before deleting.")
    refs = _equipment_links740(db).get(equipment_id, {})
    if any(refs.values()):
        return services.flash_redirect(
            target, err="Equipment is used by sets, routines or workout targets; deletion blocked."
        )
    before = {
        "name": machine.name, "gym": machine.gym, "kind": machine.kind,
        "manufacturer": machine.manufacturer or "", "model": machine.model or "",
        "had_qr_mapping": bool(machine.qr_value),
        "seat_setting": machine.seat_setting or "",
        "setup_notes": machine.setup_notes or "",
    }
    # Load interpretation is dependent equipment metadata, never a recorded set.
    load_info = db.get(WorkoutEquipmentLoad668, equipment_id)
    if load_info is not None:
        db.delete(load_info)
    db.add(ChangeAudit(
        entity_type="workout_equipment", entity_id=equipment_id,
        action="delete", before_json=json.dumps(before, ensure_ascii=False),
        after_json="{}",
    ))
    db.delete(machine)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return services.flash_redirect(target, err="Equipment has linked records; deletion blocked.")
    return services.flash_redirect("/workouts", msg="Unused equipment deleted; audit preserved.")


@router.post("/workouts/equipment/{equipment_id}/settings")
def update_settings654(
    equipment_id: int, seat_setting: str = Form(""), setup_notes: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    machine = db.get(WorkoutEquipment654, equipment_id)
    if machine is None:
        raise HTTPException(404, "Equipment not found")
    if len(seat_setting) > 80 or len(setup_notes) > 1000:
        return services.flash_redirect("/workouts", err="Settings exceed the allowed length.")
    # Preserve legacy QR data; the QR feature has been retired without a data migration.
    machine.seat_setting, machine.setup_notes = seat_setting.strip(), setup_notes.strip()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return services.flash_redirect("/workouts", err="Machine settings could not be saved.")
    return services.flash_redirect("/workouts", msg="Machine settings saved.")



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
