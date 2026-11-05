"""Release 406.1: isolated dashboard food reads."""

import inspect
import json

import pytest
from fastapi import HTTPException
from fastapi.params import Depends as DependsParameter
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app import food_read_engine406
from app.routers import food, food_quick375


@pytest.fixture
def engines():
    result = []

    for _ in range(2):
        db_engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        food.init_food_schema(db_engine)
        result.append(db_engine)

    yield result

    for db_engine in result:
        db_engine.dispose()


def populate(db_engine, name, calories):
    nutrients = {
        key: None
        for key in food.NUTRIENTS
    }
    nutrients["energy"] = calories

    with db_engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO tracker_food_products
                    (id, barcode, name,
                     serving_description, nutrients, source)
                VALUES
                    (1, '1234567890123', :name,
                     '1 serving', :nutrients, 'manual')
            """),
            {
                "name": name,
                "nutrients": json.dumps(nutrients),
            },
        )

        connection.execute(
            text("""
                INSERT INTO tracker_food_entries
                    (id, product_id, eaten_on, meal, servings)
                VALUES
                    (1, 1, '2026-11-05', 'Breakfast', 1)
            """)
        )

        connection.execute(
            text("""
                INSERT INTO tracker_food_favorites
                    (product_id) VALUES (1)
            """)
        )


def test_dashboard_declares_engine_dependency():
    parameter = inspect.signature(
        food.food_page
    ).parameters["db_engine"].default

    assert isinstance(parameter, DependsParameter)
    assert (
        parameter.dependency
        is food_read_engine406.get_food_read_engine406
    )


def test_matching_ids_are_isolated(engines):
    first, second = engines

    populate(first, "Account Two", 120)
    populate(second, "Account Three", 240)

    assert food.totals_for(
        "2026-11-05",
        db_engine=first,
    )["energy"] == 120

    assert food.totals_for(
        "2026-11-05",
        db_engine=second,
    )["energy"] == 240

    favorites_a, recent_a = food_quick375.saved_foods(
        db_engine=first
    )
    favorites_b, recent_b = food_quick375.saved_foods(
        db_engine=second
    )

    assert favorites_a[0]["id"] == favorites_b[0]["id"]
    assert favorites_a[0]["name"] == "Account Two"
    assert favorites_b[0]["name"] == "Account Three"
    assert recent_a[0]["name"] == "Account Two"
    assert recent_b[0]["name"] == "Account Three"


def test_nutrient_coverage_is_isolated(engines):
    first, second = engines

    populate(first, "Reported", 150)
    populate(second, "Unreported", 220)

    with second.begin() as db:
        db.execute(
            text("""
                UPDATE tracker_food_products
                SET nutrients=:value
                WHERE id=1
            """),
            {
                "value": json.dumps({
                    key: None
                    for key in food.NUTRIENTS
                }),
            },
        )

    a, count_a = food.nutrient_coverage(
        "2026-11-05",
        db_engine=first,
    )

    b, count_b = food.nutrient_coverage(
        "2026-11-05",
        db_engine=second,
    )

    assert count_a == count_b == 1
    assert a["energy"] == 1
    assert b["energy"] == 0


def test_missing_entry_does_not_leak(engines):
    first, second = engines

    populate(first, "Private Food", 100)

    assert food.totals_for(
        "2026-11-05",
        db_engine=second,
    )["energy"] == 0

    assert food_quick375.saved_foods(
        db_engine=second
    ) == ([], [])


def test_optional_helpers_remain_compatible():
    for helper in (
        food.init_food_schema,
        food.totals_for,
        food.nutrient_coverage,
        food_quick375.saved_foods,
    ):
        parameter = inspect.signature(
            helper
        ).parameters["db_engine"]

        assert parameter.default is None


def test_authorized_dependency_delegates(monkeypatch):
    from app import food_engine392

    marker = object()
    seen = []

    def authorize(request):
        seen.append(request)
        return marker

    monkeypatch.setattr(
        food_engine392,
        "get_food_engine392",
        authorize,
    )

    request = object()

    assert (
        food_read_engine406.get_food_read_engine406(
            request
        )
        is marker
    )

    assert seen == [request]


def test_denial_does_not_return_engine(monkeypatch):
    from app import food_engine392

    def deny(_):
        raise HTTPException(403, "Denied")

    monkeypatch.setattr(
        food_engine392,
        "get_food_engine392",
        deny,
    )

    with pytest.raises(HTTPException) as error:
        food_read_engine406.get_food_read_engine406(
            object()
        )

    assert error.value.status_code == 403


def test_additional_accounts_still_disabled():
    from app.user_storage388 import live_storage_for

    for uid in (2, 3):
        with pytest.raises(PermissionError):
            live_storage_for(uid)
