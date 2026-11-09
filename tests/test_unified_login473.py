"""Release 473: DEV unified login and account boundaries."""
import re

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import config
from app import session_auth385 as auth
from app.security import require_auth
from app.routers import session_login385
from app.secondary_preview430 import (
    COOKIE as SECONDARY_COOKIE,
    preview_app,
    _session_user,
)
from app.unified_login473 import enabled473
from app.user_bootstrap426 import (
    initialize_staged_workspace426,
)
from app.user_accounts427 import (
    stage_secondary_account427,
)


@pytest.fixture
def browser(tmp_path, monkeypatch):
    monkeypatch.setattr(
        config, "DATA_DIR", tmp_path
    )
    monkeypatch.setattr(
        config, "instance_label", lambda: "DEV"
    )
    monkeypatch.setenv(
        "TRACKER_SECONDARY_PREVIEW430", "1"
    )
    monkeypatch.setenv(
        "TRACKER_MULTIUSER_LOGIN473", "1"
    )
    monkeypatch.delenv(
        "TRACKER_SECONDARY_LOCKDOWN440",
        raising=False,
    )

    auth.bootstrap(
        "operator",
        "administrator-secure-password-473",
    )
    (tmp_path / auth.FLAG).write_text("enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(
            uid, tmp_path
        )
        stage_secondary_account427(
            uid,
            f"member-{uid}",
            f"secondary-secure-password-{uid}-473",
        )

    host = FastAPI(
        dependencies=[Depends(require_auth)]
    )

    host.include_router(
        session_login385.router
    )
    host.mount("/secondary", preview_app)

    @host.get("/admin-only")
    def admin_only():
        return {"administrator": True}

    with TestClient(
        host,
        base_url="https://tracker.test",
    ) as client:
        yield client


def login(client, username, password, destination="/"):
    page = client.get("/login")
    assert page.status_code == 200

    match = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        page.text,
    )
    assert match is not None

    return client.post(
        "/login",
        data={
            "username": username,
            "password": password,
            "csrf_token": match.group(1),
            "next": destination,
        },
        follow_redirects=False,
    )


def test_473_secondary_login_and_admin_denial(browser):
    client = browser

    assert enabled473()

    response = login(
        client,
        "member-2",
        "secondary-secure-password-2-473",
        "/admin-only",
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/secondary/overview"
    )

    secondary_token = client.cookies.get(
        SECONDARY_COOKIE
    )

    assert secondary_token
    assert _session_user(secondary_token) == 2
    assert client.cookies.get(auth.COOKIE) is None

    workspace = client.get(
        "/secondary/orm-summary.json"
    )

    assert workspace.status_code == 200
    assert workspace.json()["user_id"] == 2

    admin = client.get(
        "/admin-only",
        follow_redirects=False,
    )

    assert admin.status_code == 303
    assert admin.headers["location"].startswith(
        "/login"
    )


def test_473_secondary_account_switch_revokes_old(browser):
    client = browser

    first = login(
        client,
        "member-2",
        "secondary-secure-password-2-473",
    )
    assert first.status_code == 303

    old_token = client.cookies.get(
        SECONDARY_COOKIE
    )

    second = login(
        client,
        "member-3",
        "secondary-secure-password-3-473",
    )
    assert second.status_code == 303

    new_token = client.cookies.get(
        SECONDARY_COOKIE
    )

    assert new_token != old_token
    assert _session_user(old_token) is None
    assert _session_user(new_token) == 3

    report = client.get(
        "/secondary/orm-summary.json"
    )

    assert report.status_code == 200
    assert report.json()["user_id"] == 3

    denied = client.get(
        "/admin-only",
        follow_redirects=False,
    )

    assert denied.status_code == 303


