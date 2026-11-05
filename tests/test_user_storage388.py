"""Release 388 inactive per-user storage boundary tests."""

import os
import sqlite3
import stat

import pytest

from app import config
from app.user_storage388 import (
    inspect_storage,
    live_storage_for,
    planned_storage,
    prepare_inactive_storage,
)


def test_administrator_keeps_existing_paths(tmp_path):
    plan = planned_storage(1, tmp_path)

    assert plan.mode == "legacy-admin"
    assert plan.database == tmp_path / "tracker.db"
    assert plan.coa == tmp_path / "uploads" / "coa"
    assert plan.labs == tmp_path / "uploads" / "labs"


def test_future_user_paths_are_disjoint(tmp_path):
    first = planned_storage(2, tmp_path)
    second = planned_storage(3, tmp_path)

    assert first.database != second.database
    assert first.coa != second.coa
    assert first.labs != second.labs
    assert first.backups != second.backups

    assert first.database.is_relative_to(first.root)
    assert second.database.is_relative_to(second.root)


@pytest.mark.parametrize(
    "invalid",
    [-1, 0, True, False, "2", "../2", None, 2.0, 2147483648],
)
def test_invalid_user_ids_are_rejected(tmp_path, invalid):
    with pytest.raises(ValueError):
        planned_storage(invalid, tmp_path)


def test_live_access_remains_admin_only(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)

    with sqlite3.connect(tmp_path / "tracker.db") as db:
        db.execute(
            "CREATE TABLE private_marker (value TEXT)"
        )
        db.execute(
            "INSERT INTO private_marker VALUES ('legacy-private')"
        )

    legacy = live_storage_for(1)
    assert legacy.database == tmp_path / "tracker.db"

    for user_id in (2, 3, 100):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)


def test_inactive_store_is_empty_and_private(tmp_path):
    store = prepare_inactive_storage(2, tmp_path)

    assert store.mode == "reserved-inactive"
    assert store.database.is_file()
    assert store.coa.is_dir()
    assert store.labs.is_dir()
    assert store.backups.is_dir()

    with sqlite3.connect(store.database) as db:
        tables = db.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
        """).fetchall()
        assert tables == []

    assert stat.S_IMODE(store.root.stat().st_mode) == 0o700
    assert stat.S_IMODE(store.database.stat().st_mode) == 0o600

    overview = inspect_storage(2, tmp_path)
    assert overview["live_access_allowed"] is False


def test_provisioning_never_overwrites_existing_user(tmp_path):
    original = prepare_inactive_storage(2, tmp_path)

    with pytest.raises(FileExistsError):
        prepare_inactive_storage(2, tmp_path)

    assert original.database.is_file()


def test_admin_provisioning_is_forbidden(tmp_path):
    with pytest.raises(PermissionError):
        prepare_inactive_storage(1, tmp_path)


def test_symlinked_user_root_is_rejected(tmp_path):
    external = tmp_path.parent / (
        tmp_path.name + "-external"
    )
    external.mkdir()

    (tmp_path / "users").symlink_to(
        external, target_is_directory=True
    )

    with pytest.raises(ValueError):
        prepare_inactive_storage(2, tmp_path)

    assert not (external / "2").exists()


def test_no_existing_legacy_data_is_moved(tmp_path):
    legacy = tmp_path / "tracker.db"
    legacy.write_bytes(b"unchanged-legacy-data")

    prepare_inactive_storage(2, tmp_path)

    assert legacy.read_bytes() == b"unchanged-legacy-data"


def test_storage_planning_has_no_side_effects(tmp_path):
    planned_storage(2, tmp_path)
    planned_storage(3, tmp_path)

    assert not (tmp_path / "users").exists()
