"""Release 408: request-selected food writes and isolation."""

import inspect
import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.params import Depends as DependsParameter
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app import session_auth385
from app.food_read_engine406 import get_food_read_engine406
from app.routers import (
    food,
    food_quick375,
    food_bundle376,
    food_manage377,
    food_review378,
)


WRITE_ENDPOINTS = (
    food.create_food_entry,
    food.save_food_targets,
    food.delete_food_entry,
    food_bundle376.save_meal_template,
    food_bundle376.log_meal_template,
    food_manage377.edit_food_entry,
    food_manage377.rename_meal_template,
    food_manage377.delete_meal_template,
    food_review378.correct_nutrition,
)


@pytest.mark.parametrize("endpoint", WRITE_ENDPOINTS)
def test_every_write_uses_authorized_engine(endpoint):
    parameter = inspect.signature(
        endpoint
    ).parameters["db_engine"].default

    assert isinstance(parameter, DependsParameter)
    assert parameter.dependency is get_food_read_engine406


@pytest.fixture
def isolated(monkeypatch):
    engines = []

    for _ in range(2):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        food_bundle376.init_schema(engine)
        engines.append(engine)

    first, second = engines

    monkeypatch.setattr(
        session_auth385,
        "enabled",
        lambda: False,
    )

    monkeypatch.setattr(food, "engine", first)
    monkeypatch.setattr(food_quick375, "engine", first)

    application = FastAPI()

    for router in (
        food.router,
        food_quick375.router,
        food_bundle376.router,
        food_manage377.router,
        food_review378.router,
    ):
        application.include_router(router)

    # All new routes select the second isolated database.
    application.dependency_overrides[
        get_food_read_engine406
    ] = lambda: second

    with TestClient(application) as client:
        yield client, first, second, application

    for engine in engines:
        engine.dispose()


def count(engine, table):
    assert table in {
        "tracker_food_entries",
        "tracker_food_products",
        "tracker_food_targets",
        "tracker_food_meal_templates",
    }

    with engine.connect() as db:
        return db.execute(
            text(f"SELECT COUNT(*) FROM {table}")
        ).scalar_one()


def add_food(client, day="2026-11-05"):
    return client.post(
        "/food/entry",
        data={
            "day": day,
            "name": "Isolated Chicken",
            "serving_description": "100 g",
            "servings": "1",
            "meal": "Dinner",
            "energy": "165",
            "proteins": "31",
        },
        follow_redirects=False,
    )


def test_create_targets_and_delete_use_selected_engine(isolated):
    client, first, second, _ = isolated

    assert add_food(client).status_code == 303

    assert count(first, "tracker_food_entries") == 0
    assert count(second, "tracker_food_entries") == 1

    result = client.post(
        "/food/targets",
        data={
            "day": "2026-11-05",
            "energy": "2000",
            "proteins": "150",
        },
        follow_redirects=False,
    )
    assert result.status_code == 303

    assert count(first, "tracker_food_targets") == 0
    assert count(second, "tracker_food_targets") == 2

    delete = client.post(
        "/food/entry/1/delete",
        data={"day": "2026-11-05"},
        follow_redirects=False,
    )
    assert delete.status_code == 303

    assert count(second, "tracker_food_entries") == 0
    assert count(first, "tracker_food_entries") == 0


def test_template_creation_log_rename_delete_isolated(isolated):
    client, first, second, _ = isolated

    assert add_food(client).status_code == 303

    create = client.post(
        "/food/template/save",
        data={
            "day": "2026-11-05",
            "meal": "Dinner",
            "name": "Private Dinner",
        },
        follow_redirects=False,
    )
    assert create.status_code == 303

    assert count(first, "tracker_food_meal_templates") == 0
    assert count(second, "tracker_food_meal_templates") == 1

    log = client.post(
        "/food/template/1/log",
        data={"day": "2026-11-06"},
        follow_redirects=False,
    )
    assert log.status_code == 303

    assert count(second, "tracker_food_entries") == 2
    assert count(first, "tracker_food_entries") == 0

    rename = client.post(
        "/food/template/1/rename",
        data={
            "day": "2026-11-05",
            "name": "Renamed Dinner",
        },
        follow_redirects=False,
    )
    assert rename.status_code == 303

    with second.connect() as db:
        name = db.execute(
            text(
                "SELECT name FROM tracker_food_meal_templates"
            )
        ).scalar_one()

    assert name == "Renamed Dinner"

    remove = client.post(
        "/food/template/1/delete",
        data={"day": "2026-11-05"},
        follow_redirects=False,
    )
    assert remove.status_code == 303

    assert count(second, "tracker_food_meal_templates") == 0
    assert count(second, "tracker_food_entries") == 2


def test_entry_edit_and_nutrition_correction_isolated(isolated):
    client, first, second, _ = isolated

    assert add_food(client).status_code == 303

    edit = client.post(
        "/food/entry/1/edit",
        data={
            "original_day": "2026-11-05",
            "day": "2026-11-06",
            "meal": "Lunch",
            "servings": "2",
        },
        follow_redirects=False,
    )
    assert edit.status_code == 303

    correction = client.post(
        "/food/entry/1/nutrition",
        data={
            "day": "2026-11-06",
            "name": "Corrected Chicken",
            "serving_description": "100 g",
            "energy": "180",
            "proteins": "32",
        },
        follow_redirects=False,
    )
    assert correction.status_code == 303

    assert count(first, "tracker_food_products") == 0
    assert count(second, "tracker_food_products") == 2

    with second.connect() as db:
        row = db.execute(
            text("""
                SELECT p.name, e.meal, e.servings
                FROM tracker_food_entries e
                JOIN tracker_food_products p
                  ON p.id = e.product_id
            """)
        ).one()

    assert tuple(row) == (
        "Corrected Chicken", "Lunch", 2.0
    )


@pytest.mark.parametrize(
    "path",
    [
        "/food/entry",
        "/food/targets",
        "/food/entry/1/delete",
        "/food/template/save",
        "/food/template/1/log",
        "/food/entry/1/edit",
        "/food/template/1/rename",
        "/food/template/1/delete",
        "/food/entry/1/nutrition",
    ],
)
def test_denied_engine_prevents_write(isolated, path):
    client, first, second, application = isolated

    def deny():
        raise HTTPException(
            503, "Workspace engine unavailable"
        )

    application.dependency_overrides[
        get_food_read_engine406
    ] = deny

    response = client.post(
        path,
        follow_redirects=False,
    )

    assert response.status_code == 503

    for table in (
        "tracker_food_entries",
        "tracker_food_products",
        "tracker_food_meal_templates",
        "tracker_food_targets",
    ):
        assert count(first, table) == 0
        assert count(second, table) == 0


def test_future_users_remain_disabled():
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)
