"""Release 389: authenticated database routing foundation."""

import sqlite3
from pathlib import Path

import pytest
from fastapi import HTTPException, Request

from app import config
from app import session_auth385 as auth
from app import user_db389 as routing


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        config, "DB_PATH", tmp_path / "tracker.db"
    )
    monkeypatch.setattr(
        config, "instance_label", lambda: "DEV"
    )

    auth.bootstrap("operator", "test-password-389")
    (tmp_path / auth.FLAG).write_text("enabled")

    with sqlite3.connect(tmp_path / "tracker.db") as db:
        db.execute("CREATE TABLE private_records (id INTEGER)")
        db.execute("INSERT INTO private_records VALUES (123)")

    return tmp_path


def request_with_cookie(token=None, user_id=1):
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
        "path": "/account/storage-status",
        "raw_path": b"/account/storage-status",
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("127.0.0.1", 50000),
        "server": ("tracker.test", 443),
    }

    request = Request(scope)
    request.state.tracker_user_id = user_id
    return request


def test_username_does_not_determine_database(storage):
    first = routing.username_independent_storage(
        2, "alice"
    )
    renamed = routing.username_independent_storage(
        2, "alice-renamed"
    )
    another = routing.username_independent_storage(
        3, "alice"
    )

    assert first == renamed
    assert first != another
    assert first == storage / "users" / "2" / "tracker.db"


def test_future_users_remain_unavailable(storage):
    for uid in (2, 3, 100):
        plan = routing.future_storage_plan(uid)

        assert plan.mode == "reserved-inactive"
        assert not plan.database.exists()

        with pytest.raises(PermissionError):
            routing.live_storage_for(uid)


def test_missing_session_is_rejected(storage):
    request = request_with_cookie()

    with pytest.raises(HTTPException) as error:
        routing.resolve_authenticated_storage(request)

    assert error.value.status_code == 403


def test_fake_user_identity_is_rejected(storage):
    token, _ = auth.create_session(False)
    request = request_with_cookie(token, user_id=2)

    with pytest.raises(HTTPException) as error:
        routing.resolve_authenticated_storage(request)

    assert error.value.status_code == 403


def test_expired_or_revoked_session_is_rejected(storage):
    token, _ = auth.create_session(False)
    auth.revoke(token)

    with pytest.raises(HTTPException) as error:
        routing.resolve_authenticated_storage(
            request_with_cookie(token)
        )

    assert error.value.status_code == 403


def test_db_engine_mismatch_fails_closed(storage):
    token, _ = auth.create_session(False)

    # The application's engine was created against the
    # test configuration at import time, not this new path.
    with pytest.raises(HTTPException) as error:
        routing.resolve_authenticated_storage(
            request_with_cookie(token)
        )

    assert error.value.status_code == 503


def test_planning_never_copies_admin_records(storage):
    initial = (storage / "tracker.db").stat().st_size

    routing.future_storage_plan(2)
    routing.future_storage_plan(3)

    assert (storage / "tracker.db").stat().st_size == initial
    assert not (storage / "users").exists()


@pytest.mark.parametrize(
    "bad",
    [None, "2", True, -1, 0, 1, 2.0],
)
def test_invalid_future_user_ids_rejected(storage, bad):
    with pytest.raises(ValueError):
        routing.future_storage_plan(bad)
