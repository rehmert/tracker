import secrets

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from . import config, session_auth385

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
            request.state.tracker_user_id = 1
            return None

        # Temporary compatibility for the local release
        # smoke tester, not a general Basic Auth bypass.
        host = request.client.host if request.client else ""

        smoke = (
            host in ("127.0.0.1", "::1")
            and request.headers.get("user-agent", "")
                == "Tracker-Release-Smoke/1.0"
        )

        if smoke:
            if not config.AUTH_USER or not config.AUTH_PASS:
                raise HTTPException(
                    503, "Authentication configuration incomplete"
                )

            valid = (
                creds is not None
                and secrets.compare_digest(
                    creds.username.encode(),
                    config.AUTH_USER.encode(),
                )
                and secrets.compare_digest(
                    creds.password.encode(),
                    config.AUTH_PASS.encode(),
                )
            )

            if valid:
                request.state.tracker_user_id = 1
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
