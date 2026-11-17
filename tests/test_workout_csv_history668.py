"""Release 668 historical CSV import uses the Release 658 validation path."""
from datetime import date, datetime, timedelta
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db import Base
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from app.workout_models667 import WorkoutSetType667
from app.routers.workouts658 import import_previous_workout_csv668


def test_668_csv_history_import_atomic_and_duplicate_guard(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "csvhistory668.sqlite"))
    Base.metadata.create_all(engine)
    yesterday = date.today() - timedelta(days=1)
    with Session(engine) as db:
        machine = WorkoutEquipment654(name="Seated Row", kind="selectorized")
        db.add(machine)
        db.commit()
        payload = (
            "equipment_id,weight_lb,reps,effort,set_time\n"
            + f"{machine.id},100,10,7,09:05\n"
            + f"{machine.id},110,8,,09:15\n"
        )
        kwargs = dict(
            day=yesterday.isoformat(),
            start_time="09:00", end_time="09:30",
            routine_id="", csv_text=payload, db=db,
        )
        first = import_previous_workout_csv668(**kwargs)
        assert first.status_code == 303
        assert db.scalar(select(func.count(WorkoutSession654.id))) == 1
        assert db.scalar(select(func.count(WorkoutSet654.id))) == 2
        again = import_previous_workout_csv668(**kwargs)
        assert again.status_code == 303
        assert "err=" in again.headers["location"]
        assert db.scalar(select(func.count(WorkoutSession654.id))) == 1
        assert db.scalar(select(func.count(WorkoutSet654.id))) == 2
        broken = import_previous_workout_csv668(
            **{**kwargs, "end_time": "10:00",
               "csv_text": payload.replace("110,8", "110,0")}
        )
        assert "err=" in broken.headers["location"]
        assert db.scalar(select(func.count(WorkoutSession654.id))) == 1
        assert db.scalar(select(func.count(WorkoutSet654.id))) == 2
        typed_payload = (
            "equipment_id,weight_lb,reps,effort,set_time,set_type\n"
            + f"{machine.id},40,15,,10:05,warmup\n"
            + f"{machine.id},100,10,8,10:15,working\n"
        )
        typed = import_previous_workout_csv668(
            **{**kwargs, "start_time": "10:00", "end_time": "10:30",
               "csv_text": typed_payload}
        )
        assert typed.status_code == 303
        assert "err=" not in typed.headers["location"]
        assert db.scalar(select(func.count(WorkoutSession654.id))) == 2
        warmups = list(db.scalars(select(WorkoutSetType667)))
        assert len(warmups) == 1 and warmups[0].set_type == "warmup"
