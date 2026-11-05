"""Release 398: direct SQLite Maintenance Review protection."""

from fastapi import FastAPI, HTTPException
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app import direct_storage_guard397 as guard
from app.routers import maintenance_review


def test_all_maintenance_routes_have_guard():
    routes = [
        route
        for route in maintenance_review.router.routes
        if isinstance(route, APIRoute)
    ]

    assert routes

    for route in routes:
        dependencies = [
            item.dependency
            for item in route.dependencies
        ]

        assert (
            guard.require_direct_storage397
            in dependencies
        )


def test_denied_session_never_opens_database():
    app = FastAPI()
    app.include_router(
        maintenance_review.router
    )

    def deny():
        raise HTTPException(
            403,
            "Administrator session required",
        )

    app.dependency_overrides[
        guard.require_direct_storage397
    ] = deny

    with TestClient(app) as client:
        response = client.get(
            "/maintenance-review"
        )

    assert response.status_code == 403


def test_read_only_sqlite_mode_preserved():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "app/routers/maintenance_review.py"
    ).read_text()

    assert "sqlite3.connect(" in source
    assert "mode=ro" in source
    assert "query_only=ON" in source
