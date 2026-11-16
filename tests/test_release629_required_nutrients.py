"""Release 629: new saved foods must supply every tracked nutrient."""
import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.routers import food, food_review378
from app.food_read_engine406 import get_food_read_engine406
from app.food_storage_guard391 import require_food_storage391


@pytest.fixture
def browser():
    engine = create_engine("sqlite://",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    app = FastAPI()
    app.include_router(food.router)
    app.include_router(food_review378.router)
    app.dependency_overrides[get_food_read_engine406] = lambda: engine
    app.dependency_overrides[require_food_storage391] = lambda: None
    with TestClient(app) as client:
        yield client, engine
    engine.dispose()


def payload(**nutrients):
    values = {key: "0" for key in food.NUTRIENTS}
    values.update({
        "energy": "120", "proteins": "19", "carbohydrates": "7",
        "fat": "2", "vitamin-b12": "1.2", "potassium": "260",
    })
    values.update(nutrients)
    values.update({
        "name": "Complete Test Yogurt",
        "serving_description": "170 g",
        "day": "2026-11-14",
        "servings": "1",
        "meal": "Breakfast",
    })
    return values


def test_all_sixteen_nutrients_are_populated_and_missing_defaults_zero():
    assert len(food.NUTRIENTS) == 16
    for key in food.NUTRIENTS:
        data = payload()
        data.pop(key)
        result = food.required_food_nutrients629(data)
        assert result[key] == 0.0
        assert len(result) == 16


@pytest.mark.parametrize("unknown", ["", " ", "unknown", "Unknown",
                                       "null", "none", "n/a", "?"])
def test_unknown_and_blank_values_default_to_zero(browser, unknown):
    client, engine = browser
    data = payload()
    data["potassium"] = unknown
    response = client.post("/food/entry", data=data, follow_redirects=False)
    assert response.status_code == 303
    with engine.connect() as db:
        stored = json.loads(db.execute(text(
            "SELECT nutrients FROM tracker_food_products"
        )).scalar_one())
        assert stored["potassium"] == 0.0


@pytest.mark.parametrize("bad", ["nan", "-1", "inf", "100001", "nonsense"])
def test_invalid_values_still_rejected_without_writes(browser, bad):
    client, engine = browser
    data = payload()
    data["potassium"] = bad
    response = client.post("/food/entry", data=data, follow_redirects=False)
    assert response.status_code == 422
    with engine.connect() as db:
        assert db.execute(text(
            "SELECT COUNT(*) FROM tracker_food_products"
        )).scalar_one() == 0
        assert db.execute(text(
            "SELECT COUNT(*) FROM tracker_food_entries"
        )).scalar_one() == 0


def test_all_known_numeric_values_are_saved_including_zero(browser):
    client, engine = browser
    response = client.post("/food/entry", data=payload(),
                           follow_redirects=False)
    assert response.status_code == 303
    with engine.connect() as db:
        raw = db.execute(text(
            "SELECT nutrients FROM tracker_food_products"
        )).scalar_one()
    values = json.loads(raw)
    assert len(values) == len(food.NUTRIENTS)
    assert all(type(v) is float for v in values.values())
    assert values["sodium"] == 0
    assert values["potassium"] == 260


def test_nutrition_correction_defaults_missing_values_on_copy(browser):
    client, engine = browser
    assert client.post("/food/entry", data=payload(),
                       follow_redirects=False).status_code == 303
    with engine.connect() as db:
        entry_id, original_id = db.execute(text(
            "SELECT id, product_id FROM tracker_food_entries"
        )).one()
    correction = payload()
    correction.pop("vitamin-d")
    response = client.post(f"/food/entry/{entry_id}/nutrition",
                           data=correction, follow_redirects=False)
    assert response.status_code == 303
    with engine.connect() as db:
        assert db.execute(text(
            "SELECT COUNT(*) FROM tracker_food_products"
        )).scalar_one() == 2
        corrected_id = db.execute(text(
            "SELECT product_id FROM tracker_food_entries WHERE id=:id"
        ), {"id": entry_id}).scalar_one()
        assert corrected_id != original_id
        corrected = json.loads(db.execute(text(
            "SELECT nutrients FROM tracker_food_products WHERE id=:id"
        ), {"id": corrected_id}).scalar_one())
        assert corrected["vitamin-d"] == 0.0


def test_entry_and_correction_forms_default_unreported_nutrients_to_zero():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] /
              "app/templates/food.html").read_text()
    start = source.index('id="food-entry-form"')
    end = source.index("</form>", start)
    add = source[start:end]
    assert 'placeholder="Unknown"' not in add
    assert add.count('value="0" placeholder="0 if unknown" required>') == 2
    assert 'id="food-nutrient-{{ key }}"' in add
    assert 'name="{{ key }}"' in add
    assert 'id="food-review-warning"' in source
    assert "All 16 nutrients default to 0" in source
    assert "e.parsed_nutrients.get(key) is not none else 0" in source
