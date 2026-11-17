"""Release 668 planned calendar entries do not affect actual workout totals."""
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.workout_models655 import WorkoutRoutine655
from app.workout_models668 import WorkoutRoutineSchedule668
from app.routers.workouts664 import workout_calendar_data664


def test_668_planned_calendar_does_not_fabricate_completed_workouts(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "planned668.sqlite"))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        a = WorkoutRoutine655(name="Upper A")
        b = WorkoutRoutine655(name="lower b")
        db.add_all([a, b])
        db.flush()
        for routine in (b, a):
            db.add(WorkoutRoutineSchedule668(
                routine_id=routine.id, weekdays="0,2,4",
                start_on=date(2026, 11, 1),
            ))
        db.commit()
        calendar = workout_calendar_data664(
            db, date(2026, 11, 1), date(2026, 11, 17)
        )
        assert calendar["sessions"] == 0
        assert calendar["training_days"] == 0
        assert calendar["sets"] == 0
        monday = next(row for row in calendar["planned_days"]
                      if row["day"] == date(2026, 11, 16))
        assert [v["name"] for v in monday["routines"]] == ["lower b", "Upper A"]
        cell = next(c for week in calendar["weeks"] for c in week
                    if c["day"] == date(2026, 11, 16))
        assert cell["count"] == 0
        assert len(cell["plans"]) == 2
