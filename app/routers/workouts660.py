"""Release 660: read-only machine-scoped actual-load and exact-rep analytics.

Completed sessions only. Never estimates 1RM, bodyweight, or equivalent machine
loads; the volume number is the mathematical sum of entered lb × repetitions.
"""
from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654

router = APIRouter()
MAX_SESSION_POINTS660 = 20
MAX_REP_CHOICES660 = 12
MIN_REPS660 = 1
MAX_REPS660 = 200


def chart_points660(values: list[float]) -> str:
    """SVG numeric-only coordinates, oldest first; single-point charts use tables."""
    if len(values) < 2 or any(not math.isfinite(v) for v in values):
        return ""
    low, high = min(values), max(values)
    spread = high - low
    output = []
    for i, value in enumerate(values):
        x = 28 + 644 * i / (len(values) - 1)
        y = 138 - 98 * ((value - low) / spread if spread else 0.5)
        output.append(f"{x:.1f},{y:.1f}")
    return " ".join(output)


def range660(values: list[float]) -> tuple[float, float]:
    return (min(values), max(values)) if values else (0.0, 0.0)


@router.get("/workouts/analytics")
def analytics660(
    request: Request,
    machine: int | None = Query(default=None, ge=1),
    reps: int | None = Query(default=None, ge=MIN_REPS660, le=MAX_REPS660),
    db: Session = Depends(get_scoped_db390),
):
    equipment = list(db.scalars(
        select(WorkoutEquipment654).order_by(
            WorkoutEquipment654.gym, WorkoutEquipment654.name, WorkoutEquipment654.id
        )
    ))
    latest_machine_id = db.scalar(
        select(WorkoutSet654.equipment_id)
        .join(WorkoutSession654, WorkoutSession654.id == WorkoutSet654.session_id)
        .where(WorkoutSession654.completed_at.is_not(None))
        .order_by(WorkoutSession654.started_at.desc(), WorkoutSet654.id.desc())
        .limit(1)
    )
    chosen_id = machine if machine is not None else (
        latest_machine_id if latest_machine_id is not None else
        (equipment[0].id if equipment else None)
    )
    selected = next((item for item in equipment if item.id == chosen_id), None)
    if machine is not None and selected is None:
        raise HTTPException(status_code=404, detail="Equipment not found")

    if selected is None:
        return render(
            request, "workout_analytics660.html",
            equipment=equipment, selected=None, reps_selected=None,
            rep_choices=[], summary=None, top_load=None, top_volume=None,
            sessions=[], session_points="", session_range=(0.0, 0.0),
            exact=[], exact_points="", exact_range=(0.0, 0.0),
            session_limit=MAX_SESSION_POINTS660,
        )

    # All queries constrain to an existing equipment record and completed
    # sessions in the authenticated user's scoped DB.
    criteria = (
        WorkoutSet654.equipment_id == selected.id,
        WorkoutSession654.completed_at.is_not(None),
    )
    join = (WorkoutSession654, WorkoutSession654.id == WorkoutSet654.session_id)
    entry_volume = WorkoutSet654.weight_lb * WorkoutSet654.reps

    stats = db.execute(
        select(
            func.count(WorkoutSet654.id).label("sets"),
            func.count(func.distinct(WorkoutSession654.id)).label("sessions"),
            func.coalesce(func.sum(WorkoutSet654.reps), 0).label("reps"),
            func.coalesce(func.sum(entry_volume), 0.0).label("volume"),
        )
        .select_from(WorkoutSet654)
        .join(*join)
        .where(*criteria)
    ).one()
    summary = dict(
        sets=int(stats.sets), sessions=int(stats.sessions),
        repetitions=int(stats.reps), volume=float(stats.volume),
    )

    top_load = db.scalar(
        select(WorkoutSet654).join(*join).where(*criteria)
        .order_by(
            WorkoutSet654.weight_lb.desc(), WorkoutSet654.reps.desc(),
            WorkoutSession654.started_at.desc(), WorkoutSet654.id.desc(),
        ).limit(1)
    )
    top_volume = db.scalar(
        select(WorkoutSet654).join(*join).where(*criteria)
        .order_by(
            entry_volume.desc(), WorkoutSession654.started_at.desc(),
            WorkoutSet654.id.desc(),
        ).limit(1)
    )

    # One row per completed session on this machine. Backfilled sessions
    # sort by their entered workout date, not the later insertion time.
    sessions_desc = list(db.execute(
        select(
            WorkoutSession654.id.label("session_id"),
            WorkoutSession654.started_at.label("started_at"),
            func.count(WorkoutSet654.id).label("sets"),
            func.sum(WorkoutSet654.reps).label("reps"),
            func.sum(entry_volume).label("volume"),
            func.max(WorkoutSet654.weight_lb).label("max_lb"),
        )
        .select_from(WorkoutSet654)
        .join(*join).where(*criteria)
        .group_by(WorkoutSession654.id, WorkoutSession654.started_at)
        .order_by(
            WorkoutSession654.started_at.desc(), WorkoutSession654.id.desc(),
        )
        .limit(MAX_SESSION_POINTS660)
    ).all())
    sessions = list(reversed(sessions_desc))
    session_volumes = [float(row.volume) for row in sessions]
    session_points = chart_points660(session_volumes)

    # Each comparison is across *exactly the same repetition count* and
    # exactly the same equipment ID, never across a different machine.
    rep_choices = list(db.execute(
        select(
            WorkoutSet654.reps.label("reps"),
            func.count(WorkoutSet654.id).label("sets"),
            func.max(WorkoutSet654.weight_lb).label("best_lb"),
        )
        .select_from(WorkoutSet654)
        .join(*join).where(*criteria)
        .group_by(WorkoutSet654.reps)
        .order_by(
            func.count(WorkoutSet654.id).desc(), WorkoutSet654.reps.asc()
        )
        .limit(MAX_REP_CHOICES660)
    ).all())
    reps_selected = (
        reps if reps is not None else
        (int(rep_choices[0].reps) if rep_choices else None)
    )
    exact_desc = list(db.execute(
        select(
            WorkoutSession654.id.label("session_id"),
            WorkoutSession654.started_at.label("started_at"),
            func.max(WorkoutSet654.weight_lb).label("best_lb"),
            func.count(WorkoutSet654.id).label("sets"),
        )
        .select_from(WorkoutSet654)
        .join(*join).where(
            *criteria, WorkoutSet654.reps == reps_selected,
        )
        .group_by(WorkoutSession654.id, WorkoutSession654.started_at)
        .order_by(
            WorkoutSession654.started_at.desc(), WorkoutSession654.id.desc(),
        )
        .limit(MAX_SESSION_POINTS660)
    ).all()) if reps_selected is not None else []
    exact = list(reversed(exact_desc))
    exact_weights = [float(row.best_lb) for row in exact]

    return render(
        request, "workout_analytics660.html",
        equipment=equipment, selected=selected, reps_selected=reps_selected,
        rep_choices=rep_choices, summary=summary,
        top_load=top_load, top_volume=top_volume,
        sessions=sessions, session_points=session_points,
        session_range=range660(session_volumes),
        exact=exact, exact_points=chart_points660(exact_weights),
        exact_range=range660(exact_weights),
        session_limit=MAX_SESSION_POINTS660,
    )
