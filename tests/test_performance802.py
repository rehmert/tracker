import json
from app.routers.food import summarize_food_rows802, NUTRIENTS, to_float

def test_food_summary_preserves_unknown_and_zero():
    rows = [{"parsed_nutrients": {"energy": 100, "proteins": 0}, "servings": 1.5},
            {"parsed_nutrients": {"energy": 50, "proteins": None}, "servings": 2}]
    totals, coverage, count = summarize_food_rows802(rows)
    assert totals["energy"] == 250
    assert totals["proteins"] == 0
    assert coverage["proteins"] == 1
    assert coverage["energy"] == count == 2
    assert set(totals) == set(NUTRIENTS)
