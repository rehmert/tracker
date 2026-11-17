"""Release 668 isolated historical correction and audit tests."""
from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from app.workout_models667 import WorkoutSetType667
from app.workout_models668 import WorkoutSetCorrection668
from app.routers.workouts668 import correct_recorded_set668


def test_668_correction_audit_is_atomic_and_session_scoped(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "audit668.sqlite"))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        machine = WorkoutEquipment654(name="Row", kind="selectorized")
        completed = WorkoutSession654(
            started_at=datetime.now(), completed_at=datetime.now(),
        )
        ongoing = WorkoutSession654(started_at=datetime.now())
        db.add_all([machine, completed, ongoing])
        db.flush()
        logged = WorkoutSet654(session_id=completed.id, equipment_id=machine.id,
                                weight_lb=100, reps=10)
        pending = WorkoutSet654(session_id=ongoing.id, equipment_id=machine.id,
                                 weight_lb=20, reps=12)
        db.add_all([logged, pending])
        db.commit()

        response = correct_recorded_set668(
            completed.id, logged.id, weight_lb=115, reps=8,
            effort="8", set_type="warmup", reason="Corrected transcription",
            db=db,
        )
        assert response.status_code == 303
        db.refresh(logged)
        assert (logged.weight_lb, logged.reps, logged.effort) == (115, 8, 8)
        assert db.get(WorkoutSetType667, logged.id).set_type == "warmup"
        audits = list(db.scalars(select(WorkoutSetCorrection668)))
        assert len(audits) == 1
        assert (audits[0].old_weight_lb, audits[0].new_weight_lb) == (100, 115)
        assert audits[0].reason == "Corrected transcription"
        unchanged = correct_recorded_set668(
            completed.id, logged.id, weight_lb=115, reps=8,
            effort="8", set_type="warmup", reason="No change",
            db=db,
        )
        assert unchanged.status_code == 303
        assert len(list(db.scalars(select(WorkoutSetCorrection668)))) == 1
        blocked = correct_recorded_set668(
            ongoing.id, pending.id, weight_lb=30, reps=10,
            effort="", set_type="working", reason="Can't edit active",
            db=db,
        )
        assert blocked.status_code == 303
        assert db.get(WorkoutSet654, pending.id).weight_lb == 20
        assert len(list(db.scalars(select(WorkoutSetCorrection668)))) == 1
        with pytest.raises(HTTPException) as exc:
            correct_recorded_set668(
                ongoing.id, logged.id, weight_lb=30, reps=10,
                effort="", set_type="working", reason="Wrong session",
                db=db,
            )
        assert exc.value.status_code == 404


@pytest.mark.parametrize("bad_weight,bad_reps,reason", [
    (float("nan"), 10, "bad weight"), (-1, 10, "bad weight"),
    (100, 0, "bad reps"), (100, 201, "bad reps"),
    (100, 10, "x"),
])
def test_668_corrections_reject_invalid_entries_without_audit(
    tmp_path, bad_weight, bad_reps, reason,
):
    engine = create_engine("sqlite:///" + str(tmp_path / "bad668.sqlite"))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        machine = WorkoutEquipment654(name="Press", kind="selectorized")
        done = WorkoutSession654(
            started_at=datetime.now(), completed_at=datetime.now(),
        )
        db.add_all([machine, done])
        db.flush()
        entry = WorkoutSet654(session_id=done.id, equipment_id=machine.id,
                              weight_lb=50, reps=10)
        db.add(entry)
        db.commit()
        response = correct_recorded_set668(
            done.id, entry.id, weight_lb=bad_weight, reps=bad_reps,
            effort="", set_type="working", reason=reason, db=db,
        )
        assert response.status_code == 303
        db.refresh(entry)
        assert (entry.weight_lb, entry.reps) == (50, 10)
        assert not list(db.scalars(select(WorkoutSetCorrection668)))
