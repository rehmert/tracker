"""Release 390: authenticated database-dependency conversion."""

from pathlib import Path

import pytest
from fastapi import HTTPException, Request

from app import config
from app import scoped_db390
from app import session_auth385 as auth


def make_request(token=None, user_id=None):
    headers = []

    if token:
        headers.append((
            b"cookie",
            (auth.COOKIE + "=" + token).encode(),
        ))

    scope = {
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
    }

    request = Request(scope)

    if user_id is not None:
        request.state.tracker_user_id = user_id

    return request


@pytest.fixture
def dev_auth(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        config, "instance_label", lambda: "DEV"
    )

    auth.bootstrap("operator", "test-password-390")
    (tmp_path / auth.FLAG).write_text("enabled")
    return tmp_path


def test_missing_session_is_denied(dev_auth):
    generator = scoped_db390.get_scoped_db390(
        make_request()
    )

    with pytest.raises(HTTPException) as error:
        next(generator)

    assert error.value.status_code == 403


def test_untrusted_identity_is_denied(dev_auth):
    token, _ = auth.create_session(False)

    generator = scoped_db390.get_scoped_db390(
        make_request(token, user_id=2)
    )

    with pytest.raises(HTTPException) as error:
        next(generator)

    assert error.value.status_code == 403


def test_revoked_session_is_denied(dev_auth):
    token, _ = auth.create_session(False)
    auth.revoke(token)

    generator = scoped_db390.get_scoped_db390(
        make_request(token, user_id=1)
    )

    with pytest.raises(HTTPException) as error:
        next(generator)

    assert error.value.status_code == 403


def test_legacy_mode_retains_existing_dependency(
    monkeypatch,
):
    monkeypatch.setattr(
        scoped_db390.session_auth385,
        "enabled",
        lambda: False,
    )

    sentinel = object()
    calls = []

    def fake_get_db():
        calls.append("legacy")
        yield sentinel

    monkeypatch.setattr(
        scoped_db390, "get_db", fake_get_db
    )

    generator = scoped_db390.get_scoped_db390(
        make_request()
    )

    assert next(generator) is sentinel

    with pytest.raises(StopIteration):
        next(generator)

    assert calls == ["legacy"]


def test_session_mode_delegates_to_guard(
    dev_auth, monkeypatch,
):
    sentinel = object()
    calls = []

    def fake_get_user_db(request):
        calls.append(request)
        yield sentinel

    monkeypatch.setattr(
        scoped_db390,
        "get_user_db",
        fake_get_user_db,
    )

    request = make_request()

    generator = scoped_db390.get_scoped_db390(
        request
    )

    assert next(generator) is sentinel

    with pytest.raises(StopIteration):
        next(generator)

    assert calls == [request]


@pytest.mark.parametrize(
    "filename",
    (
        "app/routers/dashboard.py",
        "app/routers/doses.py",
        "app/routers/vitals.py",
    ),
)
def test_converted_routes_have_scoped_dependency(filename):
    source = Path(filename).read_text()

    assert "Depends(get_scoped_db390)" in source
    assert "Depends(get_db)" not in source


def test_future_users_still_disabled(dev_auth):
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3, 4):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)


def test_no_user_database_created(dev_auth):
    assert not (dev_auth / "users").exists()
    assert (dev_auth / auth.DATABASE).is_file()
