
"""Tracker maintenance and verification dashboard."""

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Request
from sqlalchemy.engine import make_url

from .. import config
from app.templating import render

router = APIRouter()


def _database_path():
    url = make_url(config.DB_URL)

    if url.get_backend_name() != "sqlite":
        raise RuntimeError("SQLite database expected")

    path = Path(url.database)

    if not path.is_absolute():
        path = (
            Path(__file__).resolve().parents[2] / path
        ).resolve()

    return path


@router.get("/maintenance-review")
def maintenance_review(request: Request):
    database = _database_path()

    checks = []

    try:
        with sqlite3.connect(
            database.as_uri() + "?mode=ro",
            uri=True,
        ) as db:
            db.execute("PRAGMA query_only=ON")

            integrity = db.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]

            checks.append({
                "name": "SQLite integrity",
                "ok": integrity == "ok",
                "detail": integrity,
            })

            violations = db.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

            checks.append({
                "name": "Foreign-key consistency",
                "ok": not violations,
                "detail": (
                    "No violations"
                    if not violations
                    else f"{len(violations)} violations"
                ),
            })

            table_count = db.execute(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE type='table'"
            ).fetchone()[0]

            checks.append({
                "name": "Database tables",
                "ok": table_count > 0,
                "detail": f"{table_count} tables",
            })

    except (OSError, sqlite3.Error) as exc:
        checks.append({
            "name": "Database inspection",
            "ok": False,
            "detail": str(exc),
        })

    backup_directory = Path("/tmp/tracker-backups")

    checks.append({
        "name": "Source backup directory",
        "ok": backup_directory.is_dir(),
        "detail": (
            "Available"
            if backup_directory.is_dir()
            else "Not found"
        ),
    })

    return render(
        request,
        "maintenance_review.html",
        checks=checks,
    )
