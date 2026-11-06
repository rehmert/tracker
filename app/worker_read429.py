"""Offline, read-only secondary worker: one allowlisted request on stdin.

No HTTP, sessions, account activation, caller-selected paths, or SQL execution.
"""

import json
import sqlite3
import sys

from pathlib import Path
from urllib.parse import quote

from .worker_probe428 import (
    validate_environment,
    verify_feature_routes428,
)

MAX_REQUEST_BYTES = 2048

COUNT_TABLES = {
    "compounds": "compounds",
    "vials": "vials",
    "doses": "dose_logs",
    "vitals": "vital_readings",
    "lab_reports": "lab_reports",
    "food_entries": "tracker_food_entries",
    "water_entries": "tracker_water_entries",
}


def parse_request429(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_REQUEST_BYTES:
        raise ValueError("Invalid worker request length")

    def unique_keys(pairs):
        fields = {}

        for key, value in pairs:
            if key in fields:
                raise ValueError("Duplicate worker request field")
            fields[key] = value

        return fields

    try:
        payload = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=unique_keys,
        )
    except (UnicodeError, ValueError) as error:
        raise ValueError("Invalid worker request JSON") from error

    if type(payload) is not dict or set(payload) != {"action"}:
        raise ValueError("Unexpected worker request fields")

    if payload["action"] != "overview":
        raise ValueError("Unsupported worker operation")

    return "overview"


def private_overview429(uid, private):
    from . import backup, config, db, session_auth385

    database = private / "tracker.db"

    if (
        config.DATA_DIR != private
        or config.DB_PATH != database
        or db.engine.url.get_backend_name() != "sqlite"
        or db.engine.url.database is None
        or Path(db.engine.url.database).absolute() != database
        or backup.BACKUP_DIR != private / "backups"
        or session_auth385.enabled()
    ):
        raise RuntimeError("Secondary worker database boundary mismatch")

    if verify_feature_routes428() != 3:
        raise RuntimeError("Required feature routes unavailable")

    uri = "file:" + quote(str(database), safe="/") + "?mode=ro"

    with sqlite3.connect(uri, uri=True, timeout=5) as connection:
        connection.execute("PRAGMA query_only=ON")

        marker = connection.execute("""
            SELECT user_id,status,schema_version
            FROM tracker_staged_workspace426
        """).fetchall()

        if marker != [(uid, "inactive", 426)]:
            raise RuntimeError("Workspace identity mismatch")

        tables = {
            row[0]
            for row in connection.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table'
            """)
        }

        if not set(COUNT_TABLES.values()) <= tables:
            raise RuntimeError("Required workspace tables missing")

        # Identifiers come exclusively from the source-code allowlist.
        counts = {
            label: connection.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]
            for label, table in COUNT_TABLES.items()
        }

    return {
        "mode": "offline-readonly-worker",
        "user_id": uid,
        "workspace_status": "inactive",
        "counts": counts,
        "http_listener_started": False,
        "login_enabled": False,
    }


def main():
    uid, private = validate_environment()

    action = parse_request429(
        sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    )

    assert action == "overview"

    print(json.dumps(
        private_overview429(uid, private),
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
