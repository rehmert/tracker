"""Release 376: isolated food bundle regression checks."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.routers import food, food_quick375, food_bundle376


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


def add(client, day="2026-11-05", meal="Breakfast"):
    return client.post(
        "/food/entry",
        data={
            "day": day,
            "name": "Favorite Yogurt",
            "serving_description": "1 container",
            "servings": "1",
            "meal": meal,
            "energy": "130",
            "proteins": "20",
            "carbohydrates": "8",
            "fat": "2",
        },
        follow_redirects=False,
    )


def test_duplicate_product_reuse(setup):
    client, engine = setup
    assert add(client).status_code == 303
    assert add(client).status_code == 303

    with engine.connect() as db:
        products = db.execute(text("""
            SELECT COUNT(*) FROM tracker_food_products
        """)).scalar_one()

        entries = db.execute(text("""
            SELECT COUNT(*) FROM tracker_food_entries
        """)).scalar_one()

    assert products == 1
    assert entries == 2


def test_saved_food_search(setup):
    client, engine = setup
    add(client)

    result = food_bundle376.search_products("yogurt")
    assert len(result) == 1
    assert result[0]["name"] == "Favorite Yogurt"

    assert food_bundle376.search_products("not-found") == []


def test_meal_template_reuses_products(setup):
    client, engine = setup
    add(client)

    result = client.post(
        "/food/template/save",
        data={
            "day": "2026-11-05",
            "meal": "Breakfast",
            "name": "Regular Breakfast",
        },
        follow_redirects=False,
    )
    assert result.status_code == 303

    templates = food_bundle376.meal_templates()
    assert len(templates) == 1
    assert templates[0]["item_count"] == 1

    result = client.post(
        f"/food/template/{templates[0]['id']}/log",
        data={"day": "2026-11-06"},
        follow_redirects=False,
    )
    assert result.status_code == 303

    with engine.connect() as db:
        rows = db.execute(text("""
            SELECT eaten_on, meal, servings
            FROM tracker_food_entries
            ORDER BY id
        """)).all()

        products = db.execute(text("""
            SELECT COUNT(*) FROM tracker_food_products
        """)).scalar_one()

    assert len(rows) == 2
    assert tuple(rows[1]) == (
        "2026-11-06", "Breakfast", 1.0
    )
    assert products == 1


def test_weekly_totals_and_missing_values(setup):
    client, engine = setup
    add(client)

    days = food_bundle376.weekly_summary("2026-11-05")
    assert len(days) == 7
    assert days[-1]["totals"]["energy"] == 130
    assert days[-1]["totals"]["proteins"] == 20
    assert days[-1]["foods"] == 1
    assert days[-2]["foods"] == 0

    with engine.begin() as db:
        db.execute(text("""
            UPDATE tracker_food_products
            SET nutrients=:values
        """), {
            "values": json.dumps({
                "energy": None,
                "proteins": 20,
            })
        })

    days = food_bundle376.weekly_summary("2026-11-05")
    assert days[-1]["reported"]["energy"] == 0
    assert days[-1]["reported"]["proteins"] == 1


def test_invalid_template_rejected(setup):
    client, engine = setup

    missing = client.post(
        "/food/template/9999/log",
        data={"day": "2026-11-06"},
        follow_redirects=False,
    )
    assert missing.status_code == 404

    empty = client.post(
        "/food/template/save",
        data={
            "day": "2026-11-05",
            "meal": "Breakfast",
            "name": "Empty Meal",
        },
        follow_redirects=False,
    )
    assert empty.status_code == 422
