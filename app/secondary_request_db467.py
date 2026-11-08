"""Release 467: authenticated private read-only DB context.

The session cookie is verified by the existing DEV secondary
gateway on every request. The caller may not supply a user ID,
database path, SQLite URI, or SQL statement.

This does not change the administrator-scoped global engine.
"""
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
import sqlite3

from fastapi import HTTPException, Request

from . import config


@dataclass(frozen=True)
class PrivateScope467:
    user_id: int
    database: Path
    mode: str


def verified_private_scope467(request: Request):
    from .secondary_preview430 import (
        COOKIE, _session_user, require_preview,
    )
    from .worker_scope428 import worker_plan428

    require_preview()

    uid = _session_user(
        request.cookies.get(COOKIE)
    )

    if type(uid) is not int or uid <= 1:
        raise HTTPException(
            401, "Secondary session required"
        )

    # worker_plan428 verifies inactive credentials,
    # private workspace identity and storage ownership.
    try:
        paths = worker_plan428(uid)

        expected = (
            config.DATA_DIR / "users" / str(uid)
        ).absolute()

        if (
            paths.user_id != uid
            or paths.mode != "reserved-inactive"
            or paths.root != expected
            or paths.database != expected / "tracker.db"
            or paths.database.is_symlink()
            or not paths.database.is_file()
        ):
            raise RuntimeError(
                "Private storage mismatch"
            )
    except (
        ValueError, PermissionError,
        RuntimeError, OSError,
    ):
        raise HTTPException(
            503, "Private storage unavailable"
        ) from None

    return PrivateScope467(
        user_id=uid,
        database=paths.database,
        mode="secondary-read-only",
    )


@contextmanager
def readonly_private_db467(request: Request):
    scope = verified_private_scope467(request)

    # URI uses the server-selected verified database path.
    # None of its components come from request parameters.
    uri = (
        "file:"
        + quote(str(scope.database), safe="/")
        + "?mode=ro"
    )

    try:
        with closing(sqlite3.connect(
            uri, uri=True, timeout=5
        )) as db:
            db.execute("PRAGMA query_only=ON")

            marker = db.execute("""
                SELECT user_id,status,schema_version
                FROM tracker_staged_workspace426
            """).fetchall()

            if marker != [
                (scope.user_id, "inactive", 426)
            ]:
                raise RuntimeError(
                    "Private workspace identity mismatch"
                )

            # Never expose a write-capable session.
            yield scope, db

    except (
        sqlite3.Error, RuntimeError, OSError,
    ):
        raise HTTPException(
            503, "Private read-only database unavailable"
        ) from None


def scoped_counts467(request: Request):
    """Allowlisted counts, not arbitrary SQL or records."""
    with readonly_private_db467(request) as (scope, db):
        compounds = db.execute(
            "SELECT COUNT(*) FROM compounds"
        ).fetchone()[0]

        food_entries = db.execute(
            "SELECT COUNT(*) FROM tracker_food_entries"
        ).fetchone()[0]

        water_entries = db.execute(
            "SELECT COUNT(*) FROM tracker_water_entries"
        ).fetchone()[0]

    values = (
        compounds, food_entries, water_entries
    )

    if any(
        type(value) is not int or value < 0
        for value in values
    ):
        raise HTTPException(
            503, "Private data count invalid"
        )

    return {
        "mode": "verified-private-readonly467",
        "user_id": scope.user_id,
        "storage_mode": scope.mode,
        "counts": {
            "compounds": compounds,
            "food_entries": food_entries,
            "water_entries": water_entries,
        },
        "write_access": False,
        "normal_login_enabled": False,
    }
