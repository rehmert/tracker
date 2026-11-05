import re

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app import config, session_auth385 as auth
from app.security import require_auth
from app.routers.session_login385 import router, build_login_html


@pytest.fixture
def client_env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setattr(config, "AUTH_USER", "operator")
    monkeypatch.setattr(config, "AUTH_PASS", "sample-password")

    auth.bootstrap("operator", "sample-password")
    (tmp_path / auth.FLAG).write_text("enabled")

    app = FastAPI(dependencies=[Depends(require_auth)])
    app.include_router(router)

    @app.get("/private")
    def private():
        return {"private": True}

    with TestClient(
        app, base_url="https://tracker.test"
    ) as client:
        yield client, tmp_path


def test_login_html_is_well_formed():
    html = build_login_html(
        '/private?x="test"',
        "test-token",
    )

    assert 'name="next"' in html
    assert 'name="csrf_token"' in html
    assert "&quot;" in html
    assert "</html>" in html


def test_database_is_separate(client_env):
    _, directory = client_env
    assert (directory / auth.DATABASE).exists()
    assert not (directory / "tracker.db").exists()


def test_authentication_redirect_and_session(client_env):
    client, _ = client_env

    response = client.get(
        "/private", follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/login?next="
    )

    login = client.get("/login?next=/private")
    assert login.status_code == 200

    token = re.search(
        r'name="csrf_token" value="([^"]+)"',
        login.text,
    ).group(1)

    response = client.post(
        "/login",
        data={
            "username": "operator",
            "password": "sample-password",
            "csrf_token": token,
            "next": "/private",
            "remember": "yes",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/private"
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "secure" in response.headers["set-cookie"].lower()

    assert client.get("/private").status_code == 200

    session = client.cookies.get(auth.COOKIE)
    assert auth.session_user(session) == 1

    auth.revoke(session)
    assert auth.session_user(session) is None


def test_missing_login_csrf_is_rejected(client_env):
    client, _ = client_env

    response = client.post(
        "/login",
        data={
            "username": "operator",
            "password": "sample-password",
        },
        follow_redirects=False,
    )

    assert response.status_code == 403


def test_external_redirect_rejected():
    assert auth.safe_next("//example.com") == "/"
    assert auth.safe_next("https://example.com") == "/"
    assert auth.safe_next("/\\example.com") == "/"
    assert auth.safe_next("/food") == "/food"


def test_prod_cannot_enable(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    (tmp_path / auth.FLAG).write_text("enabled")

    assert auth.enabled() is False
