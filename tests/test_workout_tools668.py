"""Release 668 focused DB isolation: duplication and safe recorded-set export."""
from datetime import datetime

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.db import Base
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from app.workout_models655 import WorkoutRoutine655, WorkoutRoutineItem655
from app.workout_models667 import WorkoutRoutineConfig667, WorkoutRoutineTarget667
from app.routers.workouts655 import duplicate_routine668
from app.routers.workouts663 import export_session668, safe_csv668


def test_668_routine_duplicate_copies_plan_not_history():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        WorkoutEquipment654.__table__, WorkoutRoutine655.__table__,
        WorkoutRoutineItem655.__table__, WorkoutRoutineConfig667.__table__,
        WorkoutRoutineTarget667.__table__, WorkoutSession654.__table__,
        WorkoutSet654.__table__,
    ])
    with Session(engine) as db:
        gear = WorkoutEquipment654(name="Nautilus Row", kind="selectorized")
        source = WorkoutRoutine655(name="Upper A")
        db.add_all([gear, source])
        db.flush()
        item = WorkoutRoutineItem655(routine_id=source.id, equipment_id=gear.id, position=0)
        db.add(item)
        db.flush()
        db.add(WorkoutRoutineConfig667(routine_id=source.id, rest_seconds=120))
        db.add(WorkoutRoutineTarget667(
            routine_item_id=item.id, target_sets=3, target_reps=8,
            target_weight_lb=100, setup_note="Seat 4", rest_seconds=90,
        ))
        db.commit()
        output = duplicate_routine668(source.id, db=db)
        assert output.status_code == 303
        copies = list(db.scalars(select(WorkoutRoutine655).order_by(WorkoutRoutine655.id)))
        assert [r.name for r in copies] == ["Upper A", "Upper A (Copy)"]
        new = copies[1]
        new_item = db.scalar(select(WorkoutRoutineItem655).where(
            WorkoutRoutineItem655.routine_id == new.id
        ))
        assert new_item.equipment_id == gear.id
        assert new_item.id != item.id
        goal = db.get(WorkoutRoutineTarget667, new_item.id)
        assert (goal.target_sets, goal.target_reps, goal.target_weight_lb,
                goal.setup_note, goal.rest_seconds) == (3, 8, 100, "Seat 4", 90)
        assert db.get(WorkoutRoutineConfig667, new.id).rest_seconds == 120
        assert db.scalar(select(func.count(WorkoutSet654.id))) == 0


def test_668_csv_formula_safety_and_missing_session():
    assert safe_csv668("=HYPERLINK('x')").startswith("'=")
    assert safe_csv668(" -10").startswith("' ")
    assert safe_csv668("Nautilus Press") == "Nautilus Press"
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        WorkoutEquipment654.__table__, WorkoutSession654.__table__,
        WorkoutSet654.__table__,
    ])
    with Session(engine) as db:
        from fastapi import HTTPException
        try:
            export_session668(9999, db=db)
        except HTTPException as exc:
            assert exc.status_code == 404
        else:
            raise AssertionError("Unknown session must fail")
