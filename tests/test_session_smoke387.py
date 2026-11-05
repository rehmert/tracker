"""Release 387: remove DEV Basic Auth bypass safely."""

import base64
import runpy
from pathlib import Path

import pytest
from fastapi import HTTPException, Request
from fastapi.security import HTTPBasicCredentials

from app import config
from app import session_auth385 as auth
from app.security import require_auth


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        config, "instance_label", lambda: "DEV"
    )
    monkeypatch.setattr(config, "AUTH_USER", "operator")
    monkeypatch.setattr(
        config, "AUTH_PASS", "legacy-password-387"
    )

    monkeypatch.setenv("TRACKER_INSTANCE", "DEV")
    monkeypatch.setenv(
        "TRACKER_DATA_DIR", str(tmp_path)
    )

    auth.bootstrap("operator", "login-password-387")
    (tmp_path / auth.FLAG).write_text("enabled")

    return tmp_path


def make_request(cookie=None):
    headers = [
        (
            b"user-agent",
            b"Tracker-Release-Smoke/1.0",
        ),
    ]

    if cookie:
        headers.append(
            (
                b"cookie",
                (auth.COOKIE + "=" + cookie).encode(),
            )
        )

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/healthz",
        "raw_path": b"/healthz",
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("127.0.0.1", 51234),
        "server": ("127.0.0.1", 8000),
    }

    return Request(scope)


def test_old_basic_auth_no_longer_bypasses_dev(environment):
    credentials = HTTPBasicCredentials(
        username="operator",
        password="legacy-password-387",
    )

    with pytest.raises(HTTPException) as error:
        require_auth(credentials, make_request())

    assert error.value.status_code == 303
    assert error.value.headers["Location"].startswith(
        "/login?next="
    )


def test_valid_session_still_authenticates(environment):
    token, _ = auth.create_session(False)

    request = make_request(token)

    assert require_auth(None, request) is None
    assert request.state.tracker_user_id == 1


def test_smoke_uses_and_revokes_temporary_session(environment):
    script = Path(
        "scripts/tracker-runtime-smoke.py"
    )

    module = runpy.run_path(str(script))

    settings = {
        "TRACKER_INSTANCE": "DEV",
        "TRACKER_USER": "operator",
        "TRACKER_PASS": "legacy-password-387",
        "TRACKER_DATA_DIR": str(environment),
    }

    factory = module["release_auth_headers"]

    with factory("DEV", settings) as headers:
        assert "Authorization" not in headers
        assert "Cookie" in headers

        token = headers["Cookie"].split("=", 1)[1]

        assert auth.session_user(token) == 1

        sessions = auth.session_overview(token)
        assert len(sessions) == 1

    assert auth.session_user(token) is None


def test_prod_smoke_remains_basic_auth(environment):
    module = runpy.run_path(
        "scripts/tracker-runtime-smoke.py"
    )

    settings = {
        "TRACKER_INSTANCE": "PROD",
        "TRACKER_USER": "operator",
        "TRACKER_PASS": "legacy-password-387",
    }

    with module["release_auth_headers"](
        "PROD", settings
    ) as headers:
        assert "Authorization" in headers
        assert "Cookie" not in headers

        value = headers["Authorization"].split(" ", 1)[1]

        assert base64.b64decode(value).decode() == (
            "operator:legacy-password-387"
        )


def test_no_user_data_database_created(environment):
    assert (environment / auth.DATABASE).is_file()
    assert not (environment / "tracker.db").exists()
