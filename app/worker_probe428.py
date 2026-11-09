"""Offline application import with private database and no ASGI listener.

Some test environments expose placeholders through app.routes.
Verify actual APIRoute declarations on each feature router,
matching tests/test_core_user_db394.py.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote


def fail(message):
    raise RuntimeError(message)


def validate_environment():
    raw_uid = os.getenv("TRACKER_WORKER_USER_ID", "")
    parent_raw = os.getenv(
        "TRACKER_WORKER_PARENT_DATA_DIR", ""
    )
    private_raw = os.getenv("TRACKER_DATA_DIR", "")

    if (
        os.getenv("TRACKER_WORKER_PROBE_ONLY") != "1"
        or os.getenv("TRACKER_INSTANCE") not in ("DEV", "PROD")
        or not raw_uid.isdecimal()
        or not parent_raw
        or not private_raw
        or not Path(parent_raw).is_absolute()
        or not Path(private_raw).is_absolute()
    ):
        fail("Invalid offline worker identity or configuration")

    uid = int(raw_uid)

    if not 2 <= uid <= 2147483647:
        fail("Administrator worker identity forbidden")

    parent = Path(parent_raw).absolute()
    private = Path(private_raw).absolute()

    if private != parent / "users" / str(uid):
        fail("Worker data directory does not match identity")

    paths = (
        parent,
        private,
        private / "tracker.db",
        private / "uploads",
        private / "uploads" / "coa",
        private / "uploads" / "labs",
        private / "backups",
    )

    for path in paths:
        for component in (path, *path.parents):
            if component.is_symlink():
                fail("Symlinked worker storage forbidden")

    if not private.is_dir() or not (
        private / "tracker.db"
    ).is_file():
        fail("Missing private workspace database")

    if (
        private / ".tracker-session-auth-dev"
    ).exists():
        fail("Session mode may not be active inside worker")

    if (
        os.getenv("TRACKER_USER") != "isolated-worker"
        or len(os.getenv("TRACKER_PASS", "")) < 40
    ):
        fail("Dedicated worker authentication required")

    if (
        os.getenv("TRACKER_CSRF_ENFORCE") != "1"
        or os.getenv("TRACKER_ORIGIN_GUARD") != "1"
    ):
        fail("Worker browser-write protections disabled")

    if (
        Path(
            os.getenv("TRACKER_BACKUP_DIR", "")
        ).absolute()
        != private / "backups"
    ):
        fail("Worker backup destination mismatch")

    return uid, private


def verify_feature_routes428():
    """Verify real feature endpoints and their required guards."""

    from fastapi.routing import APIRoute

    from .routers import doses, labs, food
    from .scoped_db390 import get_scoped_db390
    from .food_storage_guard391 import (
        require_food_storage391,
    )

    expected = (
        (doses, "/doses", get_scoped_db390),
        (labs, "/labs", get_scoped_db390),
        (food, "/food", require_food_storage391),
    )

    for module, path, required_guard in expected:
        matches = [
            route
            for route in module.router.routes
            if (
                isinstance(route, APIRoute)
                and route.path == path
                and "GET" in route.methods
            )
        ]

        if len(matches) != 1:
            fail(
                "Required GET route missing from feature router: "
                + path
            )

        dependencies = {
            item.call
            for item in matches[0].dependant.dependencies
        }

        if required_guard not in dependencies:
            fail(
                "Required authorization or database "
                "dependency missing: "
                + path
            )

    # Verify the application's registration declarations.
    # app.routes is not the authoritative collection in
    # Tracker's existing routing-test conventions.
    main_source = (
        Path(__file__).with_name("main.py")
        .read_text()
    )

    if (
        "app.include_router(food.router)"
        not in main_source
    ):
        fail("Food router not included in main app")

    import re

    registration = re.search(
        r"for module in\s*\((.*?)\)\s*:"
        r"\s*app\.include_router\(module\.router\)",
        main_source,
        re.S,
    )

    if (
        registration is None
        or not {"doses", "labs"} <= set(
            re.findall(
                r"\b[a-zA-Z_][a-zA-Z_0-9]*\b",
                registration.group(1),
            )
        )
    ):
        fail("Core feature routers not included in main app")

    return 3


def main():
    uid, private = validate_environment()

    # Import the app after validating private worker paths.
    from sqlalchemy.engine import Engine

    from . import config, db, backup, session_auth385
    from .main import app
    from .routers import food, food_quick375
    from .security import require_auth

    if session_auth385.enabled():
        fail(
            "Administrator session authentication "
            "leaked into worker"
        )

    if (
        config.DATA_DIR != private
        or config.DB_PATH != private / "tracker.db"
        or config.UPLOAD_DIR != private / "uploads" / "coa"
        or config.LAB_DIR != private / "uploads" / "labs"
        or backup.BACKUP_DIR != private / "backups"
    ):
        fail(
            "Worker configuration points to another "
            "storage root"
        )

    if not any(
        dependency.dependency is require_auth
        for dependency in app.router.dependencies
    ):
        fail("Application-wide authorization missing")

    for name, engine in (
        ("db", db.engine),
        ("food", food.engine),
        ("quick", food_quick375.engine),
    ):
        if (
            engine.url.get_backend_name() != "sqlite"
            or Path(
                engine.url.database or ""
            ).absolute() != private / "tracker.db"
        ):
            fail("Unexpected SQLite engine: " + name)

    if (
        db.SessionLocal.kw.get("bind")
        is not db.engine
    ):
        fail(
            "SQLAlchemy session factory bound "
            "to wrong engine"
        )

    seen = 0

    for module_name, module in list(
        sys.modules.items()
    ):
        if (
            not module_name.startswith("app.")
            or module is None
        ):
            continue

        for variable_name, value in vars(module).items():
            if not isinstance(value, Engine):
                continue

            seen += 1

            if (
                value.url.get_backend_name() != "sqlite"
                or Path(
                    value.url.database or ""
                ).absolute() != private / "tracker.db"
            ):
                fail(
                    "Unexpected database engine: "
                    + module_name
                    + "."
                    + variable_name
                )

    if seen < 3:
        fail(
            "Expected database engine audit "
            "candidates missing"
        )

    feature_count = verify_feature_routes428()

    # The two direct health endpoints can still be
    # checked through the application's outer route list.
    app_paths = {
        route.path
        for route in app.routes
        if hasattr(route, "path")
    }

    if not {"/ping", "/healthz"} <= app_paths:
        fail("App health endpoints are missing")

    uri = (
        "file:"
        + quote(
            str(private / "tracker.db"),
            safe="/",
        )
        + "?mode=ro"
    )

    with sqlite3.connect(
        uri,
        uri=True,
        timeout=5,
    ) as connection:
        marker = connection.execute("""
            SELECT user_id,status,schema_version
            FROM tracker_staged_workspace426
        """).fetchall()

        if marker != [(uid, "inactive", 426)]:
            fail("Inactive workspace identity mismatch")

        if (
            connection.execute(
                "PRAGMA quick_check"
            ).fetchone()[0]
            != "ok"
        ):
            fail("Private database integrity failure")

        compounds = connection.execute("""
            SELECT COUNT(*) FROM compounds
        """).fetchone()[0]

    print(json.dumps({
        "mode": "offline-isolated-probe",
        "user_id": uid,
        "storage_isolated": True,
        "feature_routes_verified": feature_count,
        "app_health_paths_present": True,
        "database_engines_inspected": seen,
        "private_compound_records": compounds,
        "http_listener_started": False,
        "account_login_enabled": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
