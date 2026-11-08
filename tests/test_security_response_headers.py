"""Security headers must preserve existing endpoint policies."""

import base64

from fastapi import Response
from fastapi.testclient import TestClient

from app import config
from app.main import app


def check_headers(response):
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "same-origin"
    assert response.headers["x-content-type-options"] == "nosniff"


def auth_header(user, password):
    token = base64.b64encode(
        f"{user}:{password}".encode()
    ).decode()
    return {"Authorization": "Basic " + token}


def test_health_response(monkeypatch):
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")

    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    check_headers(response)
    assert response.headers["cache-control"] == "private, no-store"


def test_html_response(monkeypatch):
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")

    with TestClient(app) as client:
        response = client.get("/labs")

    assert response.status_code == 200
    check_headers(response)
    assert response.headers["cache-control"] == "private, no-store"


def test_auth_error(monkeypatch):
    monkeypatch.setattr(config, "AUTH_USER", "operator")
    monkeypatch.setattr(config, "AUTH_PASS", "secret")

    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 401
    check_headers(response)
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["www-authenticate"].startswith("Basic")


def test_authenticated_request(monkeypatch):
    monkeypatch.setattr(config, "AUTH_USER", "operator")
    monkeypatch.setattr(config, "AUTH_PASS", "secret")

    with TestClient(app) as client:
        response = client.get(
            "/healthz",
            headers=auth_header("operator", "secret"),
        )

    assert response.status_code == 200
    check_headers(response)


def test_partial_auth_response(monkeypatch):
    monkeypatch.setattr(config, "AUTH_USER", "operator")
    monkeypatch.setattr(config, "AUTH_PASS", "")

    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 503
    check_headers(response)
    assert response.headers["cache-control"] == "private, no-store"


def test_static_assets_not_given_dynamic_cache_policy(monkeypatch):
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")

    with TestClient(app) as client:
        response = client.get("/static/app.css")

    assert response.status_code == 200
    check_headers(response)
    assert response.headers.get("cache-control") != "private, no-store"


def test_missing_route(monkeypatch):
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")

    with TestClient(app) as client:
        response = client.get("/not-a-tracker-route")

    assert response.status_code == 404
    check_headers(response)
    assert response.headers["cache-control"] == "private, no-store"


def test_route_specific_no_store_is_preserved(monkeypatch):
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")

    # Isolated temporary route to test the middleware precedence.
    from fastapi import APIRouter
    router = APIRouter()

    @router.get("/__test_explicit_cache_policy")
    def explicit_policy():
        return Response(
            "private data",
            headers={"Cache-Control": "no-store"},
        )

    app.include_router(router)

    try:
        with TestClient(app) as client:
            response = client.get(
                "/__test_explicit_cache_policy"
            )

        assert response.status_code == 200
        check_headers(response)
        assert response.headers["cache-control"] == "no-store"
    finally:
        # Remove only the test route, not any application route.
        app.router.routes[:] = [
            route for route in app.router.routes
            if getattr(route, "path", None)
            != "/__test_explicit_cache_policy"
        ]
