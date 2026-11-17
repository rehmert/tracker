"""Release 667 workout goal calculations and immutable session snapshots.

No estimates: target achievement counts only recorded working sets meeting
both the planned load and rep threshold. No live plan lookup is used for
completed-session goal comparisons.
"""
from __future__ import annotations

from datetime import datetime
from math import isfinite

from sqlalchemy import select
from sqlalchemy.orm import Session

from .workout_models654 import WorkoutSet654
from .workout_models655 import WorkoutRoutineItem655
from .workout_models667 import (
    WorkoutRoutineConfig667, WorkoutRoutineTarget667,
    WorkoutSessionTarget667, WorkoutSetType667,
)

REST_CHOICES667 = (30, 45, 60, 75, 90, 120, 150, 180, 240, 300, 360, 420, 480, 600)


def parse_goal667(sets: str, reps: str, weight: str):
    """All three fields are required for a measurable goal; all blank clears it."""
    strings = (str(sets).strip(), str(reps).strip(), str(weight).strip())
    if not any(strings):
        return (None, None, None)
    if not all(strings):
        raise ValueError("Enter sets, reps, and load together to save a measurable goal.")
    if not (strings[0].isascii() and strings[0].isdecimal() and
            strings[1].isascii() and strings[1].isdecimal()):
        raise ValueError("Target sets and repetitions must be whole numbers.")
    if len(strings[0]) > 3 or len(strings[1]) > 3 or len(strings[2]) > 32:
        raise ValueError("Target values are too long.")
    count, repetitions = int(strings[0]), int(strings[1])
    try:
        pounds = float(strings[2])
    except ValueError as exc:
        raise ValueError("Target load must be a finite number.") from exc
    if not (1 <= count <= 20 and 1 <= repetitions <= 200 and
            isfinite(pounds) and 0 <= pounds <= 2000):
        raise ValueError("Targets must be 1–20 sets, 1–200 reps, and 0–2,000 lb.")
    return (count, repetitions, pounds)


def rest667(raw: str, *, optional: bool = False) -> int | None:
    raw = str(raw).strip()
    if optional and not raw:
        return None
    if not (raw.isascii() and raw.isdecimal()) or int(raw) not in REST_CHOICES667:
        raise ValueError("Select a supported rest interval.")
    return int(raw)


def snapshots667(db: Session, routine_id: int, session_id: int) -> None:
    """Capture validated goals in same transaction as the new routine session."""
    config = db.get(WorkoutRoutineConfig667, routine_id)
    default_rest = config.rest_seconds if config else 90
    items = list(db.scalars(select(WorkoutRoutineItem655).where(
        WorkoutRoutineItem655.routine_id == routine_id
    )))
    for item in items:
        target = db.get(WorkoutRoutineTarget667, item.id)
        if target is None or target.target_sets is None:
            continue
        if db.get(WorkoutSessionTarget667, (session_id, item.equipment_id)):
            continue
        db.add(WorkoutSessionTarget667(
            session_id=session_id, equipment_id=item.equipment_id,
            target_sets=target.target_sets,
            target_reps=target.target_reps,
            target_weight_lb=target.target_weight_lb,
            rest_seconds=target.rest_seconds or default_rest,
            setup_note=target.setup_note,
        ))


def progress667(db: Session, session_id: int, equipment_id: int) -> dict:
    """Working-set count and exact planned-load-and-reps achievement."""
    target = db.get(WorkoutSessionTarget667, (session_id, equipment_id))
    recorded = list(db.execute(
        select(WorkoutSet654, WorkoutSetType667.set_type)
        .outerjoin(
            WorkoutSetType667, WorkoutSetType667.set_id == WorkoutSet654.id,
        )
        .where(
            WorkoutSet654.session_id == session_id,
            WorkoutSet654.equipment_id == equipment_id,
        )
        .order_by(WorkoutSet654.performed_at, WorkoutSet654.id)
    ).all())
    working = [row for row, kind in recorded if kind != "warmup"]
    warmups = len(recorded) - len(working)
    matches = sum(
        entry.weight_lb >= target.target_weight_lb and
        entry.reps >= target.target_reps
        for entry in working
    ) if target else 0
    return {
        "target": target,
        "working_sets": len(working),
        "warmup_sets": warmups,
        "qualifying_sets": matches,
        "credited_sets": min(matches, target.target_sets) if target else 0,
        "achieved": bool(target and matches >= target.target_sets),
        "progress_percent": (
            round(100 * min(matches, target.target_sets) / target.target_sets)
            if target else None
        ),
    }
