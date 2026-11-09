"""Server-verified, request-local user ownership context.

Only administrator ID 1 is authorized in this release.
No other user databases, uploads, or backups are activated.
"""

from dataclasses import dataclass

from fastapi import HTTPException, Request

from . import session_auth385
from .user_storage388 import (
    StoragePaths,
    planned_storage,
)


@dataclass(frozen=True)
class VerifiedRequestScope:
    user_id: int
    storage: StoragePaths
    authentication_mode: str


def establish_request_scope(
    request: Request,
    verified_user_id: int,
):
    """Attach scope only after verifying the server-side session."""

    if type(verified_user_id) is not int:
        raise PermissionError("Invalid authenticated user")

    if verified_user_id != 1:
        raise PermissionError(
            "Additional users remain disabled"
        )

    if not session_auth385.enabled():
        raise PermissionError(
            "Session authentication is not active"
        )

    token = request.cookies.get(session_auth385.COOKIE)

    if session_auth385.session_user(token) != verified_user_id:
        raise PermissionError(
            "Server-side session does not match user"
        )

    storage = planned_storage(verified_user_id)

    if storage.mode != "legacy-admin":
        raise PermissionError(
            "Unexpected administrator storage mode"
        )

    scope = VerifiedRequestScope(
        user_id=verified_user_id,
        storage=storage,
        authentication_mode="app-session",
    )

    request.state.tracker_user_id = verified_user_id
    request.state.tracker_verified_scope393 = scope

    return scope


def verified_request_scope(request: Request):
    """Revalidate user, session, and storage ownership."""

    if not session_auth385.enabled():
        raise HTTPException(
            403, "Verified user scope unavailable"
        )

    scope = getattr(
        request.state,
        "tracker_verified_scope393",
        None,
    )

    if not isinstance(scope, VerifiedRequestScope):
        raise HTTPException(
            403, "Verified request scope required"
        )

    token = request.cookies.get(session_auth385.COOKIE)
    user_id = session_auth385.session_user(token)

    if (
        user_id != 1
        or scope.user_id != user_id
        or getattr(
            request.state,
            "tracker_user_id",
            None,
        ) != user_id
    ):
        raise HTTPException(
            403, "Authenticated user context mismatch"
        )

    if (
        scope.storage != planned_storage(user_id)
        or scope.authentication_mode != "app-session"
    ):
        raise HTTPException(
            403, "Authenticated storage context mismatch"
        )

    return scope
