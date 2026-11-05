"""Release 405: request-authorized quick-food writes."""

import inspect

import pytest

from fastapi import FastAPI, HTTPException
from fastapi.params import Depends as DependsParameter
from fastapi.testclient import TestClient

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app import session_auth385
from app.food_engine392 import get_food_engine392
from app.routers import food, food_quick375


@pytest.mark.parametrize(
    "endpoint",
    [
        food_quick375.quick_log,
        food_quick375.toggle_favorite,
    ],
)
def test_write_endpoint_declares_authorized_engine(endpoint):
    dependency = inspect.signature(
        endpoint
    ).parameters["db_engine"].default

    assert isinstance(dependency, DependsParameter)
    assert dependency.dependency is get_food_engine392


@pytest.fixture
def isolated_food(monkeypatch):
    """Exercise real HTTP routes against a memory-only database."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    monkeypatch.setattr(
        session_auth385,
        "enabled",
        lambda: False,
    )

    monkeypatch.setattr(food, "engine", engine)
    monkeypatch.setattr(food_quick375, "engine", engine)

    food.init_food_schema()

    with engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO tracker_food_products
                    (barcode, name, serving_description,
                     nutrients, source)
                VALUES
                    ('1234567890123', 'Test Yogurt',
                     '1 container', '{}', 'manual')
            """)
        )

    application = FastAPI()
    application.include_router(food_quick375.router)

    # Explicit dependency override must select the
    # isolated engine used by the test.
    application.dependency_overrides[
        get_food_engine392
    ] = lambda: engine

    with TestClient(application) as browser:
        yield browser, engine, application

    engine.dispose()


def test_quick_log_writes_to_injected_engine(isolated_food):
    browser, engine, _ = isolated_food

    response = browser.post(
        "/food/quick/1",
        data={
            "day": "2026-11-05",
            "servings": "2",
            "meal": "Lunch",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    with engine.connect() as db:
        entries = db.execute(
            text("""
                SELECT product_id, eaten_on, meal, servings
                FROM tracker_food_entries
            """)
        ).all()

    assert len(entries) == 1
    assert tuple(entries[0]) == (
        1,
        "2026-11-05",
        "Lunch",
        2.0,
    )


def test_favorite_toggle_uses_injected_engine(isolated_food):
    browser, engine, _ = isolated_food

    for expected in (1, 0):
        response = browser.post(
            "/food/favorite/1",
            data={"day": "2026-11-05"},
            follow_redirects=False,
        )

        assert response.status_code == 303

        with engine.connect() as db:
            count = db.execute(
                text(
                    "SELECT COUNT(*) "
                    "FROM tracker_food_favorites"
                )
            ).scalar_one()

        assert count == expected


@pytest.mark.parametrize(
    "path,data",
    [
        (
            "/food/quick/1",
            {
                "day": "2026-11-05",
                "servings": "1",
                "meal": "Snack",
            },
        ),
        (
            "/food/favorite/1",
            {"day": "2026-11-05"},
        ),
    ],
)
def test_denied_engine_dependency_prevents_writes(
    isolated_food,
    path,
    data,
):
    browser, engine, application = isolated_food

    def deny():
        raise HTTPException(
            503,
            "Authorized food engine unavailable",
        )

    application.dependency_overrides[
        get_food_engine392
    ] = deny

    response = browser.post(
        path,
        data=data,
        follow_redirects=False,
    )

    assert response.status_code == 503

    with engine.connect() as db:
        entry_count = db.execute(
            text(
                "SELECT COUNT(*) "
                "FROM tracker_food_entries"
            )
        ).scalar_one()

        favorite_count = db.execute(
            text(
                "SELECT COUNT(*) "
                "FROM tracker_food_favorites"
            )
        ).scalar_one()

    assert entry_count == 0
    assert favorite_count == 0


def test_saved_food_helper_retains_existing_signature():
    signature = inspect.signature(
        food_quick375.saved_foods
    )

    assert len(signature.parameters) == 0


def test_secondary_user_storage_still_disabled():
    from app.user_storage388 import live_storage_for

    for uid in (2, 3):
        with pytest.raises(PermissionError):
            live_storage_for(uid)
