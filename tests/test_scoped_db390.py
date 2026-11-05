"""Release 390.2: authenticated and override-compatible DB access."""

import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException, Request
from fastapi.params import Depends as DependsParameter

from app import config
from app import scoped_db390
from app import session_auth385 as auth
from app.db import get_db


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
        config, "instance_label",
        lambda: "DEV",
    )

    auth.bootstrap("operator", "test-password-3902")
    (tmp_path / auth.FLAG).write_text("enabled")

    return tmp_path


def test_declares_real_fastapi_subdependency():
    parameter = inspect.signature(
        scoped_db390.get_scoped_db390
    ).parameters["db"]

    dependency = parameter.default

    assert isinstance(dependency, DependsParameter)
    assert dependency.dependency is get_db


def test_missing_session_is_denied(dev_auth):
    generator = scoped_db390.get_scoped_db390(
        make_request(),
        db=object(),
    )

    with pytest.raises(HTTPException) as error:
        next(generator)

    assert error.value.status_code == 403


def test_untrusted_identity_is_denied(dev_auth):
    token, _ = auth.create_session(False)

    generator = scoped_db390.get_scoped_db390(
        make_request(token, user_id=2),
        db=object(),
    )

    with pytest.raises(HTTPException) as error:
        next(generator)

    assert error.value.status_code == 403


def test_revoked_session_is_denied(dev_auth):
    token, _ = auth.create_session(False)
    auth.revoke(token)

    generator = scoped_db390.get_scoped_db390(
        make_request(token, user_id=1),
        db=object(),
    )

    with pytest.raises(HTTPException) as error:
        next(generator)

    assert error.value.status_code == 403


def test_legacy_mode_preserves_injected_db(monkeypatch):
    monkeypatch.setattr(
        scoped_db390.session_auth385,
        "enabled",
        lambda: False,
    )

    sentinel = object()

    generator = scoped_db390.get_scoped_db390(
        make_request(),
        db=sentinel,
    )

    assert next(generator) is sentinel

    with pytest.raises(StopIteration):
        next(generator)


def test_session_mode_validates_before_yield(
    dev_auth, monkeypatch,
):
    from app import workspace_engine401

    sentinel = object()
    calls = []

    def fake_resolver(request):
        calls.append(("session", request))
        return object()

    def fake_engine(request):
        calls.append(("engine", request))
        return object()

    monkeypatch.setattr(
        scoped_db390,
        "resolve_authenticated_storage",
        fake_resolver,
    )

    monkeypatch.setattr(
        workspace_engine401,
        "resolve_live_engine401",
        fake_engine,
    )

    request = make_request()

    generator = scoped_db390.get_scoped_db390(
        request,
        db=sentinel,
    )

    assert next(generator) is sentinel

    with pytest.raises(StopIteration):
        next(generator)

    assert calls == [
        ("session", request),
        ("engine", request),
    ]



def test_failed_guard_never_exposes_session(
    dev_auth, monkeypatch,
):
    def deny(request):
        raise HTTPException(403, "Denied")

    monkeypatch.setattr(
        scoped_db390,
        "resolve_authenticated_storage",
        deny,
    )

    generator = scoped_db390.get_scoped_db390(
        make_request(),
        db=object(),
    )

    with pytest.raises(HTTPException) as error:
        next(generator)

    assert error.value.status_code == 403


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


def test_future_users_remain_disabled(dev_auth):
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3, 4):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)


def test_no_user_database_created(dev_auth):
    assert not (dev_auth / "users").exists()
    assert (dev_auth / auth.DATABASE).is_file()
