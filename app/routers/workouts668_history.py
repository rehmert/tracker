"""Release 668: auditable corrections of completed sets and explicit load semantics.

Corrections never rewrite frozen targets; deletes retain the entire old set
in an append-only, timestamped audit. Existing live-set edit routes are
unaffected. All writes require existing scoped DB, auth, CSRF and origin policy.
"""
from __future__ import annotations

from datetime import datetime
import json
import math

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .. import services
from ..scoped_db390 import get_scoped_db390
from ..workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from ..workout_models667 import WorkoutSetType667
from ..workout_models668 import WorkoutLoadSemantics668, WorkoutSetAudit668

router = APIRouter()
LOAD_MODES668 = ("as_recorded", "per_hand", "added_bodyweight")


def snapshot_set668(row: WorkoutSet654, kind: str) -> dict:
    return dict(
        set_id=row.id, session_id=row.session_id,
        equipment_id=row.equipment_id,
        weight_lb=row.weight_lb, reps=row.reps, effort=row.effort,
        performed_at=row.performed_at.isoformat() if row.performed_at else None,
        set_type=kind,
    )


@router.post("/workouts/sessions/{session_id}/sets/{set_id}/correct")
def correct_historical668(
    session_id: int, set_id: int,
    action: str = Form("edit"), weight_lb: str = Form(""),
    reps: str = Form(""), effort: str = Form(""),
    set_type: str = Form("working"), reason: str = Form(""),
    confirm_delete: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    url = f"/workouts/sessions/{session_id}"
    workout = db.get(WorkoutSession654, session_id)
    if workout is None:
        raise HTTPException(404, "Workout not found")
    if workout.completed_at is None:
        return services.flash_redirect(url, err="Only completed workouts can be corrected here.")
    row = db.get(WorkoutSet654, set_id)
    if row is None or row.session_id != session_id:
        raise HTTPException(404, "Set does not belong to this workout")
    reason = reason.strip()
    if not 8 <= len(reason) <= 300:
        return services.flash_redirect(url, err="Correction reason must be 8–300 characters.")
    if action not in ("edit", "delete"):
        return services.flash_redirect(url, err="Unknown historical correction action.")
    current = db.get(WorkoutSetType667, set_id)
    kind = current.set_type if current else "working"
    before = snapshot_set668(row, kind)
    if action == "delete":
        if confirm_delete != "yes":
            return services.flash_redirect(url, err="Confirm permanent removal of the set.")
        after = dict(deleted=True)
        db.delete(row)
    else:
        if set_type not in ("working", "warmup"):
            return services.flash_redirect(url, err="Invalid working/warm-up type.")
        try:
            weight = float(weight_lb)
            count = int(reps)
            parsed_effort = int(effort) if effort.strip() else None
        except ValueError:
            return services.flash_redirect(url, err="Enter valid recorded weight, reps and effort.")
        if (not math.isfinite(weight) or not (0 <= weight <= 2000) or
                not 1 <= count <= 200 or
                (parsed_effort is not None and not 1 <= parsed_effort <= 10)):
            return services.flash_redirect(url, err="Recorded set values out of range.")
        row.weight_lb, row.reps, row.effort = weight, count, parsed_effort
        if set_type == "warmup":
            if current is None:
                db.add(WorkoutSetType667(set_id=set_id, set_type="warmup"))
        elif current is not None:
            db.delete(current)
        after = snapshot_set668(row, set_type)
        if after == before:
            return services.flash_redirect(url, msg="No changes to record.")
    db.add(WorkoutSetAudit668(
        session_id=session_id, original_set_id=set_id,
        action=action, before_json=json.dumps(before, sort_keys=True),
        after_json=json.dumps(after, sort_keys=True),
        reason=reason, changed_at=datetime.now(),
    ))
    db.commit()
    return services.flash_redirect(
        url, msg="Recorded correction with permanent audit history."
    )


@router.post("/workouts/equipment/{equipment_id}/load-semantics")
def save_load_semantics668(
    equipment_id: int, mode: str = Form("as_recorded"),
    db: Session = Depends(get_scoped_db390),
):
    if db.get(WorkoutEquipment654, equipment_id) is None:
        raise HTTPException(404, "Equipment not found")
    url = f"/workouts/equipment/{equipment_id}/progress"
    if mode not in LOAD_MODES668:
        return services.flash_redirect(url, err="Unknown load recording convention.")
    row = db.get(WorkoutLoadSemantics668, equipment_id)
    if row is None:
        row = WorkoutLoadSemantics668(equipment_id=equipment_id, mode=mode)
        db.add(row)
    else:
        row.mode = mode
    db.commit()
    return services.flash_redirect(
        url, msg="Load semantics updated for future interpretation. Historic numbers unchanged."
    )
