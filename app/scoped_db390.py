"""Authenticated DB dependency with FastAPI override compatibility.

DEV: check server-side administrator session before exposing DB.
Legacy mode: preserve existing FastAPI get_db behavior.

No additional users or per-user engines are enabled.
"""

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from . import session_auth385
from .db import get_db
from .user_db389 import resolve_authenticated_storage


def get_scoped_db390(
    request: Request,
    db: Session = Depends(get_db),
):
    """Preserve FastAPI's overrideable get_db subdependency."""

    if session_auth385.enabled():
        resolve_authenticated_storage(request)

    yield db
