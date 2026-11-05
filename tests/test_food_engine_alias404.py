"""Release 404: reject mismatched food database engine aliases."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from app import food_storage_guard391 as guard
from app.routers import food, food_quick375


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
    monkeypatch.setattr(
        guard.session_auth385,
        "enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        guard,
        "resolve_authenticated_storage",
        lambda _: SimpleNamespace(
            user_id=1,
            mode="legacy-admin",
        ),
    )

    monkeypatch.setattr(
        guard,
        "resolve_live_engine401",
        lambda _: guard.administrator_engine,
    )

    return monkeypatch


def test_original_engines_are_accepted(authorized):
    assert food.engine is guard.administrator_engine
    assert food_quick375.engine is guard.administrator_engine

    assert guard.require_food_storage391(request()) is None


@pytest.mark.parametrize(
    "module",
    [food, food_quick375],
)
def test_replaced_engine_alias_is_rejected(
    authorized,
    module,
):
    authorized.setattr(
        module,
        "engine",
        object(),
    )

    with pytest.raises(HTTPException) as error:
        guard.require_food_storage391(request())

    assert error.value.status_code == 503


def test_quick_log_denied_before_handler_runs(
    authorized,
    monkeypatch,
):
    monkeypatch.setattr(
        food_quick375,
        "engine",
        object(),
    )

    app = FastAPI()
    app.include_router(food_quick375.router)

    with TestClient(app) as client:
        response = client.post(
            "/food/quick/1",
            data={
                "day": "2026-11-05",
                "meal": "Breakfast",
                "servings": "1",
            },
            follow_redirects=False,
        )

    assert response.status_code == 503


def test_favorite_denied_before_handler_runs(
    authorized,
    monkeypatch,
):
    monkeypatch.setattr(
        food_quick375,
        "engine",
        object(),
    )

    app = FastAPI()
    app.include_router(food_quick375.router)

    with TestClient(app) as client:
        response = client.post(
            "/food/favorite/1",
            data={"day": "2026-11-05"},
            follow_redirects=False,
        )

    assert response.status_code == 503


def test_session_denial_precedes_alias_validation(
    authorized,
    monkeypatch,
):
    def deny(_):
        raise HTTPException(403, "Session denied")

    monkeypatch.setattr(
        guard,
        "resolve_authenticated_storage",
        deny,
    )
    monkeypatch.setattr(
        food_quick375,
        "engine",
        object(),
    )

    with pytest.raises(HTTPException) as error:
        guard.require_food_storage391(request())

    assert error.value.status_code == 403


def test_legacy_mode_keeps_isolated_test_support(
    monkeypatch,
):
    monkeypatch.setattr(
        guard.session_auth385,
        "enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        food_quick375,
        "engine",
        object(),
    )

    assert guard.require_food_storage391(request()) is None


def test_secondary_users_remain_disabled():
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)
