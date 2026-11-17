"""Release 663: recorded-only Workout session review and finish delegation.

All reads use the authenticated user's established scoped SQLite session.
Finish & Review invokes the existing validated Release 654 finish function once;
it never duplicates session write logic, adds columns, or estimates strength.
"""
from __future__ import annotations

import csv
from io import StringIO
from fastapi.responses import Response

from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import services
from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from ..workout_models667 import WorkoutSessionTarget667
from ..workout_program667 import progress667
from .workouts654 import active654, finish654

router = APIRouter()


@router.get("/workouts/sessions/{session_id}/review")
def workout_session_review663(
    session_id: int, request: Request,
    db: Session = Depends(get_scoped_db390),
):
    workout = db.get(WorkoutSession654, session_id)
    if workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")

    entry_volume = WorkoutSet654.weight_lb * WorkoutSet654.reps
    machine_rows = list(db.execute(
        select(
            WorkoutEquipment654.id.label("equipment_id"),
            WorkoutEquipment654.name.label("name"),
            WorkoutEquipment654.gym.label("gym"),
            func.count(WorkoutSet654.id).label("sets"),
            func.sum(WorkoutSet654.reps).label("reps"),
            func.sum(entry_volume).label("volume"),
            func.max(WorkoutSet654.weight_lb).label("heaviest_lb"),
            func.min(WorkoutSet654.performed_at).label("first_at"),
        )
        .select_from(WorkoutSet654)
        .join(
            WorkoutEquipment654,
            WorkoutEquipment654.id == WorkoutSet654.equipment_id,
        )
        .where(WorkoutSet654.session_id == session_id)
        .group_by(
            WorkoutEquipment654.id,
            WorkoutEquipment654.name,
            WorkoutEquipment654.gym,
        )
        .order_by(
            func.min(WorkoutSet654.performed_at),
            WorkoutEquipment654.id,
        )
    ).all())
    totals = {
        "machines": len(machine_rows),
        "sets": sum(int(row.sets) for row in machine_rows),
        "reps": sum(int(row.reps) for row in machine_rows),
        "volume": sum(float(row.volume) for row in machine_rows),
    }
    frozen_targets = list(db.scalars(
        select(WorkoutSessionTarget667)
        .where(WorkoutSessionTarget667.session_id == session_id)
        .order_by(WorkoutSessionTarget667.equipment_id)
    ))
    equipment_names = {
        target.equipment_id: (
            db.get(WorkoutEquipment654, target.equipment_id).name
            if db.get(WorkoutEquipment654, target.equipment_id) else
            "Unknown equipment"
        )
        for target in frozen_targets
    }
    goal_rows = [
        {
            "target": target,
            "name": equipment_names[target.equipment_id],
            "progress": progress667(db, session_id, target.equipment_id),
        }
        for target in frozen_targets
    ]
    return render(
        request, "workout_review663.html",
        workout=workout, machine_rows=machine_rows, totals=totals,
        goal_rows=goal_rows,
    )


@router.get("/workouts/insights")
def workout_insights668(
    request: Request, db: Session = Depends(get_scoped_db390),
):
    """Read-only completed-session consistency and recorded workload."""
    since = datetime.now() - timedelta(days=28)
    totals = list(db.execute(
        select(
            WorkoutSession654.id.label("session_id"),
            WorkoutSession654.started_at.label("started_at"),
            func.count(WorkoutSet654.id).label("set_count"),
            func.sum(WorkoutSet654.reps).label("repetitions"),
            func.sum(WorkoutSet654.weight_lb * WorkoutSet654.reps).label("volume"),
        )
        .select_from(WorkoutSession654)
        .join(WorkoutSet654, WorkoutSet654.session_id == WorkoutSession654.id)
        .where(WorkoutSession654.completed_at.is_not(None))
        .group_by(WorkoutSession654.id, WorkoutSession654.started_at)
        .order_by(WorkoutSession654.started_at.desc(), WorkoutSession654.id.desc())
        .limit(12)
    ))
    recent = db.execute(
        select(
            func.count(func.distinct(WorkoutSession654.id)),
            func.count(WorkoutSet654.id),
            func.coalesce(func.sum(WorkoutSet654.reps), 0),
            func.coalesce(func.sum(WorkoutSet654.weight_lb * WorkoutSet654.reps), 0.0),
        )
        .select_from(WorkoutSession654)
        .join(WorkoutSet654, WorkoutSet654.session_id == WorkoutSession654.id)
        .where(WorkoutSession654.completed_at.is_not(None),
               WorkoutSession654.started_at >= since)
    ).one()
    return render(
        request, "workout_insights668.html", sessions=totals,
        recent_count=int(recent[0]), recent_sets=int(recent[1]),
        recent_repetitions=int(recent[2]),
        recent_volume=float(recent[3]),
    )


def safe_csv668(value: object) -> str:
    """Prevent spreadsheet formula execution when exporting user-provided names."""
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")) or (text and text[0].isspace()):
        return "'" + text
    return text


@router.get("/workouts/sessions/{session_id}/export.csv")
def export_session668(
    session_id: int, db: Session = Depends(get_scoped_db390),
):
    """Export only actual user-scoped logged sets; read-only and bounded."""
    workout = db.get(WorkoutSession654, session_id)
    if workout is None:
        raise HTTPException(404, "Workout not found")
    from ..workout_models667 import WorkoutSetType667
    rows = list(db.execute(
        select(WorkoutSet654, WorkoutEquipment654.name, WorkoutSetType667.set_type)
        .join(WorkoutEquipment654, WorkoutEquipment654.id == WorkoutSet654.equipment_id)
        .outerjoin(WorkoutSetType667, WorkoutSetType667.set_id == WorkoutSet654.id)
        .where(WorkoutSet654.session_id == session_id)
        .order_by(WorkoutSet654.performed_at, WorkoutSet654.id)
    ))
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(("Session", "Started", "Completed", "Set ID", "Performed",
                     "Equipment", "Type", "Load (lb)", "Repetitions", "Effort"))
    for logged, equipment_name, set_type in rows:
        writer.writerow((
            workout.id, workout.started_at.isoformat(),
            workout.completed_at.isoformat() if workout.completed_at else "",
            logged.id, logged.performed_at.isoformat(),
            safe_csv668(equipment_name), set_type or "working",
            logged.weight_lb, logged.reps,
            logged.effort if logged.effort is not None else "",
        ))
    return Response(
        content=stream.getvalue().encode("utf-8-sig"), media_type="text/csv",
        headers={"Content-Disposition":
                 f'attachment; filename="tracker-workout-{session_id}.csv"'},
    )


@router.post("/workouts/finish-review")
def finish_then_review663(db: Session = Depends(get_scoped_db390)):
    """Reuse original completion exactly once; never invent a completion."""
    workout = active654(db)
    outcome = finish654(db=db)
    if workout is None:
        # The existing handler reports 'No workout in progress.'
        return outcome
    return services.flash_redirect(
        f"/workouts/sessions/{workout.id}/review",
        msg="Workout completed. Review your recorded session.",
    )
