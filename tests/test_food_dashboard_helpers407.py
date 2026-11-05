"""Release 407.1: shared dashboard helpers respect selected engines."""

import inspect
import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.routers import (
    food,
    food_bundle376,
    food_review378,
    food_week379,
)


@pytest.fixture
def engines():
    result = []

    for _ in range(2):
        database = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        food_bundle376.init_schema(database)
        result.append(database)

    yield result

    for database in result:
        database.dispose()


def populate(database, name, calories):
    values = {
        nutrient: None
        for nutrient in food.NUTRIENTS
    }

    values.update({
        "energy": calories,
        "proteins": 20,
        "carbohydrates": 10,
        "fat": 5,
    })

    with database.begin() as db:
        db.execute(
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
                "nutrients": json.dumps(values),
            },
        )

        db.execute(
            text("""
                INSERT INTO tracker_food_entries
                    (id, product_id, eaten_on, meal, servings)
                VALUES
                    (1, 1, '2026-11-05', 'Breakfast', 1)
            """)
        )

        db.execute(
            text("""
                INSERT INTO tracker_food_meal_templates
                    (id, name)
                VALUES
                    (1, :name)
            """),
            {"name": name + " Template"},
        )

        db.execute(
            text("""
                INSERT INTO tracker_food_meal_template_items
                    (template_id, product_id, servings, meal)
                VALUES
                    (1, 1, 1, 'Breakfast')
            """)
        )


def test_meal_templates_remain_isolated(engines):
    first, second = engines

    populate(first, "First Yogurt", 120)
    populate(second, "Second Yogurt", 240)

    a = food_bundle376.meal_templates(db_engine=first)
    b = food_bundle376.meal_templates(db_engine=second)

    assert a[0]["id"] == b[0]["id"] == 1
    assert a[0]["name"] == "First Yogurt Template"
    assert b[0]["name"] == "Second Yogurt Template"


def test_saved_product_search_is_isolated(engines):
    first, second = engines

    populate(first, "First Yogurt", 120)
    populate(second, "Second Yogurt", 240)

    a = food_bundle376.search_products(
        "First", db_engine=first
    )
    b = food_bundle376.search_products(
        "First", db_engine=second
    )

    assert len(a) == 1
    assert a[0]["name"] == "First Yogurt"
    assert b == []


def test_weekly_macros_are_isolated(engines):
    first, second = engines

    populate(first, "First", 120)
    populate(second, "Second", 240)

    a = food_bundle376.weekly_summary(
        "2026-11-05", db_engine=first
    )
    b = food_bundle376.weekly_summary(
        "2026-11-05", db_engine=second
    )

    assert sum(
        item["totals"]["energy"] for item in a
    ) == 120

    assert sum(
        item["totals"]["energy"] for item in b
    ) == 240


def test_meal_nutrition_is_isolated(engines):
    first, second = engines

    populate(first, "First", 120)
    populate(second, "Second", 240)

    a = food_review378.meal_summary(
        "2026-11-05", db_engine=first
    )
    b = food_review378.meal_summary(
        "2026-11-05", db_engine=second
    )

    assert a[0]["totals"]["energy"] == 120
    assert b[0]["totals"]["energy"] == 240


def test_weekly_nutrient_coverage_is_isolated(engines):
    first, second = engines

    populate(first, "First", 120)
    populate(second, "Second", 240)

    with second.begin() as db:
        db.execute(
            text("""
                UPDATE tracker_food_products
                SET nutrients=:value
                WHERE id=1
            """),
            {
                "value": json.dumps({
                    key: None for key in food.NUTRIENTS
                }),
            },
        )

    a = food_week379.week_details(
        "2026-11-05", db_engine=first
    )
    b = food_week379.week_details(
        "2026-11-05", db_engine=second
    )

    energy_a = next(
        item for item in a["nutrients"]
        if item["key"] == "energy"
    )

    energy_b = next(
        item for item in b["nutrients"]
        if item["key"] == "energy"
    )

    assert energy_a["complete_days"] == 1
    assert energy_b["complete_days"] == 0


def test_selected_schema_does_not_modify_other_database(engines):
    first, second = engines

    populate(first, "Private", 100)

    food_bundle376.init_schema(second)

    with first.connect() as db:
        count_a = db.execute(
            text("""
                SELECT COUNT(*)
                FROM tracker_food_meal_templates
            """)
        ).scalar_one()

    with second.connect() as db:
        count_b = db.execute(
            text("""
                SELECT COUNT(*)
                FROM tracker_food_meal_templates
            """)
        ).scalar_one()

    assert count_a == 1
    assert count_b == 0


def test_old_helper_calls_remain_supported():
    helpers = (
        food_bundle376.init_schema,
        food_bundle376.search_products,
        food_bundle376.weekly_summary,
        food_bundle376.meal_templates,
        food_review378.meal_summary,
        food_week379.week_details,
    )

    for helper in helpers:
        parameter = inspect.signature(
            helper
        ).parameters["db_engine"]

        assert parameter.default is None, helper.__name__


def test_dashboard_passes_engine_to_all_helpers():
    from pathlib import Path

    source = Path("app/routers/food.py").read_text()

    for expression in (
        "search_products(query, db_engine=db_engine)",
        "weekly_summary(day, db_engine=db_engine)",
        "meal_templates(db_engine=db_engine)",
        "meal_summary(day, db_engine=db_engine)",
        "week_details(day, db_engine=db_engine)",
    ):
        assert expression in source


def test_additional_users_remain_disabled():
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)
