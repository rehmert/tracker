"""Release 668 grouped workout guided progress uses actual working sets."""
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from app.workout_models655 import (
    WorkoutRoutine655, WorkoutRoutineItem655, WorkoutSessionRoutine655,
)
from app.workout_models667 import WorkoutSetType667
from app.workout_models668 import WorkoutRoutineGroup668, WorkoutRoutineGroupMember668
from app.routers import workouts659


def test_668_group_round_guide_counts_working_sets_only(monkeypatch):
    monkeypatch.setattr(workouts659, "render", lambda request, template, **data: data)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        gear_a = WorkoutEquipment654(name="Chest Press", kind="selectorized")
        gear_b = WorkoutEquipment654(name="Seated Row", kind="selectorized")
        routine = WorkoutRoutine655(name="Upper")
        session = WorkoutSession654(started_at=datetime.now())
        db.add_all([gear_a, gear_b, routine, session])
        db.flush()
        items = [
            WorkoutRoutineItem655(routine_id=routine.id, equipment_id=gear.id,
                                  position=index)
            for index, gear in enumerate([gear_a, gear_b])
        ]
        db.add_all(items)
        db.add(WorkoutSessionRoutine655(session_id=session.id, routine_id=routine.id))
        group = WorkoutRoutineGroup668(
            routine_id=routine.id, group_name="Push/Pull",
            group_type="superset", rounds=2,
        )
        db.add(group)
        db.flush()
        db.add_all([
            WorkoutRoutineGroupMember668(
                group_id=group.id, routine_item_id=item.id,
                position=index,
            ) for index, item in enumerate(items)
        ])
        db.flush()
        done = WorkoutSet654(session_id=session.id, equipment_id=gear_a.id,
                             weight_lb=80, reps=10)
        warming = WorkoutSet654(session_id=session.id, equipment_id=gear_b.id,
                                weight_lb=20, reps=15)
        db.add_all([done, warming])
        db.flush()
        db.add(WorkoutSetType667(set_id=warming.id, set_type="warmup"))
        db.commit()

        view = workouts659.quick_workout659(request=None, machine=gear_a.id, db=db)
        guided = view["grouped668"][0]
        assert guided["progress"][gear_a.id] == 1
        assert guided["progress"][gear_b.id] == 0
        assert guided["next_machine"].id == gear_b.id
        assert not guided["complete"]

        for gear in (gear_a, gear_b, gear_b):
            db.add(WorkoutSet654(
                session_id=session.id, equipment_id=gear.id,
                weight_lb=85, reps=8,
            ))
        db.commit()
        view = workouts659.quick_workout659(request=None, machine=gear_b.id, db=db)
        guided = view["grouped668"][0]
        assert guided["progress"][gear_a.id] == 2
        assert guided["progress"][gear_b.id] == 2
        assert guided["complete"]
        assert guided["next_machine"] is None
