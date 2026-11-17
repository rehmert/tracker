"""Release 668: idempotent authentication-scoped replay of queued actual sets.

No implicit workout creation or session-switching: client sends explicit
original session ID and UUID, which must match the active session. Receipt
and recorded set are inserted within the same SQLite transaction.
"""
from __future__ import annotations

import math
from uuid import UUID

from fastapi import APIRouter, Depends, Form
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..scoped_db390 import get_scoped_db390
from ..workout_models654 import WorkoutEquipment654, WorkoutSet654
from ..workout_models667 import WorkoutSetType667
from ..workout_models668 import WorkoutOfflineReceipt668
from .workouts654 import active654

router = APIRouter()


def replay_result668(message: str, status: int = 409):
    return JSONResponse({"ok": False, "error": message}, status_code=status, headers={"Cache-Control": "no-store"})


@router.post("/workouts/offline/sync")
def replay_offline668(
    token: str = Form(...), session_id: int = Form(...),
    equipment_id: int = Form(...), weight_lb: str = Form(...),
    reps: str = Form(...), effort: str = Form(""),
    set_type: str = Form("working"),
    db: Session = Depends(get_scoped_db390),
):
    try:
        parsed = UUID(token)
        if parsed.version != 4 or str(parsed) != token:
            raise ValueError("Malformed replay token")
    except (ValueError, AttributeError):
        return replay_result668("Invalid replay token.", 400)
    if session_id <= 0:
        return replay_result668("Invalid session ID.", 400)
    prior = db.get(WorkoutOfflineReceipt668, token)
    if prior is not None:
        if prior.session_id != session_id:
            return replay_result668("Receipt belongs to another session.", 409)
        return JSONResponse(
            {"ok": True, "duplicate": True, "set_id": prior.set_id},
            headers={"Cache-Control": "no-store"},
        )
    active = active654(db)
    if active is None or active.id != session_id:
        return replay_result668("Original workout is no longer active. Keep the unsynced queue for manual review.", 409)
    if db.get(WorkoutEquipment654, equipment_id) is None:
        return replay_result668("Equipment no longer exists.", 404)
    if set_type not in ("warmup", "working"):
        return replay_result668("Unknown set type.", 400)
    try:
        if len(weight_lb) > 32 or len(reps) > 5 or len(effort) > 3:
            raise ValueError("Field length out of range")
        weight = float(weight_lb)
        count = int(reps)
        effort_value = int(effort) if effort.strip() else None
    except ValueError:
        return replay_result668("Invalid weight, repetitions, or effort.", 400)
    if (not math.isfinite(weight) or not 0 <= weight <= 2000 or
            not 1 <= count <= 200 or
            (effort_value is not None and not 1 <= effort_value <= 10)):
        return replay_result668("Recorded set values are out of range.", 400)
    row = WorkoutSet654(
        session_id=session_id, equipment_id=equipment_id,
        weight_lb=weight, reps=count, effort=effort_value,
    )
    db.add(row)
    db.flush()
    if set_type == "warmup":
        db.add(WorkoutSetType667(set_id=row.id, set_type="warmup"))
    db.add(WorkoutOfflineReceipt668(
        token=token, session_id=session_id, set_id=row.id,
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # A concurrent replay may have already committed. Acknowledge only
        # a matching user-scoped receipt; never create two sets for a token.
        existing = db.get(WorkoutOfflineReceipt668, token)
        if existing is not None and existing.session_id == session_id:
            return JSONResponse(
                {"ok": True, "duplicate": True, "set_id": existing.set_id},
                headers={"Cache-Control": "no-store"},
            )
        return replay_result668("Concurrent replay conflict; check saved sets.", 409)
    return JSONResponse(
        {"ok": True, "duplicate": False, "set_id": row.id},
        headers={"Cache-Control": "no-store"},
    )
