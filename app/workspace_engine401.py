"""Release 401: workspace database engine/session foundation.

The existing administrator uses the original application
engine and existing get_db dependency.

Additional users have read-only engine plans but no live
engine access or authenticated sessions.

This module does not migrate databases, create tables,
initialize accounts, or enable secondary-user routing.
"""

from dataclasses import dataclass
from pathlib import Path

from fastapi import Depends, HTTPException, Request
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from . import config, session_auth385
from .db import engine, get_db
from .user_storage388 import (
    StoragePaths,
    planned_storage,
)
from .workspace_boundary399 import (
    authenticated_workspace399,
    _reject_links399,
)


@dataclass(frozen=True)
class WorkspaceEnginePlan401:
    user_id: int
    mode: str
    database: Path
    url: URL


def plan_workspace_engine401(
    user_id: int,
    data_root=None,
) -> WorkspaceEnginePlan401:
    """Compute a per-user database URL without opening a database.

    All authorization remains separate. A plan is never
    permission to access or initialize a database.
    """
    storage = planned_storage(user_id, data_root)

    return WorkspaceEnginePlan401(
        user_id=storage.user_id,
        mode=storage.mode,
        database=storage.database,
        url=URL.create(
            "sqlite",
            database=str(storage.database),
        ),
    )


def resolve_live_engine401(request: Request):
    """Resolve the only currently authorized live engine.

    Requires an actual verified administrator workspace.
    Do not accept a user ID, username, database URL, or
    engine from caller-supplied HTTP parameters.
    """
    storage = authenticated_workspace399(request)

    if (
        storage.user_id != 1
        or storage.mode != "legacy-admin"
    ):
        raise HTTPException(
            403, "Additional workspace engines disabled"
        )

    expected = Path(storage.database).absolute()
    configured = Path(config.DB_PATH).absolute()

    engine_database = engine.url.database

    if (
        engine.url.get_backend_name() != "sqlite"
        or engine_database is None
        or engine_database == ":memory:"
    ):
        raise HTTPException(
            503, "Unsupported application database engine"
        )

    live_path = Path(engine_database).absolute()

    if configured != expected or live_path != expected:
        raise HTTPException(
            503, "Workspace engine configuration mismatch"
        )

    _reject_links399(expected)

    if not expected.is_file():
        raise HTTPException(
            503, "Authorized workspace database unavailable"
        )

    return engine


def get_workspace_db401(
    request: Request,
    db: Session = Depends(get_db),
):
    """Future replacement dependency with test-override compatibility.

    Preserve the existing get_db subdependency so isolated
    tests can override it. When session authentication is
    enabled, verify the live engine before yielding a session.

    Other users cannot acquire sessions through this function.
    """
    if session_auth385.enabled():
        resolve_live_engine401(request)

    yield db
