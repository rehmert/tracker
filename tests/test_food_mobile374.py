"""Non-destructive contracts for mobile food journal."""
from app.routers import food

def test_food_targets_have_explicit_units():
    assert food.NUTRIENTS["energy"][1] == "kcal"
    assert food.NUTRIENTS["sodium"][1] == "mg"
    assert food.NUTRIENTS["vitamin-d"][1] == "mcg"
    assert "proteins" in food.NUTRIENTS
    assert "fiber" in food.NUTRIENTS

def test_bad_nutrient_values_do_not_propagate():
    assert food.to_float("12.5") == 12.5
    assert food.to_float("n/a") == 0
    assert food.to_float("-5") == 0
    assert food.to_float("nan") == 0
    assert food.to_float("inf") == 0

def test_food_barcode_requires_numeric_code():
    from fastapi import HTTPException
    try:
        food.barcode_lookup("http://localhost/")
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Invalid barcode was accepted")
