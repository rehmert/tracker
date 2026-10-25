import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from . import config

_basic = HTTPBasic(auto_error=False)


def require_auth(creds: HTTPBasicCredentials | None = Depends(_basic)) -> None:
    if not (config.AUTH_USER and config.AUTH_PASS):
        return  # auth disabled (fine on a trusted LAN; see README)
    ok = (
        creds is not None
        and secrets.compare_digest(creds.username.encode(), config.AUTH_USER.encode())
        and secrets.compare_digest(creds.password.encode(), config.AUTH_PASS.encode())
    )
    if not ok:
        raise HTTPException(401, "Authentication required",
                            headers={"WWW-Authenticate": 'Basic realm="tracker"'})
