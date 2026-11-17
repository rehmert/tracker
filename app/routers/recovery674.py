"""Release 674 audited, compare-before-write reversal of workout corrections."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import services
from ..scoped_db390 import get_scoped_db390
from ..workout_models654 import WorkoutSession654, WorkoutSet654
from ..workout_models667 import WorkoutSetType667
from ..workout_models668 import WorkoutSetCorrection668

router = APIRouter()


def undo_last_correction674(db: Session, session_id: int, set_id: int, change_id: int):
    """Return a status without modifying stale or unrelated records."""
    session = db.get(WorkoutSession654, session_id)
    row = db.get(WorkoutSet654, set_id)
    if session is None or row is None or row.session_id != session_id:
        raise HTTPException(404, "Recorded set not found")
    if session.completed_at is None:
        return "Complete the workout before reversing an audited correction."
    latest = db.scalar(
        select(WorkoutSetCorrection668)
        .where(WorkoutSetCorrection668.set_id == set_id)
        .order_by(WorkoutSetCorrection668.id.desc()).limit(1)
    )
    if latest is None or latest.id != change_id:
        return "This is no longer the latest correction. Reload the review before changing it."
    if latest.reason.startswith("Undo of correction #"):
        return "This reversal is already recorded. Use a new audited correction to change it."
    existing_kind = db.get(WorkoutSetType667, set_id)
    current_kind = existing_kind.set_type if existing_kind else "working"
    current = (row.weight_lb, row.reps, row.effort, current_kind)
    expected = (latest.new_weight_lb, latest.new_reps, latest.new_effort, latest.new_type)
    if current != expected:
        return "Set values have changed since this correction. Nothing was undone."
    db.add(WorkoutSetCorrection668(
        set_id=set_id,
        old_weight_lb=row.weight_lb, new_weight_lb=latest.old_weight_lb,
        old_reps=row.reps, new_reps=latest.old_reps,
        old_effort=row.effort, new_effort=latest.old_effort,
        old_type=current_kind, new_type=latest.old_type,
        reason=f"Undo of correction #{latest.id}",
    ))
    row.weight_lb = latest.old_weight_lb
    row.reps = latest.old_reps
    row.effort = latest.old_effort
    if latest.old_type == "working" and existing_kind is not None:
        db.delete(existing_kind)
    elif latest.old_type == "warmup" and existing_kind is None:
        db.add(WorkoutSetType667(set_id=set_id, set_type="warmup"))
    elif existing_kind is not None:
        existing_kind.set_type = latest.old_type
    db.commit()
    return None


@router.post("/workouts/sessions/{session_id}/sets/{set_id}/corrections/{change_id}/undo")
def undo_workout_correction674(
    session_id: int, set_id: int, change_id: int,
    db: Session = Depends(get_scoped_db390),
):
    problem = undo_last_correction674(db, session_id, set_id, change_id)
    url = f"/workouts/sessions/{session_id}/correct"
    if problem:
        return services.flash_redirect(url, err=problem)
    return services.flash_redirect(url, msg="Correction reversed; both changes retained in audit history.")
