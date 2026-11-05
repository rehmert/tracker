"""Release 377: isolated food editing and template management."""

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
    app.include_router(food_manage377.router)

    with TestClient(app) as client:
        yield client, engine

    engine.dispose()


def add_entry(client):
    response = client.post(
        "/food/entry",
        data={
            "day": "2026-11-05",
            "name": "Test Chicken",
            "serving_description": "100 g",
            "servings": "1",
            "meal": "Dinner",
            "energy": "165",
            "proteins": "31",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_edit_servings_meal_and_date(setup):
    client, engine = setup
    add_entry(client)

    with engine.connect() as db:
        entry_id = db.execute(text("""
            SELECT id FROM tracker_food_entries
        """)).scalar_one()

    response = client.post(
        f"/food/entry/{entry_id}/edit",
        data={
            "original_day": "2026-11-05",
            "day": "2026-11-06",
            "meal": "Lunch",
            "servings": "2.5",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    with engine.connect() as db:
        row = db.execute(text("""
            SELECT eaten_on, meal, servings
            FROM tracker_food_entries
            WHERE id=:id
        """), {"id": entry_id}).one()

        products = db.execute(text("""
            SELECT COUNT(*) FROM tracker_food_products
        """)).scalar_one()

    assert tuple(row) == (
        "2026-11-06", "Lunch", 2.5
    )
    assert products == 1

    totals = food.totals_for("2026-11-06")
    assert totals["energy"] == 412.5
    assert totals["proteins"] == 77.5


def test_invalid_edit_preserves_original(setup):
    client, engine = setup
    add_entry(client)

    with engine.connect() as db:
        entry_id = db.execute(text("""
            SELECT id FROM tracker_food_entries
        """)).scalar_one()

    for servings, meal in (
        ("0", "Lunch"),
        ("101", "Lunch"),
        ("nan", "Lunch"),
        ("1", "Invalid"),
    ):
        response = client.post(
            f"/food/entry/{entry_id}/edit",
            data={
                "original_day": "2026-11-05",
                "day": "2026-11-06",
                "meal": meal,
                "servings": servings,
            },
            follow_redirects=False,
        )
        assert response.status_code == 422

    wrong_original = client.post(
        f"/food/entry/{entry_id}/edit",
        data={
            "original_day": "2026-11-04",
            "day": "2026-11-06",
            "meal": "Lunch",
            "servings": "1",
        },
        follow_redirects=False,
    )
    assert wrong_original.status_code == 404

    with engine.connect() as db:
        row = db.execute(text("""
            SELECT eaten_on, meal, servings
            FROM tracker_food_entries
            WHERE id=:id
        """), {"id": entry_id}).one()

    assert tuple(row) == (
        "2026-11-05", "Dinner", 1.0
    )


def test_rename_and_delete_template_preserves_history(setup):
    client, engine = setup
    add_entry(client)

    create = client.post(
        "/food/template/save",
        data={
            "day": "2026-11-05",
            "meal": "Dinner",
            "name": "Old Name",
        },
        follow_redirects=False,
    )
    assert create.status_code == 303

    with engine.connect() as db:
        template_id = db.execute(text("""
            SELECT id FROM tracker_food_meal_templates
        """)).scalar_one()

    rename = client.post(
        f"/food/template/{template_id}/rename",
        data={
            "day": "2026-11-05",
            "name": "New Name",
        },
        follow_redirects=False,
    )
    assert rename.status_code == 303

    with engine.connect() as db:
        assert db.execute(text("""
            SELECT name FROM tracker_food_meal_templates
        """)).scalar_one() == "New Name"

    delete = client.post(
        f"/food/template/{template_id}/delete",
        data={"day": "2026-11-05"},
        follow_redirects=False,
    )
    assert delete.status_code == 303

    with engine.connect() as db:
        assert db.execute(text("""
            SELECT COUNT(*) FROM tracker_food_meal_templates
        """)).scalar_one() == 0

        assert db.execute(text("""
            SELECT COUNT(*)
            FROM tracker_food_meal_template_items
        """)).scalar_one() == 0

        assert db.execute(text("""
            SELECT COUNT(*) FROM tracker_food_entries
        """)).scalar_one() == 1

        assert db.execute(text("""
            SELECT COUNT(*) FROM tracker_food_products
        """)).scalar_one() == 1


def test_missing_template_rejected(setup):
    client, engine = setup

    for suffix, data in (
        ("rename", {
            "day": "2026-11-05",
            "name": "Updated",
        }),
        ("delete", {
            "day": "2026-11-05",
        }),
    ):
        response = client.post(
            f"/food/template/999999/{suffix}",
            data=data,
            follow_redirects=False,
        )
        assert response.status_code == 404
