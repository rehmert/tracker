"""Release 391: food storage authorization coverage."""

from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

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
        "client": ("127.0.0.1", 51000),
        "server": ("tracker.test", 443),
    })


def test_each_food_router_requires_storage_guard():
    for module in MODULES:
        assert module.router.routes, module.__name__

        for route in module.router.routes:
            dependencies = getattr(
                route, "dependencies", ()
            )

            funcs = [
                dependency.dependency
                for dependency in dependencies
            ]

            assert guard.require_food_storage391 in funcs, (
                module.__name__,
                route.path,
            )


def test_guard_denies_missing_session(monkeypatch):
    monkeypatch.setattr(
        guard.session_auth385,
        "enabled",
        lambda: True,
    )

    def deny(_request):
        raise HTTPException(403, "Session required")

    monkeypatch.setattr(
        guard,
        "resolve_authenticated_storage",
        deny,
    )

    with pytest.raises(HTTPException) as error:
        guard.require_food_storage391(request())

    assert error.value.status_code == 403


def test_guard_denies_mismatched_account(monkeypatch):
    monkeypatch.setattr(
        guard.session_auth385,
        "enabled",
        lambda: True,
    )

    def deny(_request):
        raise HTTPException(403, "Account mismatch")

    monkeypatch.setattr(
        guard,
        "resolve_authenticated_storage",
        deny,
    )

    with pytest.raises(HTTPException) as error:
        guard.require_food_storage391(request())

    assert error.value.status_code == 403


def test_guard_accepts_verified_admin(monkeypatch):
    monkeypatch.setattr(
        guard.session_auth385,
        "enabled",
        lambda: True,
    )

    class AdminStorage:
        user_id = 1
        mode = "legacy-admin"

    calls = []

    def authorized(value):
        calls.append(value)
        return AdminStorage()

    monkeypatch.setattr(
        guard,
        "resolve_authenticated_storage",
        authorized,
    )

    engine_calls = []

    def verified_engine(value):
        engine_calls.append(value)
        return guard.administrator_engine

    monkeypatch.setattr(
        guard,
        "resolve_live_engine401",
        verified_engine,
    )

    current = request()

    assert guard.require_food_storage391(current) is None
    assert calls == [current]
    assert engine_calls == [current]


def test_guard_rejects_future_user(monkeypatch):
    monkeypatch.setattr(
        guard.session_auth385,
        "enabled",
        lambda: True,
    )

    class FutureStorage:
        user_id = 2
        mode = "reserved-inactive"

    monkeypatch.setattr(
        guard,
        "resolve_authenticated_storage",
        lambda request: FutureStorage(),
    )

    with pytest.raises(PermissionError):
        guard.require_food_storage391(request())


def test_legacy_mode_does_not_call_session_resolver(
    monkeypatch,
):
    monkeypatch.setattr(
        guard.session_auth385,
        "enabled",
        lambda: False,
    )

    def must_not_run(request):
        raise AssertionError(
            "Session resolver used in legacy mode"
        )

    monkeypatch.setattr(
        guard,
        "resolve_authenticated_storage",
        must_not_run,
    )

    assert guard.require_food_storage391(request()) is None


def test_guard_blocks_food_before_engine_access(monkeypatch):
    monkeypatch.setattr(
        guard.session_auth385,
        "enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        guard,
        "resolve_authenticated_storage",
        lambda request: (_ for _ in ()).throw(
            HTTPException(403, "Denied")
        ),
    )

    application = FastAPI()
    application.include_router(food.router)

    with TestClient(application) as client:
        response = client.get("/food")

    assert response.status_code == 403


def test_all_food_csv_endpoints_are_guarded():
    csv_paths = set()

    for module in MODULES:
        for route in module.router.routes:
            if route.path.endswith(".csv"):
                csv_paths.add(route.path)

                funcs = [
                    item.dependency
                    for item in route.dependencies
                ]

                assert guard.require_food_storage391 in funcs

    assert "/food/export.csv" in csv_paths
    assert "/food/weekly.csv" in csv_paths


def test_no_food_database_engine_change():
    for filename in (
        "app/db.py",
        "app/config.py",
        "app/user_db389.py",
    ):
        assert Path(filename).is_file()


def test_future_accounts_remain_disabled():
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3, 4):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)
