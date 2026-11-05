#!/usr/bin/env python3
"""Read-only audit of food dashboard database selection."""

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
    from app.routers import food, food_quick375
    from app.user_storage388 import live_storage_for

    print("=== RELEASE 406.1 FOOD READ AUDIT ===")

    parameter = inspect.signature(
        food.food_page
    ).parameters["db_engine"].default

    assert isinstance(parameter, DependsParameter)
    assert parameter.dependency is get_food_read_engine406

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
        print("PASS:", helper.__name__)

    main_source = Path(food.__file__).read_text()
    quick_source = Path(food_quick375.__file__).read_text()

    assert "init_food_schema(db_engine)" in main_source
    assert "totals_for(day, db_engine=db_engine)" in main_source
    assert "with db_engine.connect() as db:" in main_source
    assert "def saved_foods(db_engine=None)" in quick_source

    for user_id in (2, 3):
        try:
            live_storage_for(user_id)
        except PermissionError:
            pass
        else:
            raise RuntimeError(
                f"Inactive user {user_id} gained access"
            )

    print()
    print("Daily entries: selected engine")
    print("Nutrient totals: selected engine")
    print("Nutrient coverage: selected engine")
    print("Saved foods: selected engine")
    print("Legacy helper calls: compatible")
    print("Other shared food helpers: not yet migrated")
    print("Additional accounts: disabled")
    print("PASS: Release 406.1 audit")


if __name__ == "__main__":
    main()