def test_473_admin_login_clears_secondary(browser):
    client = browser

    login(
        client,
        "member-2",
        "secondary-secure-password-2-473",
    )

    old_token = client.cookies.get(
        SECONDARY_COOKIE
    )
    assert old_token

    response = login(
        client,
        "operator",
        "administrator-secure-password-473",
        "/admin-only",
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/admin-only"
    )

    assert _session_user(old_token) is None
    assert client.cookies.get(SECONDARY_COOKIE) is None

    admin_token = client.cookies.get(auth.COOKIE)

    assert auth.session_user(admin_token) == 1

    admin = client.get("/admin-only")

    assert admin.status_code == 200
    assert admin.json() == {
        "administrator": True
    }


def test_473_secondary_replaces_admin(browser):
    client = browser

    login(
        client,
        "operator",
        "administrator-secure-password-473",
    )

    old_admin = client.cookies.get(auth.COOKIE)
    assert auth.session_user(old_admin) == 1

    response = login(
        client,
        "member-2",
        "secondary-secure-password-2-473",
    )
    assert response.status_code == 303

    assert auth.session_user(old_admin) is None
    assert client.cookies.get(auth.COOKIE) is None

    assert _session_user(
        client.cookies.get(SECONDARY_COOKIE)
    ) == 2


def test_473_flag_default_off(browser, monkeypatch):
    client = browser

    monkeypatch.delenv(
        "TRACKER_MULTIUSER_LOGIN473",
        raising=False,
    )
    assert enabled473() is False

    response = login(
        client,
        "member-2",
        "secondary-secure-password-2-473",
    )
    assert response.status_code == 401

    assert client.cookies.get(
        SECONDARY_COOKIE
    ) is None


def test_473_lockdown_and_prod_fail_closed(
    browser, monkeypatch
):
    client = browser

    monkeypatch.setenv(
        "TRACKER_SECONDARY_LOCKDOWN440", "1"
    )
    assert not enabled473()

    response = login(
        client,
        "member-2",
        "secondary-secure-password-2-473",
    )
    assert response.status_code == 401

    monkeypatch.delenv(
        "TRACKER_SECONDARY_LOCKDOWN440"
    )
    monkeypatch.setattr(
        config,
        "instance_label",
        lambda: "PROD",
    )

    assert enabled473()

    response = client.get("/login")
    assert response.status_code == 200


def test_473_invalid_credentials(browser):
    client = browser

    response = login(
        client,
        "member-2",
        "wrong-password-473",
    )
    assert response.status_code == 401
    assert client.cookies.get(
        SECONDARY_COOKIE
    ) is None
    assert client.cookies.get(auth.COOKIE) is None


def test_473_no_global_database_access():
    from pathlib import Path

    module = Path(
        "app/unified_login473.py"
    ).read_text()

    assert "TRACKER_MULTIUSER_LOGIN473" in module
    assert "preview_enabled()" in module

    for forbidden in (
        "create_engine(",
        "SessionLocal(",
        "from .db import",
        "sqlite3.connect(",
    ):
        assert forbidden not in module


def test_473_login_cookie_visible_to_root_login(browser):
    """Verify the browser sends the secondary cookie to /login.

    No application endpoint is added. In particular, a
    secondary user must not bypass the administrator-wide
    require_auth dependency merely to test cookie scope.
    """
    client = browser

    response = login(
        client,
        "member-2",
        "secondary-secure-password-2-473",
    )

    assert response.status_code == 303

    token = client.cookies.get(SECONDARY_COOKIE)
    assert token

    headers = response.headers.get_list("set-cookie")

    issued = [
        value for value in headers
        if value.startswith(
            SECONDARY_COOKIE + "="
        )
        and "Max-Age=1800" in value
    ]

    assert len(issued) == 1

    issued_cookie = issued[0].lower()

    assert "path=/" in issued_cookie
    assert "path=/secondary" not in issued_cookie
    assert "secure" in issued_cookie
    assert "httponly" in issued_cookie
    assert "samesite=strict" in issued_cookie

    # httpx builds this request using the same cookie jar
    # and URL path-matching rules as the TestClient.
    # A root-path session cookie must be present.
    root_request = client.build_request(
        "GET", "/login"
    )

    sent_cookie = root_request.headers.get(
        "cookie", ""
    )

    from http.cookies import SimpleCookie

    parsed = SimpleCookie()
    parsed.load(sent_cookie)

    assert SECONDARY_COOKIE in parsed
    assert parsed[SECONDARY_COOKIE].value == token

    # The secondary cookie is not an administrator cookie.
    assert auth.COOKIE not in parsed


