"""Release 668 descriptive training analytics and scheduled-session adherence.

These are retrospective summaries of actual completed sets, not load advice
or causal estimates. Recorded lb x repetitions remains unchanged regardless
of equipment load semantics.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from statistics import mean

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from ..workout_models655 import WorkoutSessionRoutine655, WorkoutRoutine655
from ..workout_models667 import WorkoutSessionTarget667, WorkoutSetType667
from ..workout_models668 import WorkoutTrainingDay668, WorkoutLoadSemantics668
from ..workout_program667 import progress667

router = APIRouter()


def summary668(db: Session, today: date | None = None) -> dict:
    today = today or datetime.now().date()
    start28 = datetime.combine(today - timedelta(days=27), time.min)
    end = datetime.combine(today + timedelta(days=1), time.min)
    sessions = list(db.scalars(
        select(WorkoutSession654)
        .where(
            WorkoutSession654.completed_at.is_not(None),
            WorkoutSession654.started_at < end,
        )
        .order_by(WorkoutSession654.started_at.desc(), WorkoutSession654.id.desc())
        .limit(40)
    ))
    recent = []
    equipment_map = {
        item.id: item.name
        for item in db.scalars(select(WorkoutEquipment654))
    }
    load_map = {
        entry.equipment_id: entry.mode
        for entry in db.scalars(select(WorkoutLoadSemantics668))
    }
    for session in sessions:
        sets = list(db.scalars(
            select(WorkoutSet654).where(WorkoutSet654.session_id == session.id)
            .order_by(WorkoutSet654.performed_at, WorkoutSet654.id)
        ))
        if not sets:
            continue
        targets = list(db.scalars(
            select(WorkoutSessionTarget667)
            .where(WorkoutSessionTarget667.session_id == session.id)
        ))
        matched = [progress667(db, session.id, target.equipment_id) for target in targets]
        goals = sum(goal["target"].target_sets for goal in matched)
        qualifying = sum(goal["credited_sets"] for goal in matched)
        effort_values = [entry.effort for entry in sets if entry.effort is not None]
        by_machine = defaultdict(list)
        for entry in sets:
            by_machine[entry.equipment_id].append(entry)
        semantics = [
            (equipment_map.get(equipment_id, str(equipment_id)),
             load_map.get(equipment_id, "as_recorded"),
             round(sum(row.weight_lb * row.reps for row in entries), 1))
            for equipment_id, entries in by_machine.items()
        ]
        recent.append(dict(
            id=session.id, started_at=session.started_at,
            date=session.started_at.date(),
            sets=len(sets), reps=sum(row.reps for row in sets),
            volume=round(sum(row.weight_lb * row.reps for row in sets), 1),
            machines=len(by_machine), avg_effort=round(mean(effort_values), 1) if effort_values else None,
            planned_goals=goals, qualifying_goals=qualifying,
            goal_pct=round(100 * qualifying / goals) if goals else None,
            semantics=semantics,
        ))
    # Count all eligible 28-day sessions (not merely the 40 rendered cards).
    recorded28 = list(db.execute(
        select(
            WorkoutSession654.id, WorkoutSession654.started_at,
            func.sum(WorkoutSet654.weight_lb * WorkoutSet654.reps).label("volume"),
        )
        .join(WorkoutSet654, WorkoutSet654.session_id == WorkoutSession654.id)
        .where(
            WorkoutSession654.completed_at.is_not(None),
            WorkoutSession654.started_at >= start28,
            WorkoutSession654.started_at < end,
        )
        .group_by(WorkoutSession654.id, WorkoutSession654.started_at)
    ))
    effort28 = db.scalar(select(func.avg(WorkoutSet654.effort))
        .join(WorkoutSession654, WorkoutSession654.id == WorkoutSet654.session_id)
        .where(
            WorkoutSession654.completed_at.is_not(None),
            WorkoutSession654.started_at >= start28,
            WorkoutSession654.started_at < end,
            WorkoutSet654.effort.is_not(None),
        )
    )
    schedules = list(db.scalars(select(WorkoutTrainingDay668)))
    # Scheduled slot is a specific weekday and routine. Count whether a
    # completed session linked to that routine happened on that date.
    links = list(db.execute(
        select(WorkoutSessionRoutine655.routine_id, WorkoutSession654.started_at)
        .join(WorkoutSession654, WorkoutSession654.id == WorkoutSessionRoutine655.session_id)
        .where(
            WorkoutSession654.completed_at.is_not(None),
            WorkoutSession654.started_at >= start28,
            WorkoutSession654.started_at < end,
            select(WorkoutSet654.id).where(
                WorkoutSet654.session_id == WorkoutSession654.id
            ).exists(),
        )
    ))
    logged_pairs = {(r.routine_id, r.started_at.date()) for r in links}
    scheduled_total = 0
    scheduled_completed = 0
    for i in range(28):
        day = today - timedelta(days=i)
        for slot in schedules:
            if slot.weekday == day.weekday():
                scheduled_total += 1
                scheduled_completed += int((slot.routine_id, day) in logged_pairs)
    with_targets = [row for row in recent if row["goal_pct"] is not None]
    return dict(
        sessions28=len(recorded28),
        days28=len({row.started_at.date() for row in recorded28}),
        volume28=round(sum(float(row.volume) for row in recorded28), 1),
        scheduled_total=scheduled_total,
        scheduled_completed=scheduled_completed,
        scheduled_pct=round(100 * scheduled_completed / scheduled_total) if scheduled_total else None,
        goal_sessions=len(with_targets),
        goal_average=round(mean(row["goal_pct"] for row in with_targets), 1) if with_targets else None,
        recent=recent[:20],
        effort_average=round(float(effort28), 1) if effort28 is not None else None,
    )


@router.get("/workouts/insights")
def insights668(request: Request, db: Session = Depends(get_scoped_db390)):
    result = summary668(db)
    # Actual matched-rep personal records across completed workouts, never
    # inferred strength equivalents or comparisons across unlike equipment.
    records = list(db.execute(
        select(
            WorkoutSet654.equipment_id, WorkoutSet654.reps,
            func.max(WorkoutSet654.weight_lb).label("best_lb"),
            func.count(WorkoutSet654.id).label("sets"),
        )
        .join(WorkoutSession654, WorkoutSession654.id == WorkoutSet654.session_id)
        .where(WorkoutSession654.completed_at.is_not(None))
        .group_by(WorkoutSet654.equipment_id, WorkoutSet654.reps)
        .order_by(func.count(WorkoutSet654.id).desc(), WorkoutSet654.equipment_id)
        .limit(18)
    ))
    names = {
        item.id: item.name
        for item in db.scalars(select(WorkoutEquipment654))
    }
    return render(
        request, "workout_insights668.html", summary=result,
        exact_rep_records=records, equipment_names=names,
    )


def dashboard_pulse668(db: Session, today: date | None = None) -> dict:
    """Bounded home widget; avoid recomputing all historical insights on /."""
    today = today or datetime.now().date()
    slots = list(db.execute(
        select(WorkoutTrainingDay668.weekday, WorkoutRoutine655.id,
               WorkoutRoutine655.name)
        .join(WorkoutRoutine655, WorkoutRoutine655.id == WorkoutTrainingDay668.routine_id)
        .order_by(WorkoutTrainingDay668.weekday, WorkoutRoutine655.name)
    ))
    upcoming = sorted(slots, key=lambda row: (
        (row.weekday - today.weekday()) % 7, row.name,
    ))[:3]
    most_recent = db.scalar(
        select(WorkoutSession654)
        .where(WorkoutSession654.completed_at.is_not(None))
        .order_by(WorkoutSession654.started_at.desc(), WorkoutSession654.id.desc())
        .limit(1)
    )
    goal = None
    if most_recent is not None:
        targets = list(db.scalars(select(WorkoutSessionTarget667).where(
            WorkoutSessionTarget667.session_id == most_recent.id
        )))
        if targets:
            achieved = [progress667(db, most_recent.id, t.equipment_id) for t in targets]
            planned = sum(row["target"].target_sets for row in achieved)
            qualified = sum(row["credited_sets"] for row in achieved)
            goal = dict(
                session_id=most_recent.id, planned=planned, qualified=qualified,
                pct=round(100 * qualified / planned) if planned else None,
            )
    return {"upcoming": upcoming, "goal": goal}
