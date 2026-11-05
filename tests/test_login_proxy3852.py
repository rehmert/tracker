"""Login-origin regression cases for TLS reverse proxies."""

import re

import pytest
from fastapi.testclient import TestClient

from app import config, session_auth385
from app.login_origin3852 import (
    reject_login_origin,
    reject_write_with_login_exception,
)
from app.main import app


def headers(origin, fetch_site="same-origin"):
    return {
        "host": "tracker-internal:8000",
        "origin": origin,
        "sec-fetch-site": fetch_site,
    }


def test_proxy_https_login_origin_accepted():
    assert not reject_login_origin(
        "POST",
        headers("https://tracker-dev.example"),
    )


def test_matching_host_still_accepted():
    assert not reject_login_origin(
        "POST",
        {
            "host": "tracker-dev.example",
            "origin": "https://tracker-dev.example",
            "sec-fetch-site": "same-origin",
        },
    )


@pytest.mark.parametrize(
    "origin,fetch_site",
    [
        ("https://attacker.example", "cross-site"),
        ("https://attacker.example", "same-site"),
        ("https://attacker.example", ""),
        ("null", "same-origin"),
        ("http://tracker-dev.example", "same-origin"),
        ("https://tracker-dev.example/path", "same-origin"),
        ("https://user@tracker-dev.example", "same-origin"),
        ("", "same-origin"),
    ],
)
def test_invalid_proxy_login_rejected(origin, fetch_site):
    assert reject_login_origin(
        "POST",
        headers(origin, fetch_site),
    )


def test_all_other_write_routes_still_protected():
    proxy = headers("https://tracker-dev.example")

    assert reject_write_with_login_exception(
        "POST", "/login", proxy
    ) is False

    assert reject_write_with_login_exception(
        "POST", "/food/entry", proxy
    ) is True

    assert reject_write_with_login_exception(
        "POST", "/doses", proxy
    ) is True

    assert reject_write_with_login_exception(
        "POST", "/logout", proxy
    ) is True


def test_non_browser_proxy_mismatch_does_not_bypass_guard():
    assert reject_login_origin(
        "POST",
        {
            "host": "tracker-internal:8000",
            "origin": "https://tracker-dev.example",
        },
    )


def test_real_login_via_proxy_headers(tmp_path, monkeypatch):
    """Exercise actual FastAPI middleware and login handler."""

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        config, "instance_label",
        lambda: "DEV",
    )

    session_auth385.bootstrap(
        "operator",
        "test-password-3852",
    )
    (tmp_path / session_auth385.FLAG).write_text("enabled")

    with TestClient(
        app,
        base_url="https://tracker-internal:8000",
    ) as client:

        login_page = client.get("/login")
        assert login_page.status_code == 200

        csrf = re.search(
            r'name="csrf_token" value="([^"]+)"',
            login_page.text,
        )

        assert csrf is not None

        # The public HTTPS origin differs from the
        # internal Host received by FastAPI.
        response = client.post(
            "/login",
            headers={
                "Origin": "https://tracker-dev.example",
                "Sec-Fetch-Site": "same-origin",
            },
            data={
                "username": "operator",
                "password": "test-password-3852",
                "csrf_token": csrf.group(1),
                "next": "/",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/"

        assert client.cookies.get(
            session_auth385.COOKIE
        )

        # A valid CSRF token must not make a cross-site
        # submission acceptable.
        bad = client.post(
            "/login",
            headers={
                "Origin": "https://attacker.example",
                "Sec-Fetch-Site": "cross-site",
            },
            data={
                "username": "operator",
                "password": "test-password-3852",
                "csrf_token": csrf.group(1),
                "next": "/",
            },
            follow_redirects=False,
        )

        assert bad.status_code == 403


def test_proxy_login_still_requires_csrf(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        config, "instance_label",
        lambda: "DEV",
    )

    session_auth385.bootstrap(
        "operator",
        "test-password-3852",
    )
    (tmp_path / session_auth385.FLAG).write_text("enabled")

    with TestClient(
        app,
        base_url="https://tracker-internal:8000",
    ) as client:
        page = client.get("/login")
        assert page.status_code == 200

        response = client.post(
            "/login",
            headers={
                "Origin": "https://tracker-dev.example",
                "Sec-Fetch-Site": "same-origin",
            },
            data={
                "username": "operator",
                "password": "test-password-3852",
            },
            follow_redirects=False,
        )

        assert response.status_code == 403
