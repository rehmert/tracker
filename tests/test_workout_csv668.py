"""Release 668 CSV contract regression tests (pure, no live database writes)."""
import csv
from io import StringIO

import pytest

from app.workout_csv668 import FIELDS668, parse_routine_csv668, render_routine_csv668


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
