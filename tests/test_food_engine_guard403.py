"""Release 403: fail-closed food journal engine validation."""

import pytest
from fastapi import HTTPException, Request
from fastapi.routing import APIRoute

from app import food_storage_guard391 as guard
from app.routers import (
    food,
    food_quick375,
    food_bundle376,
    food_manage377,
    food_review378,
    food_week379,
)


MODULES = (
    food,
    food_quick375,
    food_bundle376,
    food_manage377,
    food_review378,
    food_week379,
)


def request():
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/food",
        "raw_path": b"/food",
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("127.0.0.1", 50000),
        "server": ("tracker.test", 443),
    })


@pytest.fixture
def authorized(monkeypatch):
    calls = []

    monkeypatch.setattr(
        guard.session_auth385,
        "enabled",
        lambda: True,
    )

    class Storage:
        user_id = 1
        mode = "legacy-admin"

    def resolve_storage(current):
        calls.append("session")
        return Storage()

    def resolve_engine(current):
        calls.append("engine")
        return guard.administrator_engine

    monkeypatch.setattr(
        guard,
        "resolve_authenticated_storage",
        resolve_storage,
    )

    monkeypatch.setattr(
        guard,
        "resolve_live_engine401",
        resolve_engine,
    )

    return calls


def test_all_database_backed_food_routes_are_guarded():
    count = 0

    for module in MODULES:
        routes = [
            route
            for route in module.router.routes
            if isinstance(route, APIRoute)
        ]

        assert routes, module.__name__

        for route in routes:
            dependencies = {
                dependency.dependency
                for dependency in route.dependencies
            }

            assert (
                guard.require_food_storage391
                in dependencies
            ), route.path

            count += 1

    assert count >= 10


def test_verified_engine_allows_admin(authorized):
    assert guard.require_food_storage391(
        request()
    ) is None

    assert authorized == ["session", "engine"]


def test_unexpected_workspace_engine_is_denied(
    authorized,
    monkeypatch,
):
    monkeypatch.setattr(
        guard,
        "resolve_live_engine401",
        lambda _: object(),
    )

    with pytest.raises(HTTPException) as error:
        guard.require_food_storage391(request())

    assert error.value.status_code == 503
    assert authorized == ["session"]


def test_food_engine_replacement_is_denied(
    authorized,
    monkeypatch,
):
    monkeypatch.setattr(
        food,
        "engine",
        object(),
    )

    with pytest.raises(HTTPException) as error:
        guard.require_food_storage391(request())

    assert error.value.status_code == 503


def test_engine_failure_never_returns_success(
    authorized,
    monkeypatch,
):
    def deny(_):
        raise HTTPException(
            503, "Database configuration mismatch"
        )

    monkeypatch.setattr(
        guard,
        "resolve_live_engine401",
        deny,
    )

    with pytest.raises(HTTPException) as error:
        guard.require_food_storage391(request())

    assert error.value.status_code == 503


def test_session_denial_skips_engine_validation(
    authorized,
    monkeypatch,
):
    calls = []

    def deny(_):
        calls.append("session")
        raise HTTPException(
            403, "Session required"
        )

    def should_not_run(_):
        calls.append("engine")
        raise AssertionError(
            "Engine checked after session denial"
        )

    monkeypatch.setattr(
        guard,
        "resolve_authenticated_storage",
        deny,
    )

    monkeypatch.setattr(
        guard,
        "resolve_live_engine401",
        should_not_run,
    )

    with pytest.raises(HTTPException) as error:
        guard.require_food_storage391(request())

    assert error.value.status_code == 403
    assert calls == ["session"]


def test_legacy_mode_preserves_compatibility(monkeypatch):
    monkeypatch.setattr(
        guard.session_auth385,
        "enabled",
        lambda: False,
    )

    def must_not_run(_):
        raise AssertionError(
            "Unexpected session engine validation"
        )

    monkeypatch.setattr(
        guard,
        "resolve_authenticated_storage",
        must_not_run,
    )

    monkeypatch.setattr(
        guard,
        "resolve_live_engine401",
        must_not_run,
    )

    assert guard.require_food_storage391(
        request()
    ) is None


def test_secondary_user_access_still_disabled():
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)
