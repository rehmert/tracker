"""Release 485: OFFLINE full-app private-process acceptance.

This is a deliberately unmounted proof of a process-per-user architecture.
It never starts a listener, creates accounts, or activates staged users.
A parent must first select and verify an inactive private workspace with
worker_environment428; this child revalidates that identity before any
application/database import. It runs the actual primary FastAPI app in the
child process, so imported global engines point ONLY to the private DB.
"""

import json
import os
import sqlite3
from pathlib import Path
from urllib.parse import quote


def _database_count(path):
    uri = "file:" + quote(str(path), safe="/") + "?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=10) as conn:
        if conn.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise RuntimeError("Private database integrity check failed")
        return conn.execute("SELECT COUNT(*) FROM compounds").fetchone()[0]


def run_fullapp_rehearsal485():
    # Validate before importing app.db/config. Those modules bind the database
    # path at import time and may initialize directories.
    from .worker_probe428 import validate_environment

    uid, private = validate_environment()
    private = Path(private).absolute()
    db_path = private / "tracker.db"

    from . import config, session_auth385
    from .db import engine
    from .routers import food, food_quick375
    from .main import app
    from fastapi.routing import APIRoute
    from fastapi.testclient import TestClient

    if session_auth385.enabled():
        raise RuntimeError("Interactive session authentication in worker")

    if (
        Path(config.DATA_DIR).absolute() != private
        or Path(config.DB_PATH).absolute() != db_path
        or Path(engine.url.database or "").absolute() != db_path
        or engine.url.get_backend_name() != "sqlite"
        or food.engine is not engine
        or food_quick375.engine is not engine
        or Path(config.UPLOAD_DIR).absolute() != private / "uploads" / "coa"
        or Path(config.LAB_DIR).absolute() != private / "uploads" / "labs"
        or Path(os.environ.get("TRACKER_BACKUP_DIR", "")).absolute()
            != private / "backups"
    ):
        raise RuntimeError("Full-app private engine or storage mismatch")

    expected = (
        "/healthz", "/", "/compounds", "/vials", "/labs",
        "/protocols", "/doses", "/vitals", "/food",
    )
    routes = {
        route.path
        for route in app.routes
        if isinstance(route, APIRoute) and "GET" in route.methods
    }
    missing = sorted(set(expected) - routes)
    if missing:
        raise RuntimeError("Primary routes unavailable: " + ", ".join(missing))

    before = _database_count(db_path)
    auth = (
        os.environ["TRACKER_USER"], os.environ["TRACKER_PASS"]
    )
    statuses = {}

    # ASGI TestClient stays inside this child. No TCP or Unix listener.
    with TestClient(app, base_url="https://private-worker.invalid") as client:
        if client.get("/healthz").status_code != 401:
            raise RuntimeError("Worker unauthenticated request was accepted")

        for path in expected:
            response = client.get(path, auth=auth, follow_redirects=False)
            statuses[path] = response.status_code
            if response.status_code != 200:
                raise RuntimeError(
                    f"Private primary page {path} failed with HTTP "
                    f"{response.status_code}"
                )

    after = _database_count(db_path)
    if before != after:
        raise RuntimeError("Private primary pages changed compound count")

    return {
        "mode": "offline-fullapp-private-worker485",
        "user_id": uid,
        "private_compound_count": after,
        "full_app_routes_verified": len(statuses),
        "basic_auth_required": True,
        "primary_engine_is_private": True,
        "food_engines_are_private": True,
        "http_listener_started": False,
        "account_activated": False,
    }


def main():
    print(json.dumps(run_fullapp_rehearsal485(), sort_keys=True))


if __name__ == "__main__":
    main()
