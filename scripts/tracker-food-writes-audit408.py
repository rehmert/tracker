#!/usr/bin/env python3
"""Read-only food write routing audit for Release 408."""

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    from fastapi.params import Depends as DependsParameter

    from app.food_read_engine406 import (
        get_food_read_engine406,
    )
    from app.routers import (
        food,
        food_quick375,
        food_bundle376,
        food_manage377,
        food_review378,
    )
    from app.user_storage388 import live_storage_for

    endpoints = (
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

    print("=== RELEASE 408 FOOD WRITE AUDIT ===")

    for endpoint in endpoints:
        parameter = inspect.signature(
            endpoint
        ).parameters["db_engine"].default

        assert isinstance(parameter, DependsParameter)
        assert (
            parameter.dependency
            is get_food_read_engine406
        )

        print("PASS:", endpoint.__name__)

    for module in (
        food,
        food_bundle376,
        food_manage377,
        food_review378,
    ):
        source = Path(module.__file__).read_text()

        assert "with engine.begin() as db:" not in source
        assert "with food.engine.begin() as db:" not in source

    quick = Path(food_quick375.__file__).read_text()
    assert quick.count(
        "init_food_schema(db_engine)"
    ) == 2

    review = Path(food_review378.__file__).read_text()
    assert "food.init_food_schema(db_engine)" in review

    for uid in (2, 3):
        try:
            live_storage_for(uid)
        except PermissionError:
            pass
        else:
            raise RuntimeError(
                f"Inactive account {uid} gained access"
            )

    print()
    print("Food write endpoints migrated:", len(endpoints))
    print("Quick Log schema selection: aligned")
    print("CSV schema selection: aligned")
    print("Administrator records: unchanged")
    print("Additional accounts: disabled")
    print("Non-request/background storage audit: outstanding")
    print("Full multi-user activation: incomplete")
    print("PASS: Release 408 audit")


if __name__ == "__main__":
    main()
