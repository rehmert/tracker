"""Phase 1 login through a TLS-terminating reverse proxy."""

import re

import pytest
from fastapi.testclient import TestClient

from app import config, session_auth385
from app.main import app


@pytest.fixture
def browser(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        config, "instance_label",
        lambda: "DEV",
    )
    monkeypatch.setattr(config, "AUTH_USER", "operator")
    monkeypatch.setattr(
        config, "AUTH_PASS", "test-password-3853"
    )

    session_auth385.bootstrap(
        "operator", "test-password-3853"
    )

    (tmp_path / session_auth385.FLAG).write_text(
        "DEV session login enabled"
    )

    with TestClient(
        app,
        base_url="https://tracker-internal:8000",
    ) as client:
        yield client


def login_token(browser):
    response = browser.get("/login")

    assert response.status_code == 200

    match = re.search(
        r'name="csrf_token" value="([^"]+)"',
        response.text,
    )

    assert match is not None
    return match.group(1)


def credentials(token):
    return {
        "username": "operator",
        "password": "test-password-3853",
        "csrf_token": token,
        "next": "/",
    }


@pytest.mark.parametrize(
    "site",
    [
        "same-origin",
        "same-site",
        "",
    ],
)
def test_proxy_login_with_valid_csrf(browser, site):
    token = login_token(browser)

    response = browser.post(
        "/login",
        headers={
            "Origin": "https://tracker-dev.example",
            "Sec-Fetch-Site": site,
        },
        data=credentials(token),
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert browser.cookies.get(session_auth385.COOKIE)
    assert (
        session_auth385.session_user(
            browser.cookies.get(session_auth385.COOKIE)
        ) == 1
    )


def test_proxy_login_without_fetch_metadata(browser):
    token = login_token(browser)

    response = browser.post(
        "/login",
        headers={
            "Origin": "https://tracker-dev.example",
        },
        data=credentials(token),
        follow_redirects=False,
    )

    assert response.status_code == 303


def test_wrong_csrf_rejected(browser):
    login_token(browser)

    response = browser.post(
        "/login",
        headers={
            "Origin": "https://tracker-dev.example",
            "Sec-Fetch-Site": "same-origin",
        },
        data=credentials("forged-token"),
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert not browser.cookies.get(session_auth385.COOKIE)


def test_missing_csrf_rejected(browser):
    login_token(browser)

    response = browser.post(
        "/login",
        headers={"Origin": "https://tracker-dev.example"},
        data={
            "username": "operator",
            "password": "test-password-3853",
        },
        follow_redirects=False,
    )

    assert response.status_code == 403


def test_cross_site_login_rejected_even_with_token(browser):
    token = login_token(browser)

    response = browser.post(
        "/login",
        headers={
            "Origin": "https://attacker.example",
            "Sec-Fetch-Site": "cross-site",
        },
        data=credentials(token),
        follow_redirects=False,
    )

    assert response.status_code == 403


def test_other_routes_still_block_cross_origin(browser):
    response = browser.post(
        "/compounds",
        headers={
            "Origin": "https://attacker.example",
            "Sec-Fetch-Site": "cross-site",
        },
        data={"name": "Forbidden Product"},
        follow_redirects=False,
    )

    assert response.status_code == 403


def test_login_cannot_create_multiuser_access(browser):
    token = login_token(browser)

    response = browser.post(
        "/login",
        headers={
            "Origin": "https://tracker-dev.example",
            "Sec-Fetch-Site": "same-origin",
        },
        data={
            "username": "another-user",
            "password": "test-password-3853",
            "csrf_token": token,
            "next": "/",
        },
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert not browser.cookies.get(session_auth385.COOKIE)


def test_logout_requires_csrf(browser):
    token = login_token(browser)

    login = browser.post(
        "/login",
        data=credentials(token),
        follow_redirects=False,
    )

    assert login.status_code == 303

    denied = browser.post(
        "/logout",
        data={},
        follow_redirects=False,
    )

    assert denied.status_code == 403
    assert browser.cookies.get(session_auth385.COOKIE)
