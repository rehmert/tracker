"""Release 408.2: verify truthful food isolation inventory."""

import importlib.util
import inspect
from pathlib import Path

from fastapi.params import Depends as DependsParameter

from app.food_read_engine406 import get_food_read_engine406
from app.routers import (
    food,
    food_bundle376,
    food_manage377,
    food_review378,
)


ROOT = Path(__file__).resolve().parents[1]


def load_inventory():
    path = (
        ROOT / "scripts"
        / "tracker-isolation-inventory393.py"
    )

    spec = importlib.util.spec_from_file_location(
        "tracker_isolation_inventory4082",
        path,
    )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def test_all_migrated_modules_report_selected_engines():
    audit = load_inventory()

    for filename in (
        "app/routers/food.py",
        "app/routers/food_bundle376.py",
        "app/routers/food_manage377.py",
        "app/routers/food_review378.py",
    ):
        signals = audit.scan_module(
            ROOT / filename
        )["signals"]

        assert "selected_engine_operation" in signals
        assert "global_engine_operation" not in signals


def test_inventory_remains_explicitly_incomplete():
    report = load_inventory().build_inventory()

    assert report["multi_user_enabled"] is False
    assert report["application_isolation_complete"] is False
    assert report["status"] == "migration-in-progress"


def test_food_write_authorization_contracts():
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

    for endpoint in endpoints:
        dependency = inspect.signature(
            endpoint
        ).parameters["db_engine"].default

        assert isinstance(
            dependency,
            DependsParameter,
        )

        assert dependency.dependency is (
            get_food_read_engine406
        )


def test_legacy_import_not_mistaken_for_direct_operation():
    signals = load_inventory().scan_module(
        ROOT / "app/routers/food.py"
    )["signals"]

    assert "global_engine_import" in signals
    assert "global_engine_operation" not in signals


def test_secondary_accounts_still_disabled():
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3):
        try:
            live_storage_for(user_id)
        except PermissionError:
            continue

        raise AssertionError(
            "Secondary account unexpectedly enabled"
        )
