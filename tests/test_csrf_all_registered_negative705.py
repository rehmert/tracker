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
    if len(routes) < 120:
        raise AssertionError("Registered unsafe-route inventory shrank unexpectedly")
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
    with TestClient(app) as client:
        page = client.get("/labs")
        assert page.status_code == 200
        assert client.cookies.get(COOKIE_NAME)
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
                if result.status_code != 403:
                    failures.append((method, declared, label, result.status_code))
    assert not failures, failures[:25]
    print(f"CSRF_705_REGISTERED_UNSAFE_ROUTES={len(routes)}")
    print(f"CSRF_705_FORGED_DENIAL_CASES={len(routes) * 2}")
    print("CSRF_705_NEGATIVE_MATRIX=PASSED_NOT_POSITIVE_EVIDENCE")
