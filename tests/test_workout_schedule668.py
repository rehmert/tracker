"""Release 668 schedule parser and scoped group schema checks."""
from datetime import date

import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import Session

from app.db import Base
from app.workout_models654 import WorkoutEquipment654
from app.workout_models655 import WorkoutRoutine655, WorkoutRoutineItem655
from app.workout_models668 import (
    WorkoutRoutineSchedule668, WorkoutRoutineGroup668,
    WorkoutRoutineGroupMember668,
)
from app.routers.workouts668 import parse_weekdays668, next_occurrences668, add_group668


def test_668_weekday_recurrence_does_not_invent_sessions():
    assert parse_weekdays668("4,0,2") == "0,2,4"
    result = next_occurrences668(
        "0,2,4", date(2026, 11, 16), date(2026, 11, 25),
        today=date(2026, 11, 16),
    )
    assert result == [
        date(2026, 11, 16), date(2026, 11, 18),
        date(2026, 11, 20), date(2026, 11, 23),
        date(2026, 11, 25),
    ]


@pytest.mark.parametrize("bad", [
    "", "0,0", "7", "-1", "2,8", "3,,4", "Mon", "1, 2", "1\n2"
])
def test_668_weekday_validation_fails_closed(bad):
    with pytest.raises(ValueError):
        parse_weekdays668(bad)


def test_668_additive_group_schema_and_routine_membership(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "workout668.sqlite"))
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    names = set(inspect(engine).get_table_names())
    assert {"workout_routine_schedule668", "workout_routine_groups668",
            "workout_routine_group_members668"} <= names
    with Session(engine) as db:
        routine = WorkoutRoutine655(name="Strength")
        equipment = [
            WorkoutEquipment654(name=f"Machine {i}", kind="selectorized")
            for i in range(2)
        ]
        db.add_all([routine, *equipment])
        db.flush()
        items = [
            WorkoutRoutineItem655(
                routine_id=routine.id, equipment_id=m.id, position=n,
            ) for n, m in enumerate(equipment)
        ]
        db.add_all(items)
        db.commit()
        out = add_group668(
            routine_id=routine.id, group_name="Push/pull",
            group_type="superset", rounds=3,
            item_ids=[i.id for i in items], db=db,
        )
        assert out.status_code == 303
        groups = db.query(WorkoutRoutineGroup668).all()
        members = db.query(WorkoutRoutineGroupMember668).all()
        assert len(groups) == 1 and len(members) == 2
        assert groups[0].group_type == "superset"
        duplicate = add_group668(
            routine_id=routine.id, group_name="Repeat",
            group_type="circuit", rounds=5,
            item_ids=[i.id for i in items], db=db,
        )
        assert duplicate.status_code == 303
        assert len(db.query(WorkoutRoutineGroup668).all()) == 1
