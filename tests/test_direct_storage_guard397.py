"""Release 397: direct SQLite and backup authorization tests."""

from pathlib import Path

import pytest

from fastapi import HTTPException, Request
from fastapi.routing import APIRoute

from app import direct_storage_guard397 as guard
from app.routers import (
    backups,
    record_explorer,
    sqlite_viewer,
)


def request():
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/sqlite-viewer",
        "raw_path": b"/sqlite-viewer",
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("127.0.0.1", 50000),
        "server": ("tracker.test", 443),
    })


def fake_storage(root, user_id=1, mode="legacy-admin"):
    from app.user_storage388 import StoragePaths

    return StoragePaths(
        user_id=user_id,
        mode=mode,
        root=root,
        database=root / "tracker.db",
        coa=root / "uploads" / "coa",
        labs=root / "uploads" / "labs",
        backups=root / "backups",
    )


def test_every_direct_tool_route_has_guard():
    expected = {
        sqlite_viewer: guard.require_direct_storage397,
        record_explorer: guard.require_direct_storage397,
        backups: guard.require_backup_storage397,
    }

    for module, dependency in expected.items():
        routes = [
            route for route in module.router.routes
            if isinstance(route, APIRoute)
        ]

        assert routes, module.__name__

        for route in routes:
            functions = [
                item.dependency
                for item in route.dependencies
            ]

            assert dependency in functions, (
                module.__name__,
                route.path,
            )


def test_missing_session_is_denied(monkeypatch):
    monkeypatch.setattr(
        guard.session_auth385,
        "enabled",
        lambda: True,
    )

    def deny(_):
        raise HTTPException(403, "Session required")

    monkeypatch.setattr(
        guard,
        "resolve_authenticated_storage",
        deny,
    )

    with pytest.raises(HTTPException) as error:
        guard.require_direct_storage397(request())

    assert error.value.status_code == 403


def test_future_user_is_denied(monkeypatch, tmp_path):
    monkeypatch.setattr(
        guard.session_auth385,
        "enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        guard,
        "resolve_authenticated_storage",
        lambda _: fake_storage(
            tmp_path,
            user_id=2,
            mode="reserved-inactive",
        ),
    )

    with pytest.raises(HTTPException) as error:
        guard.require_direct_storage397(request())

    assert error.value.status_code == 403


def test_configured_database_must_match_user(
    monkeypatch,
    tmp_path,
):
    database = tmp_path / "tracker.db"
    database.write_bytes(b"test-database-placeholder")

    monkeypatch.setattr(
        guard.session_auth385,
        "enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        guard,
        "resolve_authenticated_storage",
        lambda _: fake_storage(tmp_path),
    )

    monkeypatch.setattr(
        guard.config,
        "DB_URL",
        "sqlite:///" + str(database),
    )

    assert guard.require_direct_storage397(
        request()
    ) is None

    monkeypatch.setattr(
        guard.config,
        "DB_URL",
        "sqlite:///" + str(tmp_path / "other.db"),
    )

    with pytest.raises(HTTPException) as error:
        guard.require_direct_storage397(request())

    assert error.value.status_code == 503


def test_symlinked_database_is_denied(
    monkeypatch,
    tmp_path,
):
    real_db = tmp_path / "real.db"
    real_db.write_bytes(b"placeholder")

    alias = tmp_path / "tracker.db"
    alias.symlink_to(real_db)

    monkeypatch.setattr(
        guard.session_auth385,
        "enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        guard,
        "resolve_authenticated_storage",
        lambda _: fake_storage(tmp_path),
    )

    monkeypatch.setattr(
        guard.config,
        "DB_URL",
        "sqlite:///" + str(alias),
    )

    with pytest.raises(HTTPException) as error:
        guard.require_direct_storage397(request())

    assert error.value.status_code == 503


def test_backup_storage_symlink_is_denied(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        guard.session_auth385,
        "enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        guard,
        "require_direct_storage397",
        lambda _: None,
    )

    backup_real = tmp_path / "backup-real"
    backup_real.mkdir()

    backup_alias = tmp_path / "backup-link"
    backup_alias.symlink_to(
        backup_real,
        target_is_directory=True,
    )

    monkeypatch.setattr(
        guard.backup,
        "BACKUP_DIR",
        backup_alias,
    )

    with pytest.raises(HTTPException) as error:
        guard.require_backup_storage397(request())

    assert error.value.status_code == 503


def test_legacy_auth_mode_remains_compatible(monkeypatch):
    monkeypatch.setattr(
        guard.session_auth385,
        "enabled",
        lambda: False,
    )

    def unexpected(_):
        raise AssertionError(
            "Session resolver invoked in legacy mode"
        )

    monkeypatch.setattr(
        guard,
        "resolve_authenticated_storage",
        unexpected,
    )

    assert guard.require_direct_storage397(
        request()
    ) is None

    assert guard.require_backup_storage397(
        request()
    ) is None


def test_secondary_user_databases_remain_disabled():
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3, 4):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)
