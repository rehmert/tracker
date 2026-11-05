"""Release 378 isolated CSV, corrections and meal totals tests."""

import csv
import io
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.routers import (
    food,
    food_quick375,
    food_bundle376,
    food_manage377,
    food_review378,
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
    for router in (
        food.router,
        food_quick375.router,
        food_bundle376.router,
        food_manage377.router,
        food_review378.router,
    ):
        app.include_router(router)

    with TestClient(app) as client:
        yield client, engine

    engine.dispose()


def add(client, name="Greek Yogurt"):
    response = client.post(
        "/food/entry",
        data={
            "day": "2026-11-05",
            "name": name,
            "serving_description": "1 cup",
            "servings": "2",
            "meal": "Breakfast",
            "energy": "100",
            "proteins": "10",
            "sodium": "0",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_correction_preserves_other_entries(setup):
    client, engine = setup
    add(client)

    client.post(
        "/food/entry",
        data={
            "day": "2026-11-06",
            "name": "Greek Yogurt",
            "serving_description": "1 cup",
            "servings": "1",
            "meal": "Breakfast",
            "energy": "100",
            "proteins": "10",
            "sodium": "0",
        },
        follow_redirects=False,
    )

    with engine.connect() as db:
        first = db.execute(text("""
            SELECT id, product_id
            FROM tracker_food_entries
            WHERE eaten_on='2026-11-05'
        """)).one()

        second = db.execute(text("""
            SELECT id, product_id
            FROM tracker_food_entries
            WHERE eaten_on='2026-11-06'
        """)).one()

    assert first.product_id == second.product_id

    response = client.post(
        f"/food/entry/{first.id}/nutrition",
        data={
            "day": "2026-11-05",
            "name": "Corrected Greek Yogurt",
            "serving_description": "1 cup",
            "energy": "125",
            "proteins": "15",
            "sodium": "0",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    with engine.connect() as db:
        after_first = db.execute(text("""
            SELECT product_id FROM tracker_food_entries
            WHERE id=:id
        """), {"id": first.id}).scalar_one()

        after_second = db.execute(text("""
            SELECT product_id FROM tracker_food_entries
            WHERE id=:id
        """), {"id": second.id}).scalar_one()

        assert after_first != after_second
        assert after_second == second.product_id

    assert food.totals_for("2026-11-05")["energy"] == 250
    assert food.totals_for("2026-11-06")["energy"] == 100


def test_invalid_correction_is_atomic(setup):
    client, engine = setup
    add(client)

    with engine.connect() as db:
        before = db.execute(text("""
            SELECT id, product_id FROM tracker_food_entries
        """)).one()

    result = client.post(
        f"/food/entry/{before.id}/nutrition",
        data={
            "day": "2026-11-05",
            "name": "Still Yogurt",
            "serving_description": "1 cup",
            "energy": "-10",
        },
        follow_redirects=False,
    )

    assert result.status_code == 422

    with engine.connect() as db:
        after = db.execute(text("""
            SELECT id, product_id FROM tracker_food_entries
        """)).one()

        count = db.execute(text("""
            SELECT COUNT(*) FROM tracker_food_products
        """)).scalar_one()

    assert tuple(before) == tuple(after)
    assert count == 1


def test_meal_summary_and_missing_nutrients(setup):
    client, engine = setup
    add(client)

    summary = food_review378.meal_summary("2026-11-05")
    breakfast = summary[0]

    assert breakfast["name"] == "Breakfast"
    assert breakfast["count"] == 1
    assert breakfast["totals"]["energy"] == 200
    assert breakfast["totals"]["proteins"] == 20
    assert breakfast["reported"]["fat"] == 0


def test_csv_export_unknown_blank_and_formula_safety(setup):
    client, engine = setup
    add(client, '=HYPERLINK("https://example.org")')

    response = client.get(
        "/food/export.csv?day=2026-11-05"
    )
    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert "attachment;" in response.headers[
        "content-disposition"
    ]

    rows = list(csv.DictReader(
        io.StringIO(response.text.lstrip("\ufeff"))
    ))

    assert len(rows) == 1
    assert rows[0]["Food"].startswith("'=")
    assert rows[0]["Calories (kcal)"] == "200.0"
    assert rows[0]["Protein (g)"] == "20.0"
    assert rows[0]["Potassium (mg)"] == ""


def test_invalid_export_day_rejected(setup):
    client, engine = setup
    result = client.get(
        "/food/export.csv?day=not-a-date"
    )
    assert result.status_code == 422
