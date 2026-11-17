"""Release 674: optional, explainable next-session gym targets.

Advisory only; does not modify workout history or prescribed routine goals.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .workout_models654 import WorkoutSession654, WorkoutSet654
from .workout_models667 import WorkoutSetType667


def progression_for674(db: Session, equipment_id: int, target_reps: int | None = None):
    """Use only the most recent *completed* session for a single machine."""
    latest = db.scalar(
        select(WorkoutSession654.id)
        .join(WorkoutSet654, WorkoutSet654.session_id == WorkoutSession654.id)
        .where(
            WorkoutSet654.equipment_id == equipment_id,
            WorkoutSession654.completed_at.is_not(None),
        )
        .order_by(WorkoutSession654.completed_at.desc(), WorkoutSession654.id.desc())
        .limit(1)
    )
    if latest is None:
        return None
    rows = list(db.scalars(
        select(WorkoutSet654)
        .outerjoin(WorkoutSetType667, WorkoutSetType667.set_id == WorkoutSet654.id)
        .where(
            WorkoutSet654.session_id == latest,
            WorkoutSet654.equipment_id == equipment_id,
            (WorkoutSetType667.set_type.is_(None) |
             (WorkoutSetType667.set_type == "working")),
        )
        .order_by(WorkoutSet654.id)
    ))
    if not rows:
        return None
    last = rows[-1]
    # Conservative progression requires three working sets at the same load
    # meeting the configured rep goal (or 8 reps as a transparent default).
    goal = target_reps if target_reps and 1 <= target_reps <= 200 else 8
    same_load = len(rows) >= 3 and all(abs(x.weight_lb - last.weight_lb) < .001 for x in rows[-3:])
    qualified = same_load and all(x.reps >= goal for x in rows[-3:])
    increment = 2.5 if last.weight_lb < 100 else 5.0
    proposed = min(2000.0, last.weight_lb + increment) if qualified and last.weight_lb > 0 else last.weight_lb
    improved = proposed > last.weight_lb
    return dict(
        weight=round(proposed, 2),
        reps=goal,
        progressed=improved,
        basis=(f"Last completed session: three working sets at {last.weight_lb:g} lb "
               f"met at least {goal} reps each." if improved else
               f"Last completed session did not have three working sets at one load "
               f"meeting {goal} reps each. Repeating the previous load is the default."),
        session_id=latest,
    )
