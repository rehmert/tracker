"""Authentication guards for Tracker HTTP routes."""

import base64

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPBasicCredentials
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.security import require_auth


@pytest.fixture
def credentials(monkeypatch):
    def set_values(username, password):
        monkeypatch.setattr(
            config, "AUTH_USER", username
        )
        monkeypatch.setattr(
            config, "AUTH_PASS", password
        )
    return set_values


def header(username, password):
    encoded = base64.b64encode(
        f"{username}:{password}".encode()
    ).decode()
    return {"Authorization": "Basic " + encoded}


def test_both_absent_remains_opt_out(credentials):
    credentials("", "")
    assert require_auth(None) is None

    with TestClient(app) as client:
        response = client.get("/healthz")
        assert response.status_code == 200


@pytest.mark.parametrize(
    "username,password",
    [
        ("operator", ""),
        ("", "secret"),
    ],
)
def test_partial_credentials_fail_closed(
    credentials, username, password
):
    credentials(username, password)

    with pytest.raises(HTTPException) as exc:
        require_auth(None)

    assert exc.value.status_code == 503

    with TestClient(app) as client:
        for path in (
            "/healthz",
            "/labs",
            "/vials",
        ):
            response = client.get(path)
            assert response.status_code == 503

        # Verify a write route is guarded as well.
        response = client.post(
            "/compounds",
            data={"name": "Must Not Be Created"},
            follow_redirects=False,
        )
        assert response.status_code == 503


def test_missing_auth_is_rejected(credentials):
    credentials("operator", "secret")

    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 401
    assert response.headers[
        "www-authenticate"
    ].startswith("Basic")


def test_wrong_auth_is_rejected(credentials):
    credentials("operator", "secret")

    with TestClient(app) as client:
        response = client.get(
            "/healthz",
            headers=header("operator", "wrong"),
        )

    assert response.status_code == 401


def test_correct_auth_is_accepted(credentials):
    credentials("operator", "secret")

    with TestClient(app) as client:
        response = client.get(
            "/healthz",
            headers=header("operator", "secret"),
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_partial_auth_never_accepts_a_header(credentials):
    credentials("operator", "")

    with TestClient(app) as client:
        response = client.get(
            "/healthz",
            headers=header("operator", "anything"),
        )

    assert response.status_code == 503


def test_direct_auth_dependency(credentials):
    credentials("operator", "secret")

    good = HTTPBasicCredentials(
        username="operator",
        password="secret",
    )
    bad = HTTPBasicCredentials(
        username="operator",
        password="incorrect",
    )

    assert require_auth(good) is None

    with pytest.raises(HTTPException) as exc:
        require_auth(bad)

    assert exc.value.status_code == 401
