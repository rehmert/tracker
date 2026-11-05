import secrets

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from . import config, session_auth385
from .request_scope393 import establish_request_scope

_basic = HTTPBasic(auto_error=False)


def require_auth(
    creds: HTTPBasicCredentials | None = Depends(_basic),
    request: Request = None,
) -> None:
    if request is not None and session_auth385.enabled():
        if request.url.path == "/login":
            return None

        token = request.cookies.get(session_auth385.COOKIE)

        if session_auth385.session_user(token) == 1:
            establish_request_scope(request, 1)
            return None

        if request.method == "GET":
            from urllib.parse import quote

            destination = request.url.path
            if request.url.query:
                destination += "?" + request.url.query

            destination = session_auth385.safe_next(
                destination
            )

            raise HTTPException(
                303,
                "Sign in required",
                headers={
                    "Location": "/login?next="
                    + quote(destination, safe="")
                },
            )

        raise HTTPException(
            401, "Session authentication required"
        )

    # Both absent is the documented opt-out for trusted
    # networks. A partially configured account must never
    # silently disable authentication.
    if not config.AUTH_USER and not config.AUTH_PASS:
        return
    if not config.AUTH_USER or not config.AUTH_PASS:
        raise HTTPException(
            503,
            "Authentication configuration incomplete",
        )
    ok = (
        creds is not None
        and secrets.compare_digest(creds.username.encode(), config.AUTH_USER.encode())
        and secrets.compare_digest(creds.password.encode(), config.AUTH_PASS.encode())
    )
    if not ok:
        raise HTTPException(401, "Authentication required",
                            headers={"WWW-Authenticate": 'Basic realm="tracker"'})
