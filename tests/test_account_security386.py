"""Release 386 account security and session-management tests."""

import re

import pytest
from fastapi.testclient import TestClient

from app import config, session_auth385 as auth
from app.main import app


@pytest.fixture
def browser(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setattr(config, "AUTH_USER", "operator")
    monkeypatch.setattr(
        config, "AUTH_PASS", "old-password-386"
    )

    auth.bootstrap("operator", "old-password-386")
    (tmp_path / auth.FLAG).write_text("DEV enabled")

    with TestClient(
        app, base_url="https://tracker-internal:8000"
    ) as client:
        yield client


def login(client, password="old-password-386"):
    page = client.get("/login")
    token = re.search(
        r'name="csrf_token" value="([^"]+)"',
        page.text,
    ).group(1)

    response = client.post(
        "/login",
        data={
            "username": "operator",
            "password": password,
            "csrf_token": token,
            "next": "/",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    return client.cookies.get(auth.COOKIE)


def security_csrf(client):
    response = client.get("/account/security")
    assert response.status_code == 200

    return re.search(
        r'name="csrf_token" value="([^"]+)"',
        response.text,
    ).group(1)


def test_account_security_requires_login(browser):
    response = browser.get(
        "/account/security",
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_session_overview_and_revoke_others(browser):
    first = login(browser)
    second, _ = auth.create_session(True)

    assert len(auth.session_overview(first)) == 2
    csrf = security_csrf(browser)

    result = browser.post(
        "/account/sessions/revoke-others",
        headers={"Origin": "https://tracker-dev.example"},
        data={"csrf_token": csrf},
        follow_redirects=False,
    )

    assert result.status_code == 303
    assert auth.session_user(first) == 1
    assert auth.session_user(second) is None


def test_wrong_account_csrf_is_rejected(browser):
    first = login(browser)
    security_csrf(browser)

    response = browser.post(
        "/account/sessions/revoke-others",
        data={"csrf_token": "forged"},
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert auth.session_user(first) == 1


def test_password_change_revokes_all_sessions(browser):
    old = login(browser)
    other, _ = auth.create_session(True)
    csrf = security_csrf(browser)

    response = browser.post(
        "/account/password",
        headers={"Origin": "https://tracker-dev.example"},
        data={
            "csrf_token": csrf,
            "current_password": "old-password-386",
            "new_password": "new-password-386-secure",
            "confirm_password": "new-password-386-secure",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert auth.session_user(old) is None
    assert auth.session_user(other) is None
    assert not auth.verify_admin(
        "operator", "old-password-386"
    )
    assert auth.verify_admin(
        "operator", "new-password-386-secure"
    )


def test_password_change_wrong_current_preserves_sessions(browser):
    token = login(browser)
    csrf = security_csrf(browser)

    response = browser.post(
        "/account/password",
        data={
            "csrf_token": csrf,
            "current_password": "incorrect",
            "new_password": "new-password-386-secure",
            "confirm_password": "new-password-386-secure",
        },
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert auth.session_user(token) == 1


def test_account_cross_site_rejected(browser):
    login(browser)
    csrf = security_csrf(browser)

    response = browser.post(
        "/account/sessions/revoke-others",
        headers={"Sec-Fetch-Site": "cross-site"},
        data={"csrf_token": csrf},
        follow_redirects=False,
    )

    assert response.status_code == 403


def test_login_global_throttle(browser):
    for index in range(40):
        assert not auth.verify_admin(
            f"other-{index}", "incorrect"
        )

    assert not auth.verify_admin(
        "operator", "old-password-386"
    )


def test_existing_login_still_works(browser):
    assert login(browser)
    response = browser.get("/account/security")
    assert "Account Security" in response.text
