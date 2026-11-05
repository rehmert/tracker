"""Release 391: mandatory storage authorization for food routes.

The existing food modules still use the process-wide SQLAlchemy
engine. Until they are migrated to per-user engines, allow
access only to the authenticated legacy administrator.

This is a route-level authorization gate. It must execute
before a food endpoint performs any database operation.

Legacy Basic Auth mode remains supported for compatibility.
Additional users remain disabled.
"""

from fastapi import Request

from . import session_auth385
from .user_db389 import resolve_authenticated_storage
from .workspace_engine401 import resolve_live_engine401
from .db import engine as administrator_engine


def require_food_storage391(request: Request):
    """Verify the current user's permitted storage boundary.

    In DEV session mode, use the existing strict database
    resolver. That resolver verifies the server-side session,
    request identity, and configured SQLite engine.

    With DEV session mode disabled, retain the application's
    existing authentication behavior. In that configuration,
    the application's global auth dependency remains
    responsible for Basic Auth.
    """
    if not session_auth385.enabled():
        return None

    storage = resolve_authenticated_storage(request)

    if storage.user_id != 1 or storage.mode != "legacy-admin":
        raise PermissionError(
            "Food storage is unavailable to this user"
        )

    # The route-level guard runs before food journal endpoints.
    # Verify the configured SQLAlchemy engine independently.
    authorized_engine = resolve_live_engine401(request)

    if authorized_engine is not administrator_engine:
        from fastapi import HTTPException
        raise HTTPException(
            503, "Food workspace engine mismatch"
        )

    # Most existing food operations still access food.engine.
    # Protect that direct engine reference until migration.
    from .routers import food

    if food.engine is not administrator_engine:
        from fastapi import HTTPException
        raise HTTPException(
            503, "Food journal engine substitution denied"
        )

    return None
