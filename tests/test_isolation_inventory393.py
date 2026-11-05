"""Release 393.1: source and runtime inventory distinctions."""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT / "scripts"
    / "tracker-isolation-inventory393.py"
)


def load_inventory():
    spec = importlib.util.spec_from_file_location(
        "tracker_isolation_inventory3931",
        SCRIPT,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inventory_covers_source_routes():
    audit = load_inventory()
    report = audit.build_inventory()

    assert report["source_route_declaration_count"] >= 50
    assert report["global_auth_declared"] is True


def test_runtime_inventory_is_separate():
    audit = load_inventory()
    report = audit.build_inventory()

    assert report["runtime_registered_route_count"] >= 2
    assert report["global_auth_coverage_proven"] is False


def test_inventory_is_explicitly_incomplete():
    audit = load_inventory()
    report = audit.build_inventory()

    assert report["multi_user_enabled"] is False
    assert report["application_isolation_complete"] is False
    assert report["status"] == "migration-in-progress"


def test_all_major_modules_are_inventory_candidates():
    audit = load_inventory()
    report = audit.build_inventory()

    paths = {
        item["path"]
        for item in report["modules"]
    }

    for path in (
        "app/db.py",
        "app/backup.py",
        "app/routers/food.py",
        "app/routers/labs.py",
        "app/routers/coas.py",
        "app/routers/backups.py",
        "app/routers/sqlite_viewer.py",
    ):
        assert path in paths


def test_direct_food_engine_is_still_reported():
    audit = load_inventory()

    findings = audit.scan_module(
        ROOT / "app/routers/food.py"
    )

    assert "global_engine_import" in findings["signals"]
    assert (
        "global_engine_operation"
        in findings["signals"]
    )


def test_existing_database_implementation_preserved():
    for path in (
        "app/db.py",
        "app/user_storage388.py",
        "app/user_db389.py",
    ):
        assert (ROOT / path).is_file()
