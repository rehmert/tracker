"""Release 665: read-only routine planning baselines from completed actual sets.

Targets are optional browser-local drafts managed exclusively by the UI.
This route never persists plans or workouts, guesses progression, or uses
unscoped databases. Historical comparisons keep equipment identity exact.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..workout_models654 import (
    WorkoutEquipment654, WorkoutSession654, WorkoutSet654,
)
from ..workout_models655 import WorkoutRoutine655, WorkoutRoutineItem655

router = APIRouter()
MAX_COMPARISON_SESSIONS665 = 2


def routine_plan_data665(db: Session, routine_id: int) -> dict:
    """All historical reads are restricted to the saved routine's equipment."""
    routine = db.get(WorkoutRoutine655, routine_id)
    if routine is None:
        raise HTTPException(status_code=404, detail="Routine not found")
    items = list(db.scalars(
        select(WorkoutRoutineItem655)
        .where(WorkoutRoutineItem655.routine_id == routine.id)
        .order_by(WorkoutRoutineItem655.position, WorkoutRoutineItem655.id)
    ))
    rows = []
    for item in items:
        equipment = db.get(WorkoutEquipment654, item.equipment_id)
        if equipment is None:
            # Do not guess orphaned machine history.
            continue
        volume_expr = WorkoutSet654.weight_lb * WorkoutSet654.reps
        history = list(db.execute(
            select(
                WorkoutSession654.id.label("session_id"),
                WorkoutSession654.started_at.label("started_at"),
                func.count(WorkoutSet654.id).label("sets"),
                func.sum(WorkoutSet654.reps).label("reps"),
                func.max(WorkoutSet654.weight_lb).label("heaviest_lb"),
                func.sum(volume_expr).label("volume"),
            )
            .select_from(WorkoutSet654)
            .join(
                WorkoutSession654,
                WorkoutSession654.id == WorkoutSet654.session_id,
            )
            .where(
                WorkoutSet654.equipment_id == equipment.id,
                WorkoutSession654.completed_at.is_not(None),
            )
            .group_by(
                WorkoutSession654.id, WorkoutSession654.started_at,
            )
            .order_by(
                WorkoutSession654.started_at.desc(),
                WorkoutSession654.id.desc(),
            )
            .limit(MAX_COMPARISON_SESSIONS665)
        ).all())
        latest = history[0] if history else None
        previous = history[1] if len(history) > 1 else None
        rows.append({
            "item": item,
            "equipment": equipment,
            "latest": latest,
            "previous": previous,
            "load_change": (
                float(latest.heaviest_lb) - float(previous.heaviest_lb)
                if latest is not None and previous is not None else None
            ),
            "volume_change": (
                float(latest.volume) - float(previous.volume)
                if latest is not None and previous is not None else None
            ),
        })
    return {
        "routine": routine,
        "rows": rows,
        "history_count": sum(row["latest"] is not None for row in rows),
    }


@router.get("/workouts/routines/{routine_id}/plan")
def routine_plan665(
    routine_id: int, request: Request,
    db: Session = Depends(get_scoped_db390),
):
    return render(
        request, "workout_plan665.html",
        **routine_plan_data665(db, routine_id),
    )
