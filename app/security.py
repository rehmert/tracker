import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from . import config

_basic = HTTPBasic(auto_error=False)


def require_auth(creds: HTTPBasicCredentials | None = Depends(_basic)) -> None:
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
