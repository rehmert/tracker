"""Release 668 CSV contract regression tests (pure, no live database writes)."""
import csv
from io import StringIO

import pytest

from app.workout_csv668 import (FIELDS668, parse_routine_csv668,
                                  render_routine_csv668, parse_historical_csv668)


def test_668_csv_plan_round_trip_with_utf8_and_blank_goal():
    rows = [
        dict(routine_item_id=7, sets=3, reps=10, weight_lb=125.5,
             rest_seconds=90, setup_note="Seat 4, wide grip"),
        dict(routine_item_id=8, sets="", reps="", weight_lb="",
             rest_seconds="", setup_note="No machine load goal"),
    ]
    payload = render_routine_csv668(rows)
    parsed = parse_routine_csv668(payload, {7, 8})
    assert [(r["routine_item_id"], r["target_sets"],
             r["target_weight_lb"]) for r in parsed] == [
        (7, 3, 125.5), (8, None, None)
    ]
    assert parsed[0]["setup_note"] == "Seat 4, wide grip"
    assert parsed[1]["setup_note"] == "No machine load goal"


@pytest.mark.parametrize("csv_text", [
    "",
    "equipment_id,sets,reps,weight_lb,rest_seconds,setup_note\n7,3,10,100,90,test\n",
    "routine_item_id,sets,reps,weight_lb,rest_seconds,setup_note\n999,3,10,100,90,test\n",
    "routine_item_id,sets,reps,weight_lb,rest_seconds,setup_note\n7,3,10,100,90,test\n7,2,8,90,90,duplicate\n",
    "routine_item_id,sets,reps,weight_lb,rest_seconds,setup_note\n7,3,10,100,90,test,extra\n",
    "routine_item_id,sets,reps,weight_lb,rest_seconds,setup_note\n7,3,,100,90,partial\n",
    "routine_item_id,sets,reps,weight_lb,rest_seconds,setup_note\n7,3,10,100,7,bad rest\n",
    "routine_item_id,sets,reps,weight_lb,rest_seconds,setup_note\n7,3,10,nan,90,invalid\n",
])
def test_668_csv_rejects_invalid_documents_atomically(csv_text):
    with pytest.raises(ValueError):
        parse_routine_csv668(csv_text, {7, 8})


def test_668_csv_export_neutralizes_formula_in_notes():
    result = render_routine_csv668([dict(
        routine_item_id=7, sets=3, reps=10, weight_lb=10, rest_seconds=90,
        setup_note="=IMPORTXML(example)",
    )])
    data = list(csv.reader(StringIO(result)))
    assert data[0] == list(FIELDS668)
    assert data[1][-1].startswith("'=")


def test_668_historical_csv_structure_accepts_exact_columns():
    text = "equipment_id,weight_lb,reps,effort,set_time\n3,125,10,8,08:30\n4,0,12,,08:40\n"
    rows = parse_historical_csv668(text)
    assert len(rows) == 2
    assert rows[0]["equipment_id"] == "3"
    assert rows[1]["effort"] == ""


@pytest.mark.parametrize("text", [
    "",
    "equipment,weight_lb,reps,effort,set_time\n1,20,8,,12:00\n",
    "equipment_id,weight_lb,reps,effort,set_time\n1,20,8,extra,12:00,extra\n",
    "equipment_id,weight_lb,reps,effort,set_time\n",
])
def test_668_historical_csv_rejects_malformed_documents(text):
    with pytest.raises(ValueError):
        parse_historical_csv668(text)


def test_668_plan_csv_accepts_utf8_bom_after_export():
    sample = "routine_item_id,sets,reps,weight_lb,rest_seconds,setup_note\n7,2,10,75,90,Seat 4\n"
    values = parse_routine_csv668("\ufeff" + sample, {7})
    assert len(values) == 1 and values[0]["target_weight_lb"] == 75.0


def test_668_historical_export_is_directly_import_compatible():
    from datetime import datetime
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.db import Base
    from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
    from app.routers.workouts663 import export_reimport_sets668

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        gear = WorkoutEquipment654(name="Lat Pull", kind="selectorized")
        workout = WorkoutSession654(
            started_at=datetime(2026, 11, 12, 9),
            completed_at=datetime(2026, 11, 12, 9, 30),
        )
        db.add_all([gear, workout])
        db.flush()
        logged = WorkoutSet654(
            session_id=workout.id, equipment_id=gear.id,
            weight_lb=110, reps=8, effort=7,
            performed_at=datetime(2026, 11, 12, 9, 15),
        )
        db.add(logged)
        db.commit()
        exported = export_reimport_sets668(session_id=workout.id, db=db)
        assert exported.status_code == 200
        imported = parse_historical_csv668(exported.body.decode("utf-8"))
        assert imported == [{
            "equipment_id": str(gear.id),
            "weight_lb": "110.0", "reps": "8", "effort": "7",
            "set_time": "09:15",
        }]
