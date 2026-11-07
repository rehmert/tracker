"""Release 426: offline, inactive, schema-ready secondary workspaces.

This module NEVER:
- creates login accounts or sessions;
- authorizes HTTP access to a secondary user;
- changes the administrator SQLite database;
- switches the application's global SQLAlchemy engine;
- enables background jobs for a secondary user.

Workspace creation is exclusive and refuses existing user directories.
An interrupted workspace remains inactive for explicit inspection.
"""

import sqlite3
import stat
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import URL

from . import models  # noqa: F401 - register application ORM metadata
from .db import Base
from .migrations import migrate, migrate_coa_links
from .user_storage388 import (
    planned_storage,
    prepare_inactive_storage,
    valid_user_id,
)
from .food_water425 import init_water_schema


REQUIRED_TABLES = frozenset({
    "compounds",
    "vials",
    "protocols",
    "dose_logs",
    "lab_reports",
    "lab_results",
    "tracker_food_products",
    "tracker_food_entries",
    "tracker_food_targets",
    "tracker_water_entries",
    "tracker_schema_migrations",
    "tracker_staged_workspace426",
})


def _secondary_id(user_id):
    uid = valid_user_id(user_id)
    if uid == 1:
        raise PermissionError(
            "Administrator storage cannot be staged"
        )
    return uid


def _reject_symlink_components(path):
    path = Path(path).absolute()
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError(
                "Symlinked workspace path is forbidden"
            )
    return path


def verify_staged_workspace426(user_id, data_root):
    """Read-only, fail-closed workspace verification."""
    uid = _secondary_id(user_id)
    root = _reject_symlink_components(data_root)
    paths = planned_storage(uid, root)

    for path in (
        paths.root,
        paths.database,
        paths.coa,
        paths.labs,
        paths.backups,
    ):
        _reject_symlink_components(path)

    if not paths.root.is_dir():
        raise RuntimeError("Staged workspace unavailable")

    if not paths.database.is_file():
        raise RuntimeError("Staged database unavailable")

    for directory in (
        paths.root,
        paths.coa,
        paths.labs,
        paths.backups,
    ):
        if not directory.is_dir():
            raise RuntimeError(
                "Incomplete staged workspace directories"
            )

    if stat.S_IMODE(paths.root.stat().st_mode) != 0o700:
        raise RuntimeError("Workspace permissions are unsafe")

    if stat.S_IMODE(paths.database.stat().st_mode) != 0o600:
        raise RuntimeError("Database permissions are unsafe")

    uri = "file:" + quote(
        str(paths.database.absolute()), safe="/"
    ) + "?mode=ro"

    with sqlite3.connect(uri, uri=True, timeout=5) as db:
        check = db.execute("PRAGMA quick_check").fetchall()

        if check != [("ok",)]:
            raise RuntimeError(
                "Staged SQLite integrity check failed"
            )

        tables = {
            row[0]
            for row in db.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table'
            """).fetchall()
        }

        missing = REQUIRED_TABLES - tables

        if missing:
            raise RuntimeError(
                "Staged schema incomplete: "
                + ", ".join(sorted(missing))
            )

        marker = db.execute("""
            SELECT user_id, status, schema_version
            FROM tracker_staged_workspace426
        """).fetchall()

        if marker != [(uid, "inactive", 426)]:
            raise RuntimeError(
                "Workspace identity or inactive marker mismatch"
            )

    return {
        "user_id": uid,
        "status": "inactive",
        "schema_version": 426,
        "database_available": True,
        "application_table_count": len(tables),
        "live_access_enabled": False,
    }


def initialize_staged_workspace426(user_id, data_root):
    """Create a fresh secondary workspace with the Tracker schema.

    Existing workspaces are never overwritten or implicitly
    upgraded. No secondary user is activated by this call.
    """
    uid = _secondary_id(user_id)
    root = _reject_symlink_components(data_root)

    if not root.is_dir():
        raise ValueError("Existing trusted data root required")

    paths = planned_storage(uid, root)

    _reject_symlink_components(paths.root)
    _reject_symlink_components(paths.database)

    # Exclusive creation. This refuses any existing user path.
    # It creates an empty database without allowing live access.
    paths = prepare_inactive_storage(uid, root)

    url = URL.create(
        "sqlite",
        database=str(paths.database),
    )

    tenant_engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(tenant_engine, "connect")
    def _sqlite_setup(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA journal_mode=WAL")
        finally:
            cursor.close()

    try:
        # Follow the actual Tracker application startup sequence,
        # but on the independently created secondary engine.
        migrate(tenant_engine)
        Base.metadata.create_all(tenant_engine)
        migrate_coa_links(tenant_engine)

        from .routers.food import init_food_schema

        init_food_schema(tenant_engine)
        init_water_schema(tenant_engine)

        with tenant_engine.begin() as db:
            db.exec_driver_sql("""
                CREATE TABLE IF NOT EXISTS
                tracker_schema_migrations (
                    name TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP
                )
            """)

            db.exec_driver_sql("""
                INSERT OR IGNORE INTO
                tracker_schema_migrations(name)
                VALUES ('tracker_phases_1_3_v2')
            """)

            # This is a permanently inactive staging marker.
            # It is NOT an account or an authentication record.
            db.exec_driver_sql("""
                CREATE TABLE tracker_staged_workspace426 (
                    user_id INTEGER PRIMARY KEY
                        CHECK(user_id > 1),
                    status TEXT NOT NULL
                        CHECK(status = 'inactive'),
                    schema_version INTEGER NOT NULL
                        CHECK(schema_version = 426)
                )
            """)

            db.execute(text("""
                INSERT INTO tracker_staged_workspace426
                    (user_id, status, schema_version)
                VALUES (:uid, 'inactive', 426)
            """), {"uid": uid})

    finally:
        tenant_engine.dispose()

    # Do not silently repair or activate an incomplete store.
    # A failure remains an inactive directory for investigation.
    verify_staged_workspace426(uid, root)

    return paths
