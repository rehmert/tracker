"""Release 668: authenticated, user-scoped routine scheduling and group plans.

Schedules represent intentions only, not fabricated workout sessions.
Superset/circuit groups are planning metadata; sets are still logged manually
through validated existing routes. No automatic sets are created.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import math
import re
import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .. import services
from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..workout_models655 import WorkoutRoutine655, WorkoutRoutineItem655
from ..workout_models654 import WorkoutSet654, WorkoutSession654, WorkoutEquipment654
from ..workout_models667 import WorkoutSetType667
from ..workout_models668 import (
    WorkoutRoutineSchedule668, WorkoutRoutineGroup668,
    WorkoutRoutineGroupMember668, WorkoutSetCorrection668,
    WorkoutOfflineReceipt668, WorkoutEquipmentLoad668,
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
    return [
        day for n in range(horizon)
        if (day := today + timedelta(days=n)) >= start
        and day.weekday() in selected
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


@router.get("/workouts/sessions/{session_id}/correct")
def correction_page668(
    session_id: int, request: Request,
    db: Session = Depends(get_scoped_db390),
):
    session = db.get(WorkoutSession654, session_id)
    if session is None:
        raise HTTPException(404, "Workout not found")
    recorded = list(db.scalars(
        select(WorkoutSet654).where(WorkoutSet654.session_id == session_id)
        .order_by(WorkoutSet654.performed_at, WorkoutSet654.id)
    ))
    names = {
        row.equipment_id: (
            db.get(WorkoutEquipment654, row.equipment_id).name
            if db.get(WorkoutEquipment654, row.equipment_id)
            else "Unknown equipment"
        ) for row in recorded
    }
    kinds = {
        row.set_id: row.set_type for row in db.scalars(
            select(WorkoutSetType667)
            .where(WorkoutSetType667.set_id.in_([r.id for r in recorded]))
        )
    } if recorded else {}
    changes = list(db.scalars(
        select(WorkoutSetCorrection668)
        .join(WorkoutSet654, WorkoutSet654.id == WorkoutSetCorrection668.set_id)
        .where(WorkoutSet654.session_id == session_id)
        .order_by(WorkoutSetCorrection668.corrected_at.desc(),
                  WorkoutSetCorrection668.id.desc())
    ))
    return render(request, "workout_corrections668.html", session=session,
                  recorded=recorded, names=names, kinds=kinds, changes=changes)


@router.post("/workouts/sessions/{session_id}/sets/{set_id}/correct")
def correct_recorded_set668(
    session_id: int, set_id: int,
    weight_lb: float = Form(...), reps: int = Form(...),
    effort: str = Form(""), set_type: str = Form("working"),
    reason: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    session = db.get(WorkoutSession654, session_id)
    row = db.get(WorkoutSet654, set_id)
    if session is None or row is None or row.session_id != session_id:
        raise HTTPException(404, "Workout set not found")
    url = f"/workouts/sessions/{session_id}/correct"
    if session.completed_at is None:
        return services.flash_redirect(url, err="Historical corrections require a completed workout.")
    reason = reason.strip()
    if (not math.isfinite(weight_lb) or not 0 <= weight_lb <= 2000
            or not 1 <= reps <= 200 or not 3 <= len(reason) <= 500
            or set_type not in ("working", "warmup")):
        return services.flash_redirect(url, err="Invalid correction values or reason (3–500 characters).")
    new_effort = None
    if effort.strip():
        if not effort.strip().isascii() or not effort.strip().isdecimal():
            return services.flash_redirect(url, err="Effort must be a whole number from 1 to 10.")
        new_effort = int(effort)
        if not 1 <= new_effort <= 10:
            return services.flash_redirect(url, err="Effort must be from 1 to 10.")
    existing_type = db.get(WorkoutSetType667, row.id)
    previous_type = existing_type.set_type if existing_type else "working"
    if (row.weight_lb, row.reps, row.effort, previous_type) == (
            weight_lb, reps, new_effort, set_type):
        return services.flash_redirect(url, err="No changes found; correction not recorded.")
    db.add(WorkoutSetCorrection668(
        set_id=row.id,
        old_weight_lb=row.weight_lb, new_weight_lb=weight_lb,
        old_reps=row.reps, new_reps=reps,
        old_effort=row.effort, new_effort=new_effort,
        old_type=previous_type, new_type=set_type, reason=reason,
    ))
    row.weight_lb, row.reps, row.effort = weight_lb, reps, new_effort
    if set_type == "working":
        if existing_type is not None:
            db.delete(existing_type)
    elif existing_type is None:
        db.add(WorkoutSetType667(set_id=row.id, set_type="warmup"))
    else:
        existing_type.set_type = "warmup"
    db.commit()
    return services.flash_redirect(
        url, msg="Recorded set corrected; before/after audit retained.",
    )


@router.post("/workouts/sessions/{session_id}/reuse-as-routine")
def reuse_session_as_routine668(
    session_id: int, db: Session = Depends(get_scoped_db390),
):
    """Copy the exercise sequence, NOT completed sets or inferred load targets."""
    workout = db.get(WorkoutSession654, session_id)
    if workout is None:
        raise HTTPException(404, "Workout not found")
    if workout.completed_at is None:
        return services.flash_redirect(
            f"/workouts/sessions/{session_id}/review",
            err="Only completed workouts can be reused as routines.",
        )
    sets = list(db.scalars(select(WorkoutSet654)
        .where(WorkoutSet654.session_id == session_id)
        .order_by(WorkoutSet654.performed_at, WorkoutSet654.id)))
    equipment_ids = list(dict.fromkeys(row.equipment_id for row in sets))
    if not equipment_ids:
        return services.flash_redirect(
            f"/workouts/sessions/{session_id}/review",
            err="The workout has no recorded exercises to copy.",
        )
    if len(equipment_ids) > 30:
        return services.flash_redirect(
            f"/workouts/sessions/{session_id}/review",
            err="Cannot create a routine with more than 30 exercises.",
        )
    new = WorkoutRoutine655(name=f"Workout {workout.started_at:%Y-%m-%d} (Copy)")
    db.add(new)
    db.flush()
    for position, equipment_id in enumerate(equipment_ids):
        db.add(WorkoutRoutineItem655(
            routine_id=new.id, equipment_id=equipment_id, position=position,
        ))
    db.commit()
    return services.flash_redirect(
        f"/workouts/routines/{new.id}",
        msg="Workout exercise order copied as a new routine. No historical sets were copied.",
    )


LOAD_MODES668 = {
    "stack": "Stack displayed total (lb)",
    "total_plates": "Total loaded plates (lb)",
    "per_side": "Plates on ONE side (lb)",
    "pair_total": "Total for dumbbell pair (lb)",
    "bodyweight_added": "Added resistance only (lb)",
}


@router.post("/workouts/equipment/{equipment_id}/load")
def save_load_semantics668(
    equipment_id: int, load_mode: str = Form("stack"),
    multiplier: float = Form(1.0), offset_lb: float = Form(0.0),
    note: str = Form(""), db: Session = Depends(get_scoped_db390),
):
    machine = db.get(WorkoutEquipment654, equipment_id)
    if machine is None:
        raise HTTPException(404, "Equipment not found")
    clean_note = note.strip()
    if (load_mode not in LOAD_MODES668 or not math.isfinite(multiplier)
            or not 0 < multiplier <= 10 or not math.isfinite(offset_lb)
            or not 0 <= offset_lb <= 500 or len(clean_note) > 500):
        return services.flash_redirect(
            f"/workouts/quick?machine={equipment_id}", err="Invalid equipment load settings.",
        )
    config = db.get(WorkoutEquipmentLoad668, equipment_id)
    if config is None:
        config = WorkoutEquipmentLoad668(equipment_id=equipment_id)
        db.add(config)
    config.load_mode = load_mode
    config.multiplier = multiplier
    config.offset_lb = offset_lb
    config.note = clean_note
    config.updated_at = datetime.now()
    db.commit()
    return services.flash_redirect(
        f"/workouts/quick?machine={equipment_id}",
        msg="Load input settings saved for future sets; historical loads remain unchanged.",
    )


@router.post("/workouts/quick/offline-sync")
def sync_offline_set668(
    session_id: int = Form(...), equipment_id: int = Form(...),
    client_key: str = Form(...), weight_lb: float = Form(...),
    reps: int = Form(...), effort: str = Form(""),
    set_type: str = Form("working"),
    db: Session = Depends(get_scoped_db390),
):
    """Authenticated idempotent single-action sync; UUID logs once.

    Client never supplies timestamps, user IDs or database paths. Drafts can
    sync only to their original still-active workout in the scoped workspace.
    """
    from .workouts654 import active654
    try:
        if len(client_key) != 36:
            raise ValueError("UUID must be canonical length")
        key = str(UUID(client_key))
    except (ValueError, AttributeError):
        raise HTTPException(400, "Invalid offline action identifier")
    if key != client_key.lower():
        raise HTTPException(400, "Noncanonical offline action identifier")
    fingerprint = hashlib.sha256((
        f"{session_id}|{equipment_id}|{weight_lb:.12g}|{reps}|"
        f"{effort.strip()}|{set_type}"
    ).encode("utf-8")).hexdigest()
    existing = db.scalar(select(WorkoutOfflineReceipt668)
        .where(WorkoutOfflineReceipt668.client_key == key))
    if existing:
        if existing.session_id != session_id or existing.payload_sha256 != fingerprint:
            raise HTTPException(409, "Offline UUID reused with different set data")
        return JSONResponse({"ok": True, "duplicate": True, "set_id": existing.set_id,
                             "deleted": existing.set_id is None})
    active = active654(db)
    if active is None or active.id != session_id:
        raise HTTPException(409, "Original workout is no longer active; nothing was synchronized")
    if db.get(WorkoutEquipment654, equipment_id) is None:
        raise HTTPException(404, "Equipment not found")
    if (set_type not in ("working", "warmup")
            or not math.isfinite(weight_lb) or not 0 <= weight_lb <= 2000
            or not 1 <= reps <= 200):
        raise HTTPException(422, "Invalid actual set values")
    value = None
    if effort.strip():
        if not effort.isascii() or not effort.isdecimal() or not 1 <= int(effort) <= 10:
            raise HTTPException(422, "Effort must be 1–10")
        value = int(effort)
    recorded = WorkoutSet654(
        session_id=active.id, equipment_id=equipment_id,
        weight_lb=weight_lb, reps=reps, effort=value,
        performed_at=datetime.now(),
    )
    db.add(recorded)
    db.flush()
    if set_type == "warmup":
        db.add(WorkoutSetType667(set_id=recorded.id, set_type="warmup"))
    db.add(WorkoutOfflineReceipt668(
        client_key=key, payload_sha256=fingerprint,
        session_id=active.id, set_id=recorded.id,
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        receipt = db.scalar(select(WorkoutOfflineReceipt668)
            .where(WorkoutOfflineReceipt668.client_key == key))
        if (receipt is None or receipt.session_id != session_id
                or receipt.payload_sha256 != fingerprint):
            raise HTTPException(409, "Offline synchronization conflict")
        return JSONResponse({"ok": True, "duplicate": True, "set_id": receipt.set_id,
                             "deleted": receipt.set_id is None})
    return JSONResponse({"ok": True, "duplicate": False, "set_id": recorded.id})
