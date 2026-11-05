"""Release 409: background storage boundary inventory tests."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT / "scripts"
    / "tracker-background-storage-audit409.py"
)


def load_audit():
    spec = importlib.util.spec_from_file_location(
        "tracker_background_storage409",
        SCRIPT,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def report():
    return load_audit().build_report()


def test_background_inventory_validates(report):
    load_audit().validate(report)


def test_browser_backup_and_maintenance_guards_preserved(report):
    expected = {
        "backups": "require_backup_storage397",
        "maintenance_review": "require_direct_storage397",
        "sqlite_viewer": "require_direct_storage397",
        "record_explorer": "require_direct_storage397",
    }

    for name, dependency in expected.items():
        item = report["browser_guards"][name]
        assert item["required"] == dependency
        assert item["declared"] is True


def test_background_entrypoints_remain_explicit(report):
    modules = report["python_targets"]

    for name in (
        "backup_entrypoint",
        "replication_entrypoint",
        "maintenance_entrypoint",
    ):
        assert modules[name]["executable_main"] is True


def test_backup_database_access_remains_visible(report):
    calls = report["python_targets"][
        "backup_library"
    ]["direct_database_calls"]

    assert any(
        item["call"] == "sqlite3.connect"
        for item in calls
    )


def test_legacy_shell_backup_is_not_misclassified(report):
    item = report["shell_targets"][
        "legacy_shell_backup"
    ]

    assert item["retired_entrypoint"]
    assert not item["calls_sqlite3_cli"]
    assert not item["calls_archive_cli"]
    assert not item["uses_tracker_data_dir"]


def test_background_isolation_is_not_claimed_complete(report):
    assert report["multi_user_enabled"] is False
    assert report["application_isolation_complete"] is False
    assert report["background_job_isolation_complete"] is False
    assert report["status"] == "migration-in-progress"


def test_missing_guard_fails_validation(report):
    report["browser_guards"]["backups"]["declared"] = False

    with pytest.raises(RuntimeError):
        load_audit().validate(report)


def test_missing_sqlite_call_fails_validation(report):
    report["python_targets"][
        "backup_library"
    ]["direct_database_calls"] = []

    with pytest.raises(RuntimeError):
        load_audit().validate(report)


def test_report_does_not_execute_backup_jobs(report):
    assert report["scope"] == (
        "source-only; no background processes executed"
    )


def test_secondary_accounts_still_disabled():
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)
