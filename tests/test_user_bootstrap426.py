"""Release 426: independently initialized inactive user workspaces."""

import sqlite3
import stat

import pytest

from app.user_bootstrap426 import (
    REQUIRED_TABLES,
    initialize_staged_workspace426,
    verify_staged_workspace426,
)
from app.user_storage388 import (
    live_storage_for,
    planned_storage,
    prepare_inactive_storage,
)


def _tables(path):
    with sqlite3.connect(path) as db:
        return {
            name
            for (name,) in db.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table'
            """)
        }


def test_secondary_workspaces_have_full_independent_schemas(tmp_path):
    first = initialize_staged_workspace426(2, tmp_path)
    second = initialize_staged_workspace426(3, tmp_path)

    assert first.database != second.database
    assert first.coa != second.coa
    assert first.labs != second.labs
    assert first.backups != second.backups

    assert REQUIRED_TABLES <= _tables(first.database)
    assert REQUIRED_TABLES <= _tables(second.database)

    for uid in (2, 3):
        report = verify_staged_workspace426(uid, tmp_path)

        assert report["user_id"] == uid
        assert report["status"] == "inactive"
        assert report["database_available"]
        assert not report["live_access_enabled"]


def test_sqlite_records_cannot_cross_workspaces(tmp_path):
    first = initialize_staged_workspace426(2, tmp_path)
    second = initialize_staged_workspace426(3, tmp_path)

    with sqlite3.connect(first.database) as db:
        db.execute("""
            INSERT INTO compounds
                (name, category, notes, primary_unit)
            VALUES (?, ?, ?, ?)
        """, (
            "first-user-private-compound",
            "other", "", "mg",
        ))

    with sqlite3.connect(second.database) as db:
        rows = db.execute(
            "SELECT name FROM compounds"
        ).fetchall()

        assert rows == []

        db.execute("""
            INSERT INTO compounds
                (name, category, notes, primary_unit)
            VALUES (?, ?, ?, ?)
        """, (
            "second-user-private-compound",
            "other", "", "mg",
        ))

    with sqlite3.connect(first.database) as db:
        first_names = db.execute(
            "SELECT name FROM compounds"
        ).fetchall()

    with sqlite3.connect(second.database) as db:
        second_names = db.execute(
            "SELECT name FROM compounds"
        ).fetchall()

    assert first_names == [
        ("first-user-private-compound",)
    ]

    assert second_names == [
        ("second-user-private-compound",)
    ]


def test_existing_administrator_database_is_unchanged(tmp_path):
    legacy = tmp_path / "tracker.db"

    with sqlite3.connect(legacy) as db:
        db.execute("""
            CREATE TABLE administrator_private (
                value TEXT NOT NULL
            )
        """)
        db.execute("""
            INSERT INTO administrator_private(value)
            VALUES ('admin-only')
        """)

    original_bytes = legacy.read_bytes()

    secondary = initialize_staged_workspace426(
        2, tmp_path
    )

    assert legacy.read_bytes() == original_bytes
    assert "administrator_private" not in _tables(
        secondary.database
    )

    with sqlite3.connect(legacy) as db:
        value = db.execute("""
            SELECT value FROM administrator_private
        """).scalar() if hasattr(
            sqlite3.Cursor, "scalar"
        ) else db.execute("""
            SELECT value FROM administrator_private
        """).fetchone()[0]

    assert value == "admin-only"


def test_private_filesystem_permissions(tmp_path):
    paths = initialize_staged_workspace426(
        2, tmp_path
    )

    assert stat.S_IMODE(
        paths.root.stat().st_mode
    ) == 0o700

    assert stat.S_IMODE(
        paths.database.stat().st_mode
    ) == 0o600

    for directory in (
        paths.coa,
        paths.labs,
        paths.backups,
    ):
        assert stat.S_IMODE(
            directory.stat().st_mode
        ) == 0o700


def test_provisioning_is_exclusive_and_not_a_migration(tmp_path):
    paths = initialize_staged_workspace426(
        2, tmp_path
    )

    with sqlite3.connect(paths.database) as db:
        db.execute("""
            INSERT INTO tracker_food_products
                (name, serving_description, nutrients, source)
            VALUES (?, ?, ?, ?)
        """, (
            "private-food", "one", "{}", "manual",
        ))

    with pytest.raises(FileExistsError):
        initialize_staged_workspace426(2, tmp_path)

    with sqlite3.connect(paths.database) as db:
        result = db.execute("""
            SELECT name FROM tracker_food_products
        """).fetchone()

    assert result == ("private-food",)


def test_admin_cannot_be_reprovisioned(tmp_path):
    with pytest.raises(PermissionError):
        initialize_staged_workspace426(
            1, tmp_path
        )

    assert not (tmp_path / "tracker.db").exists()


def test_symlinked_user_root_is_rejected(tmp_path):
    outside = tmp_path.parent / (
        tmp_path.name + "-outside"
    )
    outside.mkdir()

    (tmp_path / "users").symlink_to(
        outside,
        target_is_directory=True,
    )

    with pytest.raises(ValueError):
        initialize_staged_workspace426(
            2, tmp_path
        )

    assert not (outside / "2").exists()


def test_existing_uninitialized_workspace_not_overwritten(tmp_path):
    original = prepare_inactive_storage(
        2, tmp_path
    )

    assert _tables(original.database) == set()

    with pytest.raises(FileExistsError):
        initialize_staged_workspace426(
            2, tmp_path
        )

    assert _tables(original.database) == set()


def test_workspaces_do_not_enable_login_or_live_routing(tmp_path):
    initialize_staged_workspace426(
        2, tmp_path
    )

    with pytest.raises(PermissionError):
        live_storage_for(2)

    assert planned_storage(
        2, tmp_path
    ).mode == "reserved-inactive"

    report = verify_staged_workspace426(
        2, tmp_path
    )

    assert report["status"] == "inactive"
    assert report["live_access_enabled"] is False
