#!/usr/bin/env python3
"""Read-only Release 407.1 food dashboard audit."""

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    from app.routers import (
        food,
        food_bundle376,
        food_review378,
        food_week379,
    )
    from app.user_storage388 import live_storage_for

    print("=== RELEASE 407.1 FOOD DASHBOARD AUDIT ===")

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

        assert parameter.default is None

        print(
            "PASS:",
            helper.__name__,
            "supports selected engine",
        )

    dashboard = Path(food.__file__).read_text()

    for expression in (
        "search_products(query, db_engine=db_engine)",
        "weekly_summary(day, db_engine=db_engine)",
        "meal_templates(db_engine=db_engine)",
        "meal_summary(day, db_engine=db_engine)",
        "week_details(day, db_engine=db_engine)",
    ):
        assert expression in dashboard

    print("PASS: Dashboard propagates authorized engine")

    bundle = Path(
        food_bundle376.__file__
    ).read_text()

    review = Path(
        food_review378.__file__
    ).read_text()

    assert bundle.count(
        "with food.engine.begin() as db:"
    ) == 2

    assert review.count(
        "with food.engine.begin() as db:"
    ) == 1

    print("PASS: Existing write transaction paths retained")

    for user_id in (2, 3):
        try:
            live_storage_for(user_id)
        except PermissionError:
            pass
        else:
            raise RuntimeError(
                f"Inactive user {user_id} gained live access"
            )

    print()
    print("Product search: selected engine")
    print("Weekly macro summaries: selected engine")
    print("Meal templates: selected engine")
    print("Meal nutrition: selected engine")
    print("Weekly nutrient coverage: selected engine")
    print("Legacy helper interfaces: supported")
    print("Additional users: disabled")
    print("Remaining write migrations: incomplete")
    print("Application-wide isolation: incomplete")

    print("PASS: Release 407.1 audit")


if __name__ == "__main__":
    main()
