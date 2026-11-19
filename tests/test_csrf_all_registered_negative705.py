"""Release 705: all currently registered ordinary writes reject missing/forged CSRF.

Strict mode is isolated to this TestClient. The data directory is disposable;
no signed business operations or live records are touched. This is negative
security coverage, NOT evidence that valid user writes succeed.
"""
from __future__ import annotations

import re

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
    """Inspect actual ASGI registered routes by shape, not a class assumption.

    FastAPI/Starlette route classes and wrappers can change independently of
    the route metadata. Recurse only into mounted non-secondary applications.
    Avoid a guessed minimum route count: fail closed on critical sentinels
    after examining the runtime route inventory.
    """
    routes = set()

    def visit(items, prefix="", depth=0):
        if depth > 4:
            raise AssertionError("Unexpectedly nested ASGI router hierarchy")
        for route in items:
            path = getattr(route, "path", "")
            if not isinstance(path, str) or not path.startswith("/"):
                continue
            full_path = prefix + path
            if full_path.startswith(("/secondary/", "/static/")):
                continue
            methods = getattr(route, "methods", None)
            if methods is not None:
                names = {methods.upper()} if isinstance(methods, str) else {
                    str(item).upper() for item in methods
                }
                for method in names & METHODS:
                    if not (
                        method == "POST"
                        and full_path in SIGNED_SESSION_POST_PATHS520
                    ):
                        routes.add((method, full_path))
            nested = getattr(route, "routes", None)
            if nested is not None and not methods:
                visit(nested, full_path.rstrip("/"), depth + 1)

    visit(route_items)
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
             sorted(str(x) for x in (getattr(route, "methods", None) or ())))
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


def test_705_route_enumeration_handles_wrapped_routes_and_nested_mounts():
    from types import SimpleNamespace

    # Dependency/library class identity must not decide route coverage.
    # Registered method metadata is the contract; session and secondary
    # routes have independent CSRF ownership.
    entries = [
        SimpleNamespace(path="/compounds", methods={"POST"}),
        SimpleNamespace(path="/vitals/{rid}", methods={"DELETE", "GET"}),
        SimpleNamespace(path="/custom", methods="PATCH"),
        SimpleNamespace(
            path="/tools", methods=None,
            routes=[SimpleNamespace(path="/write", methods={"PUT"})],
        ),
        SimpleNamespace(
            path="/secondary", methods=None,
            routes=[SimpleNamespace(path="/vitals/new", methods={"POST"})],
        ),
        SimpleNamespace(path="/login", methods={"POST"}),
        SimpleNamespace(path="/static", methods=None),
    ]
    assert enumerate_unsafe_routes(entries) == {
        ("POST", "/compounds"),
        ("DELETE", "/vitals/{rid}"),
        ("PATCH", "/custom"),
        ("PUT", "/tools/write"),
    }


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