def test_473_switch_clears_legacy_cookie_path(browser):
    client = browser

    response = login(
        client,
        "member-2",
        "secondary-secure-password-2-473",
    )

    assert response.status_code == 303

    headers = response.headers.get_list("set-cookie")

    assert any(
        value.startswith(SECONDARY_COOKIE + "=")
        and "path=/secondary" in value.lower()
        and "max-age=0" in value.lower()
        for value in headers
    )

    response = login(
        client,
        "operator",
        "administrator-secure-password-473",
    )

    assert response.status_code == 303

    headers = response.headers.get_list("set-cookie")

    for required_path in ("path=/", "path=/secondary"):
        assert any(
            value.startswith(SECONDARY_COOKIE + "=")
            and required_path in value.lower()
            and "max-age=0" in value.lower()
            for value in headers
        )


def test_478_failed_login_can_retry_with_same_form(browser):
    """A 401 response must provide a valid retry token."""
    from app.routers.session_login385 import LOGIN_CSRF
    from app.csrf_tokens import verify_pair
    from app.csrf_runtime import load_key

    client = browser

    failed = login(
        client,
        "member-2",
        "incorrect-password",
    )

    assert failed.status_code == 401
    assert "Sign-in unsuccessful" in failed.text

    match = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        failed.text,
    )
    assert match, "Retry form token missing"

    retry_token = match.group(1)
    assert retry_token
    assert verify_pair(
        client.cookies.get(LOGIN_CSRF),
        retry_token,
        load_key(),
    )

    assert client.cookies.get(auth.COOKIE) is None
    assert client.cookies.get(SECONDARY_COOKIE) is None

    # Submit directly from the returned error page.
    # No intervening GET /login is permitted.
    retried = client.post(
        "/login",
        data={
            "username": "member-2",
            "password": (
                "secondary-secure-password-2-473"
            ),
            "csrf_token": retry_token,
            "next": "/",
        },
        follow_redirects=False,
    )

    assert retried.status_code == 303
    assert retried.headers["location"] == (
        "/secondary/overview"
    )

    secondary_token = client.cookies.get(
        SECONDARY_COOKIE
    )
    assert secondary_token
    assert _session_user(secondary_token) == 2


def test_478_blank_login_token_still_rejected(browser):
    """Never bypass CSRF to make retries work."""
    client = browser
    page = client.get("/login")

    assert page.status_code == 200

    response = client.post(
        "/login",
        data={
            "username": "member-2",
            "password": (
                "secondary-secure-password-2-473"
            ),
            "csrf_token": "",
            "next": "/",
        },
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert client.cookies.get(SECONDARY_COOKIE) is None
    assert client.cookies.get(auth.COOKIE) is None


def test_478_admin_retry_also_works(browser):
    """Administrator and secondary login share the fix."""
    client = browser

    failed = login(
        client,
        "operator",
        "incorrect-password",
        "/admin-only",
    )
    assert failed.status_code == 401

    match = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        failed.text,
    )
    assert match
    token = match.group(1)
    assert token

    retried = client.post(
        "/login",
        data={
            "username": "operator",
            "password": (
                "administrator-secure-password-473"
            ),
            "csrf_token": token,
            "next": "/admin-only",
        },
        follow_redirects=False,
    )

    assert retried.status_code == 303
    assert retried.headers["location"] == (
        "/admin-only"
    )
    assert auth.session_user(
        client.cookies.get(auth.COOKIE)
    ) == 1
