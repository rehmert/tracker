"""Release 663: recorded-only Workout session review and finish delegation.

All reads use the authenticated user's established scoped SQLite session.
Finish & Review invokes the existing validated Release 654 finish function once;
it never duplicates session write logic, adds columns, or estimates strength.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import services
from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
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
    return render(
        request, "workout_review663.html",
        workout=workout, machine_rows=machine_rows, totals=totals,
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
