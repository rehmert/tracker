"""Release 668 offline synchronization and equipment load metadata regressions."""
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.db import Base
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from app.workout_models667 import WorkoutSetType667
from app.workout_models668 import WorkoutOfflineReceipt668, WorkoutEquipmentLoad668
from app.routers.workouts668 import sync_offline_set668, save_load_semantics668


def test_668_offline_sync_idempotency_and_stale_session(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "offline.sqlite"))
    @event.listens_for(engine, "connect")
    def sqlite_foreign_keys(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        machine = WorkoutEquipment654(name="Nautilus Row", kind="selectorized")
        session = WorkoutSession654(started_at=datetime.now())
        db.add_all([machine, session])
        db.commit()
        key = str(uuid4())
        req = dict(session_id=session.id, equipment_id=machine.id,
                   client_key=key, weight_lb=115, reps=10, effort="8",
                   set_type="warmup", db=db)
        first = sync_offline_set668(**req)
        assert first.status_code == 200 and first.body
        duplicate = sync_offline_set668(**req)
        assert duplicate.status_code == 200
        assert b'"duplicate":true' in duplicate.body
        assert db.scalar(select(func.count(WorkoutSet654.id))) == 1
        assert db.scalar(select(func.count(WorkoutOfflineReceipt668.id))) == 1
        actual = db.scalar(select(WorkoutSet654))
        assert (actual.weight_lb, actual.reps, actual.effort) == (115, 10, 8)
        assert db.get(WorkoutSetType667, actual.id).set_type == "warmup"
        session.completed_at = datetime.now()
        db.commit()
        # A retry of an acknowledged UUID is safe after completion.
        assert sync_offline_set668(**req).status_code == 200
        with pytest.raises(HTTPException) as exc:
            sync_offline_set668(**{**req, "client_key": str(uuid4())})
        assert exc.value.status_code == 409
        assert db.scalar(select(func.count(WorkoutSet654.id))) == 1

        # Explicit deletion must not let a retry re-create the removed set.
        db.delete(actual)
        db.commit()
        db.refresh(db.scalar(select(WorkoutOfflineReceipt668)))
        tombstone = db.scalar(select(WorkoutOfflineReceipt668))
        assert tombstone.set_id is None
        deleted_retry = sync_offline_set668(**req)
        assert deleted_retry.status_code == 200
        assert b'"deleted":true' in deleted_retry.body
        assert db.scalar(select(func.count(WorkoutSet654.id))) == 0


@pytest.mark.parametrize("weight,reps,effort,kind", [
    (float("nan"), 10, "", "working"),
    (2001, 10, "", "working"),
    (50, 0, "", "working"),
    (50, 10, "11", "working"),
    (50, 10, "", "fake"),
])
def test_668_offline_invalid_set_never_writes(tmp_path, weight, reps, effort, kind):
    engine = create_engine("sqlite:///" + str(tmp_path / "invalid.sqlite"))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        machine = WorkoutEquipment654(name="Leg Press", kind="selectorized")
        session = WorkoutSession654(started_at=datetime.now())
        db.add_all([machine, session])
        db.commit()
        with pytest.raises(HTTPException) as exc:
            sync_offline_set668(
                session_id=session.id, equipment_id=machine.id,
                client_key=str(uuid4()), weight_lb=weight, reps=reps,
                effort=effort, set_type=kind, db=db,
            )
        assert exc.value.status_code == 422
        assert db.scalar(select(func.count(WorkoutSet654.id))) == 0


def test_668_machine_load_settings_never_reinterpret_historical_set():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        machine = WorkoutEquipment654(name="Plate Press", kind="plate_loaded")
        session = WorkoutSession654(
            started_at=datetime.now(), completed_at=datetime.now(),
        )
        db.add_all([machine, session])
        db.flush()
        old = WorkoutSet654(session_id=session.id, equipment_id=machine.id,
                            weight_lb=45, reps=12)
        db.add(old)
        db.commit()
        result = save_load_semantics668(
            equipment_id=machine.id, load_mode="per_side",
            multiplier=2, offset_lb=20, note="two 45 lb plates",
            db=db,
        )
        assert result.status_code == 303
        config = db.get(WorkoutEquipmentLoad668, machine.id)
        assert (config.load_mode, config.multiplier, config.offset_lb) == (
            "per_side", 2, 20
        )
        db.refresh(old)
        assert (old.weight_lb, old.reps) == (45, 12)
        invalid = save_load_semantics668(
            equipment_id=machine.id, load_mode="per_side",
            multiplier=float("inf"), offset_lb=0, note="", db=db,
        )
        assert invalid.status_code == 303
        assert db.get(WorkoutEquipmentLoad668, machine.id).multiplier == 2
