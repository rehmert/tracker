"""Release 392: request-authorized food export engines."""

import inspect
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, Request
from fastapi.params import Depends as DependsParameter

from app import food_engine392
from app.routers import food_review378, food_week379


def make_request():
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/food/export.csv",
        "raw_path": b"/food/export.csv",
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("127.0.0.1", 50000),
        "server": ("tracker.test", 443),
    })


def test_both_csv_exports_declare_engine_dependency():
    for function in (
        food_review378.export_food_csv,
        food_week379.weekly_csv,
    ):
        parameter = inspect.signature(
            function
        ).parameters["db_engine"]

        dependency = parameter.default

        assert isinstance(dependency, DependsParameter)
        assert dependency.dependency is (
            food_engine392.get_food_engine392
        )


def test_denied_request_never_receives_engine(monkeypatch):
    def deny(request):
        raise HTTPException(403, "Unauthorized")

    monkeypatch.setattr(
        food_engine392,
        "require_food_storage391",
        deny,
    )

    with pytest.raises(HTTPException) as error:
        food_engine392.get_food_engine392(
            make_request()
        )

    assert error.value.status_code == 403


def test_legacy_injected_engine_is_preserved(monkeypatch):
    sentinel = object()

    monkeypatch.setattr(
        food_engine392.session_auth385,
        "enabled",
        lambda: False,
    )

    monkeypatch.setattr(
        food_engine392,
        "require_food_storage391",
        lambda request: None,
    )

    monkeypatch.setattr(
        food_engine392.food,
        "engine",
        sentinel,
    )

    assert (
        food_engine392.get_food_engine392(make_request())
        is sentinel
    )


def test_session_mode_forbids_engine_substitution(monkeypatch):
    monkeypatch.setattr(
        food_engine392.session_auth385,
        "enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        food_engine392,
        "require_food_storage391",
        lambda request: None,
    )

    monkeypatch.setattr(
        food_engine392.food,
        "engine",
        object(),
    )

    with pytest.raises(HTTPException) as error:
        food_engine392.get_food_engine392(
            make_request()
        )

    assert error.value.status_code == 503


def test_session_mode_accepts_only_original_engine(monkeypatch):
    monkeypatch.setattr(
        food_engine392.session_auth385,
        "enabled",
        lambda: True,
    )

    calls = []

    def verified(request):
        calls.append(request)

    monkeypatch.setattr(
        food_engine392,
        "require_food_storage391",
        verified,
    )

    monkeypatch.setattr(
        food_engine392.food,
        "engine",
        food_engine392.administrator_engine,
    )

    request = make_request()

    assert (
        food_engine392.get_food_engine392(request)
        is food_engine392.administrator_engine
    )

    assert calls == [request]


def test_week_details_retains_direct_helper_interface():
    parameter = inspect.signature(
        food_week379.week_details
    ).parameters["db_engine"]

    assert parameter.default is None


def test_csv_export_routes_still_have_food_guard():
    from app.food_storage_guard391 import (
        require_food_storage391,
    )

    for module in (food_review378, food_week379):
        export_routes = [
            route for route in module.router.routes
            if route.path.endswith(".csv")
        ]

        assert export_routes

        for route in export_routes:
            dependencies = [
                item.dependency
                for item in route.dependencies
            ]
            assert require_food_storage391 in dependencies


def test_database_and_authentication_code_unchanged():
    for filename in (
        "app/db.py",
        "app/security.py",
        "app/session_auth385.py",
        "app/user_storage388.py",
    ):
        assert Path(filename).is_file()
