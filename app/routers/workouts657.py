"""Release 657: explicitly confirmed correction/removal of ACTIVE workout sets.

All reads and writes occur in the authenticated scoped user database; sets
belonging to completed/other workouts cannot be modified via these endpoints.
No schema changes and no modification of historical session timestamps.
"""
import math

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session

from .. import services
from ..scoped_db390 import get_scoped_db390
from ..workout_models654 import WorkoutSet654
from .workouts654 import active654

router = APIRouter()


def flash_back657(target: str, *, msg: str = "", err: str = ""):
    """Preserve Tracker flash query and scroll back to the edited set list."""
    response = services.flash_redirect(target, msg=msg, err=err)
    response.headers["location"] += "#workout-sets657"
    return response


def active_set657(db: Session, set_id: int) -> WorkoutSet654 | None:
    current = active654(db)
    if current is None:
        return None
    entry = db.get(WorkoutSet654, set_id)
    if entry is None or entry.session_id != current.id:
        raise HTTPException(status_code=404, detail="Set not found in active workout")
    return entry


@router.post("/workouts/sets/{set_id}/edit")
def edit_set657(
    set_id: int,
    weight_lb: float = Form(...),
    reps: int = Form(...),
    effort: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    entry = active_set657(db, set_id)
    if entry is None:
        return services.flash_redirect("/workouts", err="Only an active workout can be edited.")
    target = f"/workouts?machine={entry.equipment_id}"
    if not math.isfinite(weight_lb) or not (0 <= weight_lb <= 2000):
        return flash_back657(target, err="Weight must be between 0 and 2,000 lb.")
    if not 1 <= reps <= 200:
        return flash_back657(target, err="Repetitions must be 1 to 200.")
    parsed_effort = None
    if effort.strip():
        try:
            parsed_effort = int(effort)
        except ValueError:
            return flash_back657(target, err="Effort must be 1–10.")
        if not 1 <= parsed_effort <= 10:
            return flash_back657(target, err="Effort must be 1–10.")

    # Only edit the three recorded values. Retain original set timestamp,
    # equipment identity and session association for historical integrity.
    entry.weight_lb = weight_lb
    entry.reps = reps
    entry.effort = parsed_effort
    db.commit()
    return flash_back657(
        target, msg="Set corrected."
    )


@router.post("/workouts/sets/{set_id}/delete")
def delete_set657(
    set_id: int,
    confirm_delete: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    entry = active_set657(db, set_id)
    if entry is None:
        return services.flash_redirect("/workouts", err="Only an active workout can be edited.")
    target = f"/workouts?machine={entry.equipment_id}"
    if confirm_delete != "yes":
        return flash_back657(
            target,
            err="Confirm removal of the recorded set first.",
        )
    db.delete(entry)
    db.commit()
    return flash_back657(
        target, msg="Set removed."
    )
