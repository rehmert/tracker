"""Release 668 focused DB isolation: duplication and safe recorded-set export."""
from datetime import datetime

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.db import Base
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from app.workout_models655 import WorkoutRoutine655, WorkoutRoutineItem655
from app.workout_models667 import WorkoutRoutineConfig667, WorkoutRoutineTarget667
from app.routers.workouts655 import duplicate_routine668, substitute_routine_item668
from app.routers.workouts663 import export_session668, safe_csv668, workout_insights668


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
        alternate = WorkoutEquipment654(name="Different Machine", kind="plate_loaded")
        db.add(alternate)
        db.commit()
        result = substitute_routine_item668(
            routine_id=new.id, item_id=new_item.id,
            equipment_id=alternate.id, db=db,
        )
        assert result.status_code == 303
        db.refresh(new_item)
        assert new_item.equipment_id == alternate.id
        db.refresh(goal)
        assert (goal.target_sets, goal.target_reps, goal.target_weight_lb) == (
            None, None, None,
        )
        # Original routine and its machine-specific plan must remain intact.
        assert db.get(WorkoutRoutineItem655, item.id).equipment_id == gear.id
        assert db.get(WorkoutRoutineTarget667, item.id).target_weight_lb == 100
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


def test_668_insights_counts_only_completed_sessions_with_actual_sets(monkeypatch):
    from app.routers import workouts663
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        WorkoutEquipment654.__table__, WorkoutSession654.__table__,
        WorkoutSet654.__table__,
    ])
    monkeypatch.setattr(
        workouts663, "render", lambda request, template, **context: context,
    )
    with Session(engine) as db:
        gear = WorkoutEquipment654(name="Verified Row", kind="selectorized")
        done = WorkoutSession654(
            started_at=datetime.now(), completed_at=datetime.now(),
        )
        open_session = WorkoutSession654(started_at=datetime.now())
        empty = WorkoutSession654(
            started_at=datetime.now(), completed_at=datetime.now(),
        )
        db.add_all([gear, done, open_session, empty])
        db.flush()
        db.add_all([
            WorkoutSet654(
                session_id=done.id, equipment_id=gear.id,
                weight_lb=100, reps=10,
            ),
            WorkoutSet654(
                session_id=open_session.id, equipment_id=gear.id,
                weight_lb=500, reps=10,
            ),
        ])
        db.commit()
        data = workout_insights668(request=None, db=db)
        assert data["recent_count"] == 1
        assert data["recent_sets"] == 1
        assert data["recent_repetitions"] == 10
        assert data["recent_volume"] == 1000
        assert len(data["sessions"]) == 1
        assert data["sessions"][0].session_id == done.id
