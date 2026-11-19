"""Release 705: all currently registered ordinary writes reject missing/forged CSRF.

Strict mode is isolated to this TestClient. The data directory is disposable;
no signed business operations or live records are touched. This is negative
security coverage, NOT evidence that valid user writes succeed.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, FastAPI
from fastapi.routing import iter_route_contexts
from fastapi.testclient import TestClient

from app import config
from app.csrf_enforcement520 import SIGNED_SESSION_POST_PATHS520
from app.csrf_runtime import COOKIE_NAME, HEADER_NAME
from app.main import app

METHODS = frozenset(("POST", "PUT", "PATCH", "DELETE"))

# Independent, explicit critical-write sentinels grounded in registered
# application routes. The historical source report's 161 declarations include
# scopes and conventions not identical to FastAPI's runtime APIRoute list.
# Do not invent a total-route threshold and call it an application regression.
CRITICAL_WRITES = frozenset({
    ("POST", "/compounds"),
    ("POST", "/coas/new"),
    ("POST", "/doses"),
    ("DELETE", "/doses/{did}"),
    ("POST", "/food/water"),
    ("POST", "/labs"),
    ("POST", "/pages"),
    ("POST", "/protocols"),
    ("POST", "/purchases"),
    ("POST", "/regimen/items"),
    ("POST", "/supplies"),
    ("DELETE", "/vitals/{rid}"),
    ("POST", "/vitals"),
    ("POST", "/vials/bulk"),
    ("POST", "/workouts/backfill"),
})


def enumerate_unsafe_routes(route_items) -> set[tuple[str, str]]:
    """Use FastAPI 0.162's *effective* included-router route contexts.

    FastAPI 0.137+ stores included routers as lazy _IncludedRouter entries.
    These top-level ASGI entries have no path or methods. The framework's
    iter_route_contexts expands them, retaining the include-time prefix and
    the leaf route's real methods. Inspecting app.routes directly silently
    loses every Tracker business route on the installed FastAPI version.
    """
    routes = set()
    for context in iter_route_contexts(route_items):
        path = context.path
        methods = context.methods
        if not isinstance(path, str) or not path.startswith("/"):
            continue
        if path.startswith(("/secondary/", "/static/")):
            continue
        if not methods:
            continue
        for method in {str(item).upper() for item in methods} & METHODS:
            if method == "POST" and path in SIGNED_SESSION_POST_PATHS520:
                continue
            routes.add((method, path))
    return routes

def registered_writes() -> tuple[tuple[str, str], ...]:
    actual = tuple(app.routes)
    routes = enumerate_unsafe_routes(actual)
    missing = CRITICAL_WRITES - routes
    if missing:
        # Display only route classes, safe route paths and methods. Never
        # expose cookies, tokens, user data, credentials or payloads.
        examples = [
            (type(route).__module__ + "." + type(route).__name__,
             getattr(route, "path", None),
             type(getattr(route, "original_router", None)).__name__)
            for route in actual[:24]
        ]
        raise AssertionError(
            "Critical registered write routes missing after ASGI inspection: "
            + repr(sorted(missing))
            + "; routes discovered=" + str(len(routes))
            + "; total top-level ASGI entries=" + str(len(actual))
            + "; sample=" + repr(examples)
        )
    return tuple(sorted(routes))

def sample_path(template: str) -> str:
    # All replacements are non-existent synthetic IDs or names. Missing or
    # forged CSRF must fail in middleware before the route is ever executed.
    return re.sub(r"\{[^{}]+\}", "999999999", template)


def test_705_fastapi_0162_resolves_real_included_routers():
    """Regression against the installed FastAPI router implementation.

    This is not a synthetic SimpleNamespace: FastAPI itself constructs the
    included-router objects and the same framework iterator resolves them.
    """
    fixture = FastAPI()
    child = APIRouter()

    @child.post("/create")
    def create():
        return {"ok": True}

    @child.delete("/item/{item_id}")
    def remove(item_id: int):
        return {"id": item_id}

    nested = APIRouter()
    nested.include_router(child, prefix="/nested")
    fixture.include_router(nested, prefix="/v1")

    actual = enumerate_unsafe_routes(fixture.routes)
    assert actual == {
        ("POST", "/v1/nested/create"),
        ("DELETE", "/v1/nested/item/{item_id}"),
    }, actual
    assert len(fixture.routes) >= 1
    print("CSRF_705_FASTAPI_INCLUDED_ROUTER_RESOLUTION=PASSED")


def test_705_application_route_inventory_has_critical_writes():
    """Fail before any HTTP test if current routes aren't inventoried."""
    routes = set(registered_writes())
    assert CRITICAL_WRITES <= routes
    assert routes
    print(f"CSRF_705_REGISTERED_UNSAFE_ROUTES={len(routes)}")

def test_705_all_registered_unsafe_routes_reject_missing_and_forged_csrf(
    monkeypatch, tmp_path,
):
    monkeypatch.setenv("TRACKER_CSRF_ENFORCE", "1")
    monkeypatch.setenv("TRACKER_ORIGIN_GUARD", "1")
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)

    routes = registered_writes()
    failures = []
    observed = set()
    with TestClient(app) as client:
        page = client.get("/labs")
        assert page.status_code == 200
        token = client.cookies.get(COOKIE_NAME)
        assert token
        # A valid token reaches route validation (but the deliberately empty
        # Compound name cannot create a record). This confirms strict mode
        # is not merely rejecting all writes indiscriminately.
        signed_invalid = client.post(
            "/compounds", data={"name": ""},
            headers={HEADER_NAME: token}, follow_redirects=False,
        )
        assert signed_invalid.status_code == 422
        for method, declared in routes:
            url = sample_path(declared)
            for label, headers in (
                ("missing", {}),
                ("forged", {HEADER_NAME: "forged-705-token"}),
            ):
                result = client.request(
                    method, url, data={"csrf_probe_705": "invalid"},
                    headers=headers, follow_redirects=False,
                )
                observed.add((method, declared, label))
                if result.status_code != 403:
                    failures.append((method, declared, label, result.status_code))
    assert not failures, failures[:25]
    assert observed == {
        (method, path, label)
        for method, path in routes for label in ("missing", "forged")
    }
    print(f"CSRF_705_REGISTERED_UNSAFE_ROUTES={len(routes)}")
    print(f"CSRF_705_FORGED_DENIAL_CASES={len(routes) * 2}")
    print("CSRF_705_NEGATIVE_MATRIX=PASSED_NOT_POSITIVE_EVIDENCE")
