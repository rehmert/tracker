"""Release 384: nutrition previews and contextual redirect tests."""

from pathlib import Path
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.routers import (
    food,
    food_quick375,
    food_bundle376,
    food_preview384,
)


def test_previews_preserve_unknown_and_zero():
    raw = {
        "energy": 125,
        "proteins": 0,
        "carbohydrates": None,
        "fat": "2.5",
    }

    result = food_preview384.per_serving(raw)

    assert result["energy"] == 125
    assert result["proteins"] == 0
    assert result["carbohydrates"] is None
    assert result["fat"] == 2.5


def test_invalid_values_do_not_appear():
    result = food_preview384.per_serving({
        "energy": "nan",
        "proteins": -3,
        "carbohydrates": True,
        "fat": "invalid",
    })

    assert all(value is None for value in result.values())


def test_redirect_allowlist():
    response = food_quick375.food_redirect(
        "2026-11-05", "food-recorded"
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/food?day=2026-11-05#food-recorded"
    )

    response = food_quick375.food_redirect(
        "2026-11-05", "https://evil.example"
    )

    assert response.headers["location"] == (
        "/food?day=2026-11-05"
    )


@pytest.fixture
def setup(monkeypatch):
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
    app.include_router(food_bundle376.router)

    with TestClient(app) as client:
        yield client, engine

    engine.dispose()


def test_quick_log_and_favorite_redirects(setup):
    client, engine = setup

    response = client.post(
        "/food/entry",
        data={
            "day": "2026-11-05",
            "name": "Test Yogurt",
            "serving_description": "1 container",
            "servings": "1",
            "meal": "Breakfast",
            "energy": "110",
            "proteins": "20",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith(
        "#food-recorded"
    )

    with engine.connect() as db:
        product_id = db.execute(text("""
            SELECT id FROM tracker_food_products
        """)).scalar_one()

    quick = client.post(
        f"/food/quick/{product_id}",
        data={
            "day": "2026-11-05",
            "meal": "Lunch",
            "servings": "2",
        },
        follow_redirects=False,
    )

    assert quick.status_code == 303
    assert quick.headers["location"].endswith(
        "#food-recorded"
    )

    favorite = client.post(
        f"/food/favorite/{product_id}",
        data={"day": "2026-11-05"},
        follow_redirects=False,
    )

    assert favorite.status_code == 303
    assert favorite.headers["location"].endswith(
        "#food-quick-log"
    )

    favorites, recent = food_quick375.saved_foods()

    assert len(favorites) == 1
    assert favorites[0]["nutrients"]
    assert recent[0]["nutrients"]


def test_mobile_preview_contract():
    template = Path("app/templates/food.html").read_text()

    assert template.count(
        'data-food384-preview'
    ) == 3

    assert "e.macro_per_serving" in template

    assert "tracker-food384.css?v=384" in template
    assert "tracker-food384.js?v=384" in template
    assert 'name="day" value="{{ day }}"' in template

    script = Path(
        "app/static/js/tracker-food384.js"
    ).read_text()

    assert "data-food384-value" in script
    assert "scrollIntoView" in script
