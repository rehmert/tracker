"""Release 375: isolated food favorites and repeat-entry regressions."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.routers import food, food_quick375


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    monkeypatch.setattr(food, "engine", engine)
    monkeypatch.setattr(food_quick375, "engine", engine)

    app = FastAPI()
    app.include_router(food.router)
    app.include_router(food_quick375.router)

    with TestClient(app) as test_client:
        yield test_client, engine

    engine.dispose()


def make_entry(client):
    response = client.post(
        "/food/entry",
        data={
            "day": "2026-11-05",
            "name": "Test Greek Yogurt",
            "serving_description": "1 container",
            "servings": "1.5",
            "meal": "Breakfast",
            "energy": "100",
            "proteins": "20",
            "sodium": "0",
            # Potassium intentionally unknown.
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_unknown_and_zero_are_distinct(client):
    browser, engine = client
    make_entry(browser)

    with engine.connect() as db:
        raw = db.execute(text(
            "SELECT nutrients FROM tracker_food_products LIMIT 1"
        )).scalar_one()

    values = json.loads(raw)
    assert values["sodium"] == 0
    assert values["potassium"] is None
    assert values["proteins"] == 20

    counts, count = food.nutrient_coverage("2026-11-05")
    assert count == 1
    assert counts["sodium"] == 1
    assert counts["potassium"] == 0


def test_favorite_and_repeat_reuse_same_product(client):
    browser, engine = client
    make_entry(browser)

    with engine.connect() as db:
        product_id = db.execute(text(
            "SELECT id FROM tracker_food_products LIMIT 1"
        )).scalar_one()

    favorite = browser.post(
        f"/food/favorite/{product_id}",
        data={"day": "2026-11-05"},
        follow_redirects=False,
    )
    assert favorite.status_code == 303

    favorites, recent = food_quick375.saved_foods()
    assert any(x["id"] == product_id for x in favorites)
    assert any(x["id"] == product_id for x in recent)

    repeat = browser.post(
        f"/food/quick/{product_id}",
        data={
            "day": "2026-11-06",
            "servings": "2",
            "meal": "Lunch",
        },
        follow_redirects=False,
    )
    assert repeat.status_code == 303

    with engine.connect() as db:
        assert db.execute(text(
            "SELECT COUNT(*) FROM tracker_food_products"
        )).scalar_one() == 1

        rows = db.execute(text("""
            SELECT eaten_on, meal, servings
            FROM tracker_food_entries ORDER BY id
        """)).all()

    assert len(rows) == 2
    assert tuple(rows[1]) == ("2026-11-06", "Lunch", 2.0)

    unfavorite = browser.post(
        f"/food/favorite/{product_id}",
        data={"day": "2026-11-05"},
        follow_redirects=False,
    )
    assert unfavorite.status_code == 303
    assert food_quick375.saved_foods()[0] == []


def test_quick_log_rejects_invalid_inputs(client):
    browser, engine = client
    make_entry(browser)

    with engine.connect() as db:
        product_id = db.execute(text(
            "SELECT id FROM tracker_food_products LIMIT 1"
        )).scalar_one()

    for value in ("0", "-1", "101", "nan", "invalid"):
        result = browser.post(
            f"/food/quick/{product_id}",
            data={
                "day": "2026-11-06",
                "servings": value,
                "meal": "Dinner",
            },
            follow_redirects=False,
        )
        assert result.status_code == 422

    invalid_meal = browser.post(
        f"/food/quick/{product_id}",
        data={
            "day": "2026-11-06",
            "servings": "1",
            "meal": "NotAMeal",
        },
        follow_redirects=False,
    )
    assert invalid_meal.status_code == 422

    missing = browser.post(
        "/food/quick/999999",
        data={
            "day": "2026-11-06",
            "servings": "1",
            "meal": "Lunch",
        },
        follow_redirects=False,
    )
    assert missing.status_code == 404

    with engine.connect() as db:
        assert db.execute(text(
            "SELECT COUNT(*) FROM tracker_food_entries"
        )).scalar_one() == 1


def test_500_quick_food_filters_preserve_existing_submit_forms():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    markup = (root / "app/templates/food.html").read_text()
    script = (root / "app/static/js/tracker-food500.js").read_text()

    for marker in (
        'id="food500-quick-controls"',
        'id="food500-quick-search"',
        'id="food500-quick-scope"',
        'id="food500-quick-count"',
        'id="food500-quick-reset"',
        'id="food500-quick-empty"',
        'data-food500-scope="favorites"',
        'data-food500-scope="recent"',
        'id="food500-recent"',
        'tracker-food500.js?v=500',
    ):
        assert marker in markup, marker
    assert 'action="/food/quick/{{ item.id }}"' in markup
    assert "card.hidden = !visible" in script
    assert "recent.open = true" in script
    assert "fetch(" not in script
    assert ".submit(" not in script
    assert "localStorage" not in script
