"""Authenticated database routing foundation.

Release 389 deliberately routes only the existing administrator
to the legacy SQLite engine.

Additional users are denied. Their databases are not opened,
created, migrated, attached, or made available to application
routes.

This module is an opt-in dependency, not a global engine switch.
"""

from pathlib import Path

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from . import config, session_auth385
from .db import SessionLocal, engine
from .user_storage388 import (
    live_storage_for,
    planned_storage,
)


def resolve_authenticated_storage(request: Request):
    """Resolve storage from a verified session, never caller input."""

    if not session_auth385.enabled():
        raise HTTPException(
            403, "User-scoped routing is not enabled"
        )

    token = request.cookies.get(session_auth385.COOKIE)

    # Validate the token against the server-side session table.
    user_id = session_auth385.session_user(token)

    if user_id != 1:
        raise HTTPException(
            403, "Authenticated administrator required"
        )

    # The application's global auth dependency must already
    # have established the same identity for this request.
    if getattr(
        request.state, "tracker_user_id", None
    ) != user_id:
        raise HTTPException(
            403, "Authentication context mismatch"
        )

    try:
        storage = live_storage_for(user_id)
    except (PermissionError, RuntimeError, ValueError):
        raise HTTPException(
            503, "Authorized data storage unavailable"
        ) from None

    # Ensure the engine's configured database remains exactly
    # the legacy administrator database.
    expected = storage.database.absolute()
    configured = Path(config.DB_PATH).absolute()
    engine_database = engine.url.database

    if engine_database is None:
        raise HTTPException(
            503, "Unsupported database engine"
        )

    engine_path = Path(engine_database).absolute()

    if configured != expected or engine_path != expected:
        raise HTTPException(
            503, "Database routing configuration mismatch"
        )

    return storage


def get_user_db(request: Request):
    """FastAPI dependency yielding only an authorized SQLAlchemy Session.

    A future release can replace its internal engine selection
    after all direct SQL and filesystem routes are audited.
    """
    resolve_authenticated_storage(request)

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def future_storage_plan(user_id):
    """Plan-only lookup. Does not grant access to other users."""
    if type(user_id) is not int or user_id <= 1:
        raise ValueError(
            "A future user's numeric ID is required"
        )

    plan = planned_storage(user_id)

    if plan.mode != "reserved-inactive":
        raise PermissionError("Unexpected storage mode")

    return plan


def username_independent_storage(user_id, username):
    """Demonstrate that username is metadata, not a path key."""
    if not isinstance(username, str):
        raise ValueError("Invalid username metadata")

    # Username is intentionally NOT passed to planned_storage.
    return planned_storage(user_id).database
