"""Release 402: request-scoped database engine authorization."""

import ast
import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException, Request, FastAPI, Depends
from fastapi.params import Depends as DependsParameter
from fastapi.testclient import TestClient

from app import scoped_db390
from app import workspace_engine401
from app.db import get_db


ROOT = Path(__file__).resolve().parents[1]


def make_request():
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/vitals",
        "raw_path": b"/vitals",
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("127.0.0.1", 50000),
        "server": ("tracker.test", 443),
    })


def test_existing_fastapi_override_contract():
    parameter = inspect.signature(
        scoped_db390.get_scoped_db390
    ).parameters["db"]

    dependency = parameter.default

    assert isinstance(dependency, DependsParameter)
    assert dependency.dependency is get_db


def test_new_engine_dependency_retains_override_contract():
    parameter = inspect.signature(
        workspace_engine401.get_workspace_db401
    ).parameters["db"]

    dependency = parameter.default

    assert isinstance(dependency, DependsParameter)
    assert dependency.dependency is get_db


def test_both_checks_run_before_session_exposure(monkeypatch):
    marker = object()
    calls = []

    monkeypatch.setattr(
        scoped_db390.session_auth385,
        "enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        scoped_db390,
        "resolve_authenticated_storage",
        lambda request: calls.append("session"),
    )

    monkeypatch.setattr(
        workspace_engine401,
        "resolve_live_engine401",
        lambda request: calls.append("engine"),
    )

    generator = scoped_db390.get_scoped_db390(
        make_request(),
        marker,
    )

    assert next(generator) is marker
    assert calls == ["session", "engine"]

    with pytest.raises(StopIteration):
        next(generator)


def test_engine_failure_does_not_expose_database(monkeypatch):
    calls = []

    monkeypatch.setattr(
        scoped_db390.session_auth385,
        "enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        scoped_db390,
        "resolve_authenticated_storage",
        lambda request: calls.append("session"),
    )

    def reject_engine(request):
        calls.append("engine-denied")
        raise HTTPException(
            503,
            "Workspace engine mismatch",
        )

    monkeypatch.setattr(
        workspace_engine401,
        "resolve_live_engine401",
        reject_engine,
    )

    generator = scoped_db390.get_scoped_db390(
        make_request(),
        object(),
    )

    with pytest.raises(HTTPException) as error:
        next(generator)

    assert error.value.status_code == 503
    assert calls == ["session", "engine-denied"]


def test_session_failure_skips_engine_check(monkeypatch):
    calls = []

    monkeypatch.setattr(
        scoped_db390.session_auth385,
        "enabled",
        lambda: True,
    )

    def reject_session(request):
        calls.append("session-denied")
        raise HTTPException(403, "Not authenticated")

    monkeypatch.setattr(
        scoped_db390,
        "resolve_authenticated_storage",
        reject_session,
    )

    monkeypatch.setattr(
        workspace_engine401,
        "resolve_live_engine401",
        lambda request: calls.append("engine"),
    )

    generator = scoped_db390.get_scoped_db390(
        make_request(),
        object(),
    )

    with pytest.raises(HTTPException) as error:
        next(generator)

    assert error.value.status_code == 403
    assert calls == ["session-denied"]


def test_secondary_workspace_engine_is_rejected(
    monkeypatch,
    tmp_path,
):
    from app.user_storage388 import planned_storage

    monkeypatch.setattr(
        workspace_engine401,
        "authenticated_workspace399",
        lambda request: planned_storage(2, tmp_path),
    )

    with pytest.raises(HTTPException) as error:
        workspace_engine401.resolve_live_engine401(
            make_request()
        )

    assert error.value.status_code == 403


def test_legacy_mode_skips_session_and_engine(monkeypatch):
    marker = object()

    monkeypatch.setattr(
        scoped_db390.session_auth385,
        "enabled",
        lambda: False,
    )

    def unexpected(request):
        raise AssertionError("Unexpected validation")

    monkeypatch.setattr(
        scoped_db390,
        "resolve_authenticated_storage",
        unexpected,
    )

    monkeypatch.setattr(
        workspace_engine401,
        "resolve_live_engine401",
        unexpected,
    )

    generator = scoped_db390.get_scoped_db390(
        make_request(),
        marker,
    )

    assert next(generator) is marker

    with pytest.raises(StopIteration):
        next(generator)


def test_fastapi_override_still_works(monkeypatch):
    monkeypatch.setattr(
        scoped_db390.session_auth385,
        "enabled",
        lambda: False,
    )

    app = FastAPI()

    def fake_database():
        yield {"marker": "isolated-test"}

    app.dependency_overrides[get_db] = fake_database

    @app.get("/test")
    def test_route(
        db=Depends(scoped_db390.get_scoped_db390),
    ):
        return {"marker": db["marker"]}

    with TestClient(app) as client:
        response = client.get("/test")

    assert response.status_code == 200
    assert response.json() == {
        "marker": "isolated-test",
    }


def test_existing_routes_keep_original_dependency():
    source = (
        ROOT / "app/scoped_db390.py"
    ).read_text()

    tree = ast.parse(source)

    dependencies = []

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Depends"
            and node.args
            and isinstance(node.args[0], ast.Name)
        ):
            dependencies.append(node.args[0].id)

    assert dependencies == ["get_db"]

    assert "yield from get_workspace_db401" in source


def test_secondary_user_live_storage_still_disabled():
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3, 100):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)
