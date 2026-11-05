"""Release 390: gradual conversion to authenticated DB access.

With DEV session authentication enabled, only a verified
administrator session can open the existing SQLite database.

With session authentication disabled, preserve the existing
legacy dependency for compatibility with PROD.

This does not enable other users or per-user engines.
"""

from fastapi import Request

from . import session_auth385
from .db import get_db
from .user_db389 import get_user_db


def get_scoped_db390(request: Request):
    """Yield a session from the appropriate guarded dependency."""

    dependency = (
        get_user_db
        if session_auth385.enabled()
        else get_db
    )

    yield from dependency(request) if dependency is get_user_db else dependency()
