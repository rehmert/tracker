
"""Tracker maintenance and verification dashboard."""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from sqlalchemy.engine import make_url

from .. import config, backup
from ..recovery_status import restore_status
from ..replica_health import replica_health
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

    # Application archives are created by app.backup, not by the installer.
    # A temporary source-code backup cannot substitute for a SQLite +
    # uploads archive. This is availability/freshness, not verification.
    backup_directory = backup.BACKUP_DIR
    checks.append({
        "name": "Configured backup directory",
        "ok": backup_directory.is_dir(),
        "detail": (
            "Found: " + str(backup_directory)
            if backup_directory.is_dir()
            else "Missing: " + str(backup_directory)
        ),
    })

    try:
        archives = backup.list_backups()
        latest = archives[0] if archives else None
        checks.append({
            "name": "Tracker backup archives",
            "ok": bool(archives),
            "detail": (
                f"{len(archives)} archive(s) available"
                if archives else "No backup archives found"
            ),
        })
        if latest:
            age = max(
                0.0,
                (datetime.now(timezone.utc) -
                 latest["modified"]).total_seconds() / 3600,
            )
            checks.append({
                "name": "Latest backup age",
                "ok": age <= 24,
                "detail": (
                    f'{latest["name"]} · {age:.1f} hours old · '
                    f'{latest["size"] / 1048576:.1f} MB'
                ),
            })
    except (OSError, ValueError) as exc:
        checks.append({
            "name": "Backup archive inventory",
            "ok": False,
            "detail": "Unable to inspect backup archives: " + str(exc),
        })

    recovery = restore_status()
    checks.append({
        "name": "Isolated backup restoration",
        "ok": recovery["ok"],
        "detail": recovery["detail"],
    })

    secondary = replica_health()
    if secondary["configured"]:
        checks.append({
            "name": "Secondary local backup copy",
            "ok": secondary["ok"],
            "detail": secondary["detail"],
        })

    return render(
        request,
        "maintenance_review.html",
        checks=checks,
        passed=sum(1 for check in checks if check["ok"]),
        attention=sum(1 for check in checks if not check["ok"]),
    )
