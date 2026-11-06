"""Release 425 water tracking and Food Journal regressions."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.routing import APIRoute
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.food_water425 import (
    WATER_TARGET_OZ,
    init_water_schema,
    parse_ounces,
    water_report,
)
from app.food_read_engine406 import get_food_read_engine406
from app.food_storage_guard391 import require_food_storage391
from app.routers import food, food_quick375


@pytest.fixture
def isolated(monkeypatch):
    db_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    monkeypatch.setattr(food, "engine", db_engine)
    monkeypatch.setattr(food_quick375, "engine", db_engine)

    # This is the critical fixture fix:
    # create the table BEFORE testing invalid requests.
    # Invalid POSTs correctly do not initialize storage.
    init_water_schema(db_engine)

    app = FastAPI()
    app.include_router(food.router)

    with TestClient(app) as client:
        yield client, db_engine

    db_engine.dispose()


def test_target_and_quantity_validation():
    assert WATER_TARGET_OZ == 140
    assert parse_ounces("16") == 16
    assert parse_ounces("16.125") == 16.13
    assert parse_ounces("140") == 140

    invalid = (
        "", "0", "-2", "nan", "inf",
        "not-water", "257", "0.001",
    )

    for value in invalid:
        with pytest.raises(ValueError):
            parse_ounces(value)


def test_unlogged_day_is_not_zero_intake(isolated):
    _, engine = isolated

    report = water_report("2026-11-05", engine)

    assert report["count"] == 0
    assert report["total"] == 0
    assert report["target"] == 140
    assert report["percent"] == 0


def test_quick_add_and_daily_totals(isolated):
    client, engine = isolated

    for amount in ("16", "24", "32"):
        response = client.post(
            "/food/water",
            data={
                "day": "2026-11-05",
                "ounces": amount,
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == (
            "/food?day=2026-11-05#food-water"
        )

    report = water_report("2026-11-05", engine)

    assert report["total"] == 72
    assert report["remaining"] == 68
    assert report["percent"] == 51
    assert report["count"] == 3

    assert water_report(
        "2026-11-06", engine
    )["count"] == 0

    food.init_food_schema(engine)

    # Water entries never become food entries.
    with engine.connect() as db:
        food_count = db.execute(text(
            "SELECT COUNT(*) FROM tracker_food_entries"
        )).scalar_one()

    assert food_count == 0

    assert food.totals_for(
        "2026-11-05", db_engine=engine
    )["energy"] == 0

    assert food.nutrient_coverage(
        "2026-11-05", db_engine=engine
    )[1] == 0


def test_water_target_overage(isolated):
    client, engine = isolated

    for amount in ("100", "60"):
        response = client.post(
            "/food/water",
            data={
                "day": "2026-11-05",
                "ounces": amount,
            },
            follow_redirects=False,
        )

        assert response.status_code == 303

    report = water_report("2026-11-05", engine)

    assert report["total"] == 160
    assert report["over"] == 20
    assert report["remaining"] == 0
    assert report["percent"] == 100


def test_invalid_water_never_writes(isolated):
    client, engine = isolated

    for amount in ("0", "-1", "nan", "999", "0.001"):
        response = client.post(
            "/food/water",
            data={
                "day": "2026-11-05",
                "ounces": amount,
            },
            follow_redirects=False,
        )

        assert response.status_code == 422

    assert water_report(
        "2026-11-05", engine
    )["count"] == 0

    response = client.post(
        "/food/water",
        data={
            "day": "not-a-date",
            "ounces": "16",
        },
        follow_redirects=False,
    )

    assert response.status_code == 422

    assert water_report(
        "2026-11-05", engine
    )["count"] == 0


def test_delete_cannot_remove_wrong_day(isolated):
    client, engine = isolated

    response = client.post(
        "/food/water",
        data={
            "day": "2026-11-05",
            "ounces": "20",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    entry_id = water_report(
        "2026-11-05", engine
    )["entries"][0]["id"]

    wrong = client.post(
        f"/food/water/{entry_id}/delete",
        data={"day": "2026-11-06"},
        follow_redirects=False,
    )

    assert wrong.status_code == 404

    assert water_report(
        "2026-11-05", engine
    )["count"] == 1

    valid = client.post(
        f"/food/water/{entry_id}/delete",
        data={"day": "2026-11-05"},
        follow_redirects=False,
    )

    assert valid.status_code == 303

    assert water_report(
        "2026-11-05", engine
    )["count"] == 0


def test_water_routes_remain_authorized():
    routes = {
        route.path: route
        for route in food.router.routes
        if isinstance(route, APIRoute)
    }

    for path in (
        "/food/water",
        "/food/water/{entry_id}/delete",
    ):
        assert path in routes

        dependencies = {
            dependency.call
            for dependency in routes[path].dependant.dependencies
        }

        assert require_food_storage391 in dependencies
        assert get_food_read_engine406 in dependencies


def test_template_retains_original_accordions():
    template = (
        Path(__file__).resolve().parents[1]
        / "app/templates/food.html"
    ).read_text()

    assert template.count('data-food382-section="') == 9
    assert template.count('id="food-water"') == 1
    assert 'Water target progress' in template
    assert 'name="ounces" value="8"' in template
    assert 'name="ounces" value="32"' in template
    assert 'food425-water-card' in template
    assert 'food425-water-log' in template
    assert '140 oz goal' in template
