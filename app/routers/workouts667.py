"""Release 667: authenticated, database-backed workout program configuration.

All writes use existing app-wide auth/origin/CSRF protections, are restricted
to the caller's scoped SQLite session, and cannot edit frozen workout goals.
"""
from __future__ import annotations

import json
from fastapi.responses import Response
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import services
from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..workout_models655 import WorkoutRoutine655, WorkoutRoutineItem655
from ..workout_models667 import WorkoutRoutineConfig667, WorkoutRoutineTarget667
from ..workout_program667 import REST_CHOICES667, parse_goal667, rest667
from ..workout_csv668 import parse_routine_csv668, render_routine_csv668
from .workouts665 import routine_plan_data665

router = APIRouter()
MAX_IMPORT_BYTES667 = 16000


def _routine667(db: Session, routine_id: int):
    routine = db.get(WorkoutRoutine655, routine_id)
    if routine is None:
        raise HTTPException(404, "Routine not found")
    return routine


def _item667(db: Session, routine_id: int, item_id: int):
    _routine667(db, routine_id)
    item = db.get(WorkoutRoutineItem655, item_id)
    if item is None or item.routine_id != routine_id:
        raise HTTPException(404, "Exercise not found in this routine")
    return item


def _program_url667(routine_id: int):
    return f"/workouts/routines/{routine_id}/program"


@router.get("/workouts/routines/{routine_id}/program")
def program667(routine_id: int, request: Request,
               db: Session = Depends(get_scoped_db390)):
    data = routine_plan_data665(db, routine_id)
    targets = {
        row["item"].id: db.get(WorkoutRoutineTarget667, row["item"].id)
        for row in data["rows"]
    }
    config = db.get(WorkoutRoutineConfig667, routine_id)
    return render(
        request, "workout_program667.html", **data, targets=targets,
        default_rest=config.rest_seconds if config else 90,
        rest_choices=REST_CHOICES667,
    )


@router.get("/workouts/routines/{routine_id}/program/export.csv")
def export_program_csv668(routine_id: int, db: Session = Depends(get_scoped_db390)):
    """Export future program rows; never include actual workout history."""
    _routine667(db, routine_id)
    items = list(db.scalars(
        select(WorkoutRoutineItem655)
        .where(WorkoutRoutineItem655.routine_id == routine_id)
        .order_by(WorkoutRoutineItem655.position, WorkoutRoutineItem655.id)
    ))
    rows = []
    for item in items:
        goal = db.get(WorkoutRoutineTarget667, item.id)
        rows.append(dict(
            routine_item_id=item.id,
            sets=goal.target_sets if goal and goal.target_sets is not None else "",
            reps=goal.target_reps if goal and goal.target_reps is not None else "",
            weight_lb=goal.target_weight_lb if goal and goal.target_weight_lb is not None else "",
            rest_seconds=goal.rest_seconds if goal and goal.rest_seconds is not None else "",
            setup_note=goal.setup_note if goal else "",
        ))
    return Response(
        content=render_routine_csv668(rows).encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition":
                 f'attachment; filename="tracker-routine-{routine_id}-plan.csv"'},
    )


