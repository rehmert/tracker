"""Release 668 Dashboard must count only actual completed sessions and sets."""
from datetime import date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from app.workout_dashboard661 import workout_dashboard661


def test_668_dashboard_28_day_actual_only():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    today = date.today()
    with Session(engine) as db:
        gear = WorkoutEquipment654(name="Press", kind="selectorized")
        complete = WorkoutSession654(
            started_at=datetime.combine(today, datetime.min.time()),
            completed_at=datetime.now(),
        )
        unfinished = WorkoutSession654(
            started_at=datetime.combine(today, datetime.min.time()),
        )
        stale = WorkoutSession654(
            started_at=datetime.combine(today - timedelta(days=40), datetime.min.time()),
            completed_at=datetime.now(),
        )
        db.add_all([gear, complete, unfinished, stale])
        db.flush()
        db.add_all([
            WorkoutSet654(session_id=complete.id, equipment_id=gear.id,
                          weight_lb=100, reps=10),
            WorkoutSet654(session_id=complete.id, equipment_id=gear.id,
                          weight_lb=100, reps=8),
            WorkoutSet654(session_id=unfinished.id, equipment_id=gear.id,
                          weight_lb=500, reps=100),
            WorkoutSet654(session_id=stale.id, equipment_id=gear.id,
                          weight_lb=500, reps=100),
        ])
        db.commit()
        summary = workout_dashboard661(db, today)
        assert summary["sessions28"] == 1
        assert summary["sets28"] == 2
        assert summary["reps28"] == 18
        assert summary["days28"] == 1
