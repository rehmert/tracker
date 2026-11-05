"""Release 393.1: server-side authenticated ownership."""

import pytest
from fastapi import HTTPException, Request

from app import config, session_auth385 as auth
from app.request_scope393 import (
    VerifiedRequestScope,
    establish_request_scope,
    verified_request_scope,
)
from app.security import require_auth


def make_request(token=None):
    headers = []

    if token:
        headers.append((
            b"cookie",
            (auth.COOKIE + "=" + token).encode(),
        ))

    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/vitals",
        "raw_path": b"/vitals",
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("127.0.0.1", 50000),
        "server": ("tracker.test", 443),
    })


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        config,
        "instance_label",
        lambda: "DEV",
    )

    auth.bootstrap("operator", "password-3931")
    (tmp_path / auth.FLAG).write_text("enabled")
    return tmp_path


def test_login_attaches_verified_scope(environment):
    token, _ = auth.create_session(False)
    request = make_request(token)

    assert require_auth(None, request) is None

    scope = verified_request_scope(request)

    assert isinstance(scope, VerifiedRequestScope)
    assert scope.user_id == 1
    assert scope.storage.mode == "legacy-admin"
    assert scope.storage.database == (
        environment / "tracker.db"
    )


def test_username_does_not_choose_database(environment):
    token, _ = auth.create_session(False)
    request = make_request(token)

    require_auth(None, request)
    scope = verified_request_scope(request)

    assert scope.storage.database.name == "tracker.db"
    assert "users" not in scope.storage.database.parts


@pytest.mark.parametrize(
    "invalid",
    [2, 3, 0, True, "1", None],
)
def test_other_user_ids_are_rejected(environment, invalid):
    with pytest.raises(PermissionError):
        establish_request_scope(
            make_request(), invalid
        )


def test_missing_session_cannot_establish_scope(environment):
    with pytest.raises(PermissionError):
        establish_request_scope(
            make_request(), 1
        )


def test_forged_request_state_is_rejected(environment):
    token, _ = auth.create_session(False)
    request = make_request(token)

    require_auth(None, request)
    request.state.tracker_user_id = 2

    with pytest.raises(HTTPException) as error:
        verified_request_scope(request)

    assert error.value.status_code == 403


def test_revocation_invalidates_scope(environment):
    token, _ = auth.create_session(False)
    request = make_request(token)

    require_auth(None, request)
    auth.revoke(token)

    with pytest.raises(HTTPException) as error:
        verified_request_scope(request)

    assert error.value.status_code == 403


def test_scope_does_not_provision_user_database(environment):
    token, _ = auth.create_session(False)
    request = make_request(token)

    require_auth(None, request)

    assert not (environment / "users").exists()
    assert not (environment / "tracker.db").exists()


def test_missing_login_does_not_attach_scope(environment):
    request = make_request()

    with pytest.raises(HTTPException):
        require_auth(None, request)

    assert not hasattr(
        request.state,
        "tracker_verified_scope393",
    )


def test_legacy_auth_remains_compatible(monkeypatch):
    monkeypatch.setattr(
        auth, "enabled", lambda: False
    )
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")

    assert require_auth(None, make_request()) is None