@router.post("/workouts/routines/{routine_id}/program/import.csv")
def import_program_csv668(
    routine_id: int, csv_text: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    """Validate all rows before a single atomic database commit."""
    _routine667(db, routine_id)
    url = _program_url667(routine_id)
    known = set(db.scalars(
        select(WorkoutRoutineItem655.id).where(
            WorkoutRoutineItem655.routine_id == routine_id
        )
    ))
    try:
        rows = parse_routine_csv668(csv_text, known)
    except ValueError as exc:
        return services.flash_redirect(url, err=str(exc))
    for row in rows:
        item_id = row["routine_item_id"]
        target = db.get(WorkoutRoutineTarget667, item_id)
        if target is None:
            target = WorkoutRoutineTarget667(routine_item_id=item_id)
            db.add(target)
        target.target_sets = row["target_sets"]
        target.target_reps = row["target_reps"]
        target.target_weight_lb = row["target_weight_lb"]
        target.rest_seconds = row["rest_seconds"]
        target.setup_note = row["setup_note"]
        target.updated_at = datetime.now()
    db.commit()
    return services.flash_redirect(
        url, msg=f"Imported {len(rows)} future routine exercise plans.",
    )


@router.post("/workouts/routines/{routine_id}/program/rest")
def save_rest667(
    routine_id: int, rest_seconds: str = Form("90"),
    db: Session = Depends(get_scoped_db390),
):
    _routine667(db, routine_id)
    url = _program_url667(routine_id)
    try:
        seconds = rest667(rest_seconds)
    except ValueError as exc:
        return services.flash_redirect(url, err=str(exc))
    config = db.get(WorkoutRoutineConfig667, routine_id)
    if config is None:
        config = WorkoutRoutineConfig667(routine_id=routine_id)
        db.add(config)
    config.rest_seconds = seconds
    db.commit()
    return services.flash_redirect(url, msg="Routine rest interval updated.")


@router.post("/workouts/routines/{routine_id}/program/items/{item_id}")
def save_item667(
    routine_id: int, item_id: int,
    target_sets: str = Form(""), target_reps: str = Form(""),
    target_weight_lb: str = Form(""), rest_seconds: str = Form(""),
    setup_note: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    _item667(db, routine_id, item_id)
    url = _program_url667(routine_id)
    try:
        sets, reps, pounds = parse_goal667(
            target_sets, target_reps, target_weight_lb,
        )
        seconds = rest667(rest_seconds, optional=True)
        note = setup_note.strip()
        if len(note) > 1000:
            raise ValueError("Exercise setup notes must be 1,000 characters or fewer.")
    except ValueError as exc:
        return services.flash_redirect(url, err=str(exc))
    target = db.get(WorkoutRoutineTarget667, item_id)
    if target is None:
        target = WorkoutRoutineTarget667(routine_item_id=item_id)
        db.add(target)
    target.target_sets, target.target_reps, target.target_weight_lb = (
        sets, reps, pounds,
    )
    target.rest_seconds, target.setup_note, target.updated_at = (
        seconds, note, datetime.now(),
    )
    db.commit()
    return services.flash_redirect(
        url, msg="Persistent exercise targets and notes saved.",
    )


@router.post("/workouts/routines/{routine_id}/program/import")
def import_browser667(
    routine_id: int, targets_json: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    """Explicit migration of complete, validated Release 665 browser plans.

    Never trusts caller item IDs without looking them up in the routine.
    Import overwrites only target numbers, preserving notes and rest settings.
    """
    _routine667(db, routine_id)
    url = _program_url667(routine_id)
    if not targets_json or len(targets_json) > MAX_IMPORT_BYTES667:
        return services.flash_redirect(url, err="No valid browser plan to import.")
    try:
        doc = json.loads(targets_json)
        if (not isinstance(doc, dict) or doc.get("version") != 1 or
                not isinstance(doc.get("targets"), dict)):
            raise ValueError("Unrecognized browser plan format.")
        uploaded = doc["targets"]
        items = {
            str(item.id): item for item in db.scalars(
                select(WorkoutRoutineItem655).where(
                    WorkoutRoutineItem655.routine_id == routine_id,
                )
            )
        }
        if not (1 <= len(uploaded) <= 30) or not set(uploaded) <= set(items):
            raise ValueError("Browser plan includes unknown routine exercises.")
        parsed = {}
        for item_key, value in uploaded.items():
            if not isinstance(value, dict):
                raise ValueError("Malformed browser exercise target.")
            fields = tuple(value.get(k, "") for k in ("sets", "reps", "weight"))
            if any(not isinstance(v, str) for v in fields):
                raise ValueError("Malformed browser target number.")
            parsed[item_key] = parse_goal667(*fields)
            if parsed[item_key][0] is None:
                raise ValueError("All imported goals require sets, reps, and weight.")
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return services.flash_redirect(url, err=str(exc))

    for key, (sets, reps, pounds) in parsed.items():
        item_id = items[key].id
        existing = db.get(WorkoutRoutineTarget667, item_id)
        if existing is None:
            existing = WorkoutRoutineTarget667(routine_item_id=item_id)
            db.add(existing)
        existing.target_sets = sets
        existing.target_reps = reps
        existing.target_weight_lb = pounds
        existing.updated_at = datetime.now()
    db.commit()
    return services.flash_redirect(
        url, msg=f"Imported {len(parsed)} browser goals to Tracker. Previous saved targets were replaced for those exercises.",
    )
