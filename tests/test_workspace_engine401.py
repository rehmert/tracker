"""Release 401: workspace engines and session authorization."""

import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from fastapi import HTTPException, Request
from fastapi.params import Depends as DependsParameter
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import config
from app import workspace_engine401 as routing
from app.db import Base, get_db
from app.models import Compound
from app.user_storage388 import (
    planned_storage,
    prepare_inactive_storage,
    live_storage_for,
)


def make_request():
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/compounds",
        "raw_path": b"/compounds",
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("127.0.0.1", 50000),
        "server": ("tracker.test", 443),
    })


def test_engine_planning_has_no_side_effects(tmp_path):
    first = routing.plan_workspace_engine401(
        2, tmp_path
    )
    second = routing.plan_workspace_engine401(
        3, tmp_path
    )

    assert first.user_id == 2
    assert second.user_id == 3
    assert first.mode == "reserved-inactive"
    assert first.database != second.database
    assert first.url.database == str(first.database)
    assert second.url.database == str(second.database)

    assert not (tmp_path / "users").exists()
    assert not first.database.exists()
    assert not second.database.exists()


def test_legacy_admin_plan_retains_database_path(tmp_path):
    admin = routing.plan_workspace_engine401(
        1, tmp_path
    )

    assert admin.mode == "legacy-admin"
    assert admin.database == tmp_path / "tracker.db"


@pytest.mark.parametrize(
    "bad",
    [None, "2", 2.0, True, 0, -1, "../3"],
)
def test_invalid_user_ids_rejected(tmp_path, bad):
    with pytest.raises(ValueError):
        routing.plan_workspace_engine401(
            bad, tmp_path
        )


@pytest.fixture
def independent_engines(tmp_path):
    """Engines are opened by TEST CODE, never by live routing."""
    first = prepare_inactive_storage(2, tmp_path)
    second = prepare_inactive_storage(3, tmp_path)

    p1 = routing.plan_workspace_engine401(2, tmp_path)
    p2 = routing.plan_workspace_engine401(3, tmp_path)

    assert p1.database == first.database
    assert p2.database == second.database

    e1 = create_engine(
        p1.url,
        connect_args={"check_same_thread": False},
    )
    e2 = create_engine(
        p2.url,
        connect_args={"check_same_thread": False},
    )

    Base.metadata.create_all(e1)
    Base.metadata.create_all(e2)

    try:
        yield first, second, e1, e2
    finally:
        e1.dispose()
        e2.dispose()


def test_duplicate_ids_are_isolated(independent_engines):
    _, _, e1, e2 = independent_engines

    with Session(e1) as db:
        db.add(Compound(name="Account Two"))
        db.commit()

    with Session(e2) as db:
        db.add(Compound(name="Account Three"))
        db.commit()

    with Session(e1) as db:
        item = db.get(Compound, 1)
        assert item.name == "Account Two"

    with Session(e2) as db:
        item = db.get(Compound, 1)
        assert item.name == "Account Three"


def test_independent_session_writes(independent_engines):
    _, _, e1, e2 = independent_engines

    with Session(e1) as db:
        db.add(Compound(name="Only User Two"))
        db.commit()

    with Session(e2) as db:
        assert db.scalars(select(Compound)).all() == []

    with Session(e2) as db:
        db.add(Compound(name="Only User Three"))
        db.commit()

    with Session(e1) as db:
        names = [
            item.name for item in
            db.scalars(select(Compound)).all()
        ]
        assert names == ["Only User Two"]

    with Session(e2) as db:
        names = [
            item.name for item in
            db.scalars(select(Compound)).all()
        ]
        assert names == ["Only User Three"]


def test_test_database_creation_does_not_enable_accounts(
    independent_engines,
):
    for user_id in (2, 3):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)


def test_live_engine_matches_verified_admin(
    tmp_path,
    monkeypatch,
):
    database = tmp_path / "tracker.db"
    database.touch()

    storage = planned_storage(1, tmp_path)

    test_engine = create_engine(
        "sqlite:///" + str(database)
    )

    monkeypatch.setattr(
        routing,
        "authenticated_workspace399",
        lambda _: storage,
    )
    monkeypatch.setattr(
        routing,
        "engine",
        test_engine,
    )
    monkeypatch.setattr(
        config,
        "DB_PATH",
        database,
    )

    try:
        assert routing.resolve_live_engine401(
            make_request()
        ) is test_engine

        monkeypatch.setattr(
            config,
            "DB_PATH",
            tmp_path / "other.db",
        )

        with pytest.raises(HTTPException) as error:
            routing.resolve_live_engine401(
                make_request()
            )

        assert error.value.status_code == 503
    finally:
        test_engine.dispose()


def test_secondary_workspace_engine_is_denied(
    tmp_path,
    monkeypatch,
):
    storage = planned_storage(2, tmp_path)

    monkeypatch.setattr(
        routing,
        "authenticated_workspace399",
        lambda _: storage,
    )

    with pytest.raises(HTTPException) as error:
        routing.resolve_live_engine401(
            make_request()
        )

    assert error.value.status_code == 403


def test_missing_verified_request_is_denied(
    monkeypatch,
):
    def deny(_):
        raise HTTPException(
            403, "Verified session required"
        )

    monkeypatch.setattr(
        routing,
        "authenticated_workspace399",
        deny,
    )

    with pytest.raises(HTTPException) as error:
        routing.resolve_live_engine401(
            make_request()
        )

    assert error.value.status_code == 403


def test_new_dependency_preserves_fastapi_override():
    parameter = inspect.signature(
        routing.get_workspace_db401
    ).parameters["db"]

    dependency = parameter.default

    assert isinstance(
        dependency,
        DependsParameter,
    )
    assert dependency.dependency is get_db


def test_dependency_checks_engine_in_session_mode(
    monkeypatch,
):
    marker = object()
    calls = []

    monkeypatch.setattr(
        routing.session_auth385,
        "enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        routing,
        "resolve_live_engine401",
        lambda _: calls.append("checked"),
    )

    dependency = routing.get_workspace_db401(
        make_request(),
        marker,
    )

    assert next(dependency) is marker
    assert calls == ["checked"]

    with pytest.raises(StopIteration):
        next(dependency)


def test_dependency_denial_does_not_yield_session(
    monkeypatch,
):
    monkeypatch.setattr(
        routing.session_auth385,
        "enabled",
        lambda: True,
    )

    def deny(_):
        raise HTTPException(403, "Denied")

    monkeypatch.setattr(
        routing,
        "resolve_live_engine401",
        deny,
    )

    dependency = routing.get_workspace_db401(
        make_request(),
        object(),
    )

    with pytest.raises(HTTPException) as error:
        next(dependency)

    assert error.value.status_code == 403


def test_legacy_dependency_preserves_existing_behavior(
    monkeypatch,
):
    marker = object()

    monkeypatch.setattr(
        routing.session_auth385,
        "enabled",
        lambda: False,
    )

    def must_not_run(_):
        raise AssertionError("Unexpected session routing")

    monkeypatch.setattr(
        routing,
        "resolve_live_engine401",
        must_not_run,
    )

    dependency = routing.get_workspace_db401(
        make_request(),
        marker,
    )

    assert next(dependency) is marker
