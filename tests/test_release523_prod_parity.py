"""Release 523: real PROD parity, no DEV credential/data copying.

Session login and the existing private secondary gateway are activated only
with a PROD-specific marker and explicit process opt-in. All credentials
and workspace SQLite live inside disposable pytest directories.
"""

import re

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import config, session_auth385 as auth
from app.instance_parity523 import interactive_parity523
from app.main import tracker_response_protection
from app.security import require_auth
from app.routers import session_login385, account_security386
from app.secondary_preview430 import (
    COOKIE as SECONDARY_COOKIE,
    preview_app, preview_enabled,
)
from app.unified_login473 import enabled473
from app.user_accounts427 import stage_secondary_account427
from app.user_bootstrap426 import initialize_staged_workspace426


def _csrf(html):
    result = re.search(
        r'name="csrf_token"\s+value="([^"]+)"', html
    )
    assert result is not None
    return result.group(1)


@pytest.fixture
def prod_environment523(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "AUTH_USER", "operator")
    monkeypatch.setattr(config, "AUTH_PASS", "legacy-prod-password")
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    monkeypatch.setenv("TRACKER_INSTANCE", "PROD")
    monkeypatch.delenv("TRACKER_PROD_PARITY523", raising=False)
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")
    monkeypatch.setenv("TRACKER_MULTIUSER_LOGIN473", "1")
    monkeypatch.delenv("TRACKER_SECONDARY_LOCKDOWN440", raising=False)

    auth.bootstrap("operator", "new-prod-login-password")
    (tmp_path / auth.PROD_FLAG523).write_text("enabled")

    host = FastAPI(dependencies=[Depends(require_auth)])
    host.middleware("http")(tracker_response_protection)
    host.include_router(session_login385.router)
    host.include_router(account_security386.router)
    host.mount("/secondary", preview_app)

    @host.get("/admin-only")
    def admin_only():
        return {"administrator": True}

    with TestClient(host, base_url="https://tracker.test") as client:
        yield client, tmp_path, monkeypatch


def _login(client, username, password):
    page = client.get("/login")
    assert page.status_code == 200
    result = client.post(
        "/login",
        data={
            "username": username,
            "password": password,
            "csrf_token": _csrf(page.text),
            "next": "/admin-only",
        },
        follow_redirects=False,
    )
    return result


def test_523_prod_remains_basic_until_explicit_opt_in(prod_environment523):
    client, root, monkeypatch = prod_environment523

    assert not interactive_parity523()
    assert not auth.enabled()
    assert not preview_enabled()
    assert not enabled473()

    response = client.get("/admin-only", follow_redirects=False)
    assert response.status_code == 401
    assert response.headers.get("www-authenticate", "").startswith("Basic")

    assert client.get("/login").status_code == 401
    assert client.get(
        "/admin-only", auth=("operator", "legacy-prod-password")
    ).status_code == 200


def test_523_prod_login_logout_and_account_security(prod_environment523):
    client, root, monkeypatch = prod_environment523
    monkeypatch.setenv("TRACKER_PROD_PARITY523", "1")

    assert interactive_parity523()
    assert auth.enabled()
    assert preview_enabled()
    assert enabled473()

    denied = client.get("/admin-only", follow_redirects=False)
    assert denied.status_code == 303
    assert denied.headers["location"].startswith("/login")

    # Old Basic credentials no longer bypass session authentication.
    old_basic = client.get(
        "/admin-only", auth=("operator", "legacy-prod-password"),
        follow_redirects=False,
    )
    assert old_basic.status_code == 303

    login = _login(client, "operator", "new-prod-login-password")
    assert login.status_code == 303
    assert login.headers["location"] == "/admin-only"
    assert client.cookies.get(auth.COOKIE)
    assert client.get("/admin-only").json() == {"administrator": True}

    security = client.get("/account/security")
    assert security.status_code == 200
    token = _csrf(security.text)
    bad = client.post(
        "/account/sessions/revoke-others",
        data={"csrf_token": "forged"},
        follow_redirects=False,
    )
    assert bad.status_code == 403
    allowed = client.post(
        "/account/sessions/revoke-others",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert allowed.status_code == 303

    # Root logout has its own signed cookie; do not allow GET logout.
    from app.csrf_runtime import COOKIE_NAME
    logout_token = client.cookies.get(COOKIE_NAME)
    assert logout_token
    logout = client.post(
        "/logout",
        data={"csrf_token": logout_token},
        follow_redirects=False,
    )
    assert logout.status_code == 303
    assert client.cookies.get(auth.COOKIE) is None


def test_523_prod_secondary_login_and_private_user_isolation(prod_environment523):
    client, root, monkeypatch = prod_environment523
    monkeypatch.setenv("TRACKER_PROD_PARITY523", "1")

    initialize_staged_workspace426(2, root)
    stage_secondary_account427(
        2, "member2", "private-prod-password",
    )
    admin = _login(client, "operator", "new-prod-login-password")
    assert admin.status_code == 303
    assert client.get("/admin-only").status_code == 200

    member = _login(client, "member2", "private-prod-password")
    assert member.status_code == 303
    assert member.headers["location"] == "/secondary/overview"
    assert client.cookies.get(SECONDARY_COOKIE)
    assert client.cookies.get(auth.COOKIE) is None
    assert client.get("/secondary/overview").status_code == 200

    # A private secondary session cannot access administrator data.
    blocked = client.get("/admin-only", follow_redirects=False)
    assert blocked.status_code == 303
    assert blocked.headers["location"].startswith("/login")
    assert not auth.session_user(client.cookies.get(SECONDARY_COOKIE))

    # Explicit lockdown disables private accounts, not the admin login.
    monkeypatch.setenv("TRACKER_SECONDARY_LOCKDOWN440", "1")
    assert not preview_enabled()
    assert not enabled473()
    assert client.get("/secondary/overview").status_code == 404


def test_523_prod_marker_not_interchangeable_with_dev_marker(
    prod_environment523,
):
    client, root, monkeypatch = prod_environment523
    monkeypatch.setenv("TRACKER_PROD_PARITY523", "1")
    (root / auth.PROD_FLAG523).unlink()
    (root / auth.FLAG).write_text("DEV marker must not activate PROD")
    assert not auth.enabled()
    assert client.get("/login").status_code == 401


def test_523_prod_secondary_worker_plan_isolated(prod_environment523):
    client, root, monkeypatch = prod_environment523
    monkeypatch.setenv("TRACKER_PROD_PARITY523", "1")
    initialize_staged_workspace426(2, root)
    stage_secondary_account427(2, "member2", "private-prod-password")

    from app.worker_scope428 import worker_plan428
    private = worker_plan428(2, root)
    assert private.root == root / "users" / "2"
    assert private.database != root / "tracker.db"
