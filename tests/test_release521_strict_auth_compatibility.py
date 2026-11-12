"""Release 521: strict CSRF preserves administrator and secondary signed forms.

A standalone FastAPI host uses the same actual Tracker middleware, mounted
secondary app, and authentication routes against temporary credentials and
temporary SQLite. No installed LXC service or real users are touched.
"""
import re

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import config, session_auth385 as auth
from app.csrf_enforcement520 import enforce_multipart_csrf520
from app.csrf_runtime import COOKIE_NAME
from app.main import tracker_response_protection
from app.routers import account_security386, session_login385
from app.security import require_auth
from app.secondary_preview430 import COOKIE as SECONDARY_COOKIE, preview_app
from app.user_accounts427 import stage_secondary_account427
from app.user_bootstrap426 import initialize_staged_workspace426


def _form_token(html):
    match = re.search(
        r'name="csrf_token"\s+value="([^"]+)"', html
    )
    assert match is not None, "An authenticated form must have a signed token"
    return match.group(1)


@pytest.fixture
def strict_host521(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACKER_CSRF_ENFORCE", "1")
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")
    monkeypatch.delenv("TRACKER_SECONDARY_LOCKDOWN440", raising=False)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")

    auth.bootstrap("operator", "administrator-secure-password-521")
    (tmp_path / auth.FLAG).write_text("enabled")
    initialize_staged_workspace426(2, tmp_path)
    stage_secondary_account427(
        2, "member-2", "secondary-secure-password-521",
    )

    # Recreate the actual production middleware on a narrow disposable host.
    # The mounted preview app is intentionally not subject to root dependencies.
    host = FastAPI(
        dependencies=[
            Depends(require_auth),
            Depends(enforce_multipart_csrf520),
        ]
    )
    host.middleware("http")(tracker_response_protection)
    host.include_router(session_login385.router)
    host.include_router(account_security386.router)
    host.mount("/secondary", preview_app)

    with TestClient(host, base_url="https://tracker.test") as client:
        yield client


def test_521_strict_admin_login_account_and_logout_still_work(strict_host521):
    client = strict_host521
    page = client.get("/login")
    assert page.status_code == 200
    login_token = _form_token(page.text)
    login = client.post(
        "/login",
        data={
            "username": "operator",
            "password": "administrator-secure-password-521",
            "csrf_token": login_token,
            "next": "/account/security",
        },
        follow_redirects=False,
    )
    assert login.status_code == 303
    assert auth.session_user(client.cookies.get(auth.COOKIE)) == 1

    security = client.get("/account/security")
    assert security.status_code == 200
    token = _form_token(security.text)
    rejected = client.post(
        "/account/sessions/revoke-others",
        data={"csrf_token": "forged"},
        follow_redirects=False,
    )
    assert rejected.status_code == 403
    assert auth.session_user(client.cookies.get(auth.COOKIE)) == 1

    allowed = client.post(
        "/account/sessions/revoke-others",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert allowed.status_code == 303
    assert auth.session_user(client.cookies.get(auth.COOKIE)) == 1

    # Logout uses the root signed browser cookie, not the login-specific or
    # account-security-specific signed cookies.
    logout_cookie = client.cookies.get(COOKIE_NAME)
    assert logout_cookie
    logout = client.post(
        "/logout",
        data={"csrf_token": logout_cookie},
        follow_redirects=False,
    )
    assert logout.status_code == 303
    assert client.cookies.get(auth.COOKIE) is None


def test_521_strict_secondary_login_security_and_logout_work(strict_host521):
    client = strict_host521
    page = client.get("/secondary/login")
    assert page.status_code == 200
    token = _form_token(page.text)

    login = client.post(
        "/secondary/login",
        data={
            "username": "member-2",
            "password": "secondary-secure-password-521",
            "csrf_token": token,
        },
        follow_redirects=False,
    )
    assert login.status_code == 303, login.text[:160]
    assert client.cookies.get(SECONDARY_COOKIE)

    security = client.get("/secondary/security")
    assert security.status_code == 200
    signed = _form_token(security.text)
    denied = client.post(
        "/secondary/security/revoke-others",
        data={"csrf_token": "forged"},
        follow_redirects=False,
    )
    assert denied.status_code == 403
    allowed = client.post(
        "/secondary/security/revoke-others",
        data={"csrf_token": signed},
        follow_redirects=False,
    )
    assert allowed.status_code == 303
    assert client.cookies.get(SECONDARY_COOKIE)

    # Secondary logout has its own CSRF cookie and must not be double-gated
    # by the root strict mode.
    logout = client.post(
        "/secondary/logout",
        data={"csrf_token": signed},
        follow_redirects=False,
    )
    assert logout.status_code == 303
    assert client.cookies.get(SECONDARY_COOKIE) is None


# Release 576: expand strict-mode session security negative coverage on a
# disposable TestClient host. Do not touch installed accounts or passwords.
def test_576_admin_password_rejects_absent_and_forged_signed_token(strict_host521):
    client = strict_host521
    page = client.get("/login")
    token = _form_token(page.text)
    login = client.post(
        "/login",
        data={
            "username": "operator",
            "password": "administrator-secure-password-521",
            "csrf_token": token,
            "next": "/account/security",
        },
        follow_redirects=False,
    )
    assert login.status_code == 303
    assert client.get("/account/security").status_code == 200
    fields = {
        "current_password": "administrator-secure-password-521",
        "new_password": "unwanted-admin-password-change-576",
        "confirm_password": "unwanted-admin-password-change-576",
    }
    for submitted in (None, "v1.forged"):
        data = dict(fields)
        if submitted is not None:
            data["csrf_token"] = submitted
        denied = client.post("/account/password", data=data, follow_redirects=False)
        assert denied.status_code == 403
    assert auth.session_user(client.cookies.get(auth.COOKIE)) == 1
    assert client.get("/account/security").status_code == 200


def test_576_secondary_security_forgery_and_cross_site_are_denied(strict_host521):
    client = strict_host521
    page = client.get("/secondary/login")
    token = _form_token(page.text)
    login = client.post(
        "/secondary/login",
        data={
            "username": "member-2",
            "password": "secondary-secure-password-521",
            "csrf_token": token,
        },
        follow_redirects=False,
    )
    assert login.status_code == 303
    security = client.get("/secondary/security")
    assert security.status_code == 200
    signed = _form_token(security.text)

    fields = {
        "current_password": "secondary-secure-password-521",
        "new_password": "unwanted-secondary-password-change-576",
        "confirm_password": "unwanted-secondary-password-change-576",
    }
    for submitted in (None, "v1.forged"):
        data = dict(fields)
        if submitted is not None:
            data["csrf_token"] = submitted
        denied = client.post(
            "/secondary/security/password", data=data, follow_redirects=False
        )
        assert denied.status_code == 403

    denied_logout = client.post(
        "/secondary/logout",
        data={"csrf_token": "v1.forged"},
        follow_redirects=False,
    )
    assert denied_logout.status_code == 403

    denied_cross_site = client.post(
        "/secondary/security/revoke-others",
        data={"csrf_token": signed},
        headers={"Sec-Fetch-Site": "cross-site"},
        follow_redirects=False,
    )
    assert denied_cross_site.status_code == 403
    assert client.cookies.get(SECONDARY_COOKIE)
    assert client.get("/secondary/security").status_code == 200
