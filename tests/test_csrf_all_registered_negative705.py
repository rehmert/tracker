"""Release 705: all currently registered ordinary writes reject missing/forged CSRF.

Strict mode is isolated to this TestClient. The data directory is disposable;
no signed business operations or live records are touched. This is negative
security coverage, NOT evidence that valid user writes succeed.
"""
from __future__ import annotations

import re

from fastapi.routing import APIRoute
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


def registered_writes() -> tuple[tuple[str, str], ...]:
    routes = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in (route.methods or set()) & METHODS:
            if route.path in SIGNED_SESSION_POST_PATHS520:
                continue
            # Mounted /secondary has independent session CSRF ownership.
            if route.path.startswith("/secondary/"):
                continue
            routes.add((method, route.path))
    missing = CRITICAL_WRITES - routes
    if missing:
        raise AssertionError(
            "Critical registered write routes disappeared: "
            + repr(sorted(missing))
        )
    return tuple(sorted(routes))


def sample_path(template: str) -> str:
    # All replacements are non-existent synthetic IDs or names. Missing or
    # forged CSRF must fail in middleware before the route is ever executed.
    return re.sub(r"\{[^{}]+\}", "999999999", template)


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
