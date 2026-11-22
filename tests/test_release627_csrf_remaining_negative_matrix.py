"""Release 627: fail-closed matrix for currently unqualified unsafe routes.

This validates strict-mode denial only. It is NOT successful signed-browser
lifecycle evidence, and cannot change source witness counts in gap plan 590.
All requests use an isolated test client and omit required CSRF credentials.
"""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.csrf_reporting import REPORT_HEADER
from app.csrf_runtime import COOKIE_NAME, HEADER_NAME
from scripts.tracker_csrf_reconcile627 import build, CURRENT_UNQUALIFIED_ADDITIONS

ROOT = Path(__file__).resolve().parents[1]
# Session-owned routes validate independent signed double-submit tokens.
# They must be verified with their enabled-session fixtures, not claimed as
# coverage through this global middleware-only matrix.
SESSION_OWNED = frozenset({
    ("POST", "/login"),
    ("POST", "/logout"),
    ("POST", "/account/password"),
    ("POST", "/account/sessions/revoke-others"),
    ("POST", "/account/users"),
    ("POST", "/account/users/edit"),
})


# The Release 627 baseline was 144 unsafe routes (61 without source
# witnesses). Release 629 added the equivalent-merge route; Release 630
# added two resolution routes. They remain unqualified and MUST appear
# in the strict negative CSRF matrix, not be silently counted as covered.
NEW_FOOD_ROUTES = frozenset({
    ("POST", "/food/duplicates/merge"),
    ("POST", "/food/duplicates/resolve-unused"),
    ("POST", "/food/duplicates/keep-distinct"),
})


# Release 635 adds nine regimen write routes. These are NOT positive signed
# browser witnesses and must remain in the strict negative matrix.
NEW_REGIMEN_ROUTES = frozenset({
    ("POST", "/regimen/items"),
    ("POST", "/regimen/items/{item_id}/edit"),
    ("POST", "/regimen/items/{item_id}/archive"),
    ("POST", "/regimen/schedules"),
    ("POST", "/regimen/schedules/{schedule_id}/edit"),
    ("POST", "/regimen/schedules/{schedule_id}/stop"),
    ("POST", "/regimen/entries"),
    ("POST", "/regimen/entries/{entry_id}/edit"),
    ("POST", "/regimen/entries/{entry_id}/delete"),
})
# Release 643: two COA attachment write endpoints remain without positive
# signed-browser clearance. Include both in the strict negative matrix.
NEW_COA_ROUTES = frozenset({
    ("POST", "/coas/{cid}/attachments"),
    ("POST", "/coas/{cid}/attachments/{aid}/delete"),
})
NEW_DEFAULT_ROUTES645 = frozenset({
    ("POST", "/coas/{cid}/attachments/{aid}/test-type"),
    ("POST", "/coas/{cid}/default-file"),
})
# Release 647 adds one bulk metadata write route. It must get negative
# strict-CSRF coverage; this is not a positive signed-browser witness.
NEW_BULK_ROUTES647 = frozenset({
    ("POST", "/coas/{cid}/attachments/test-types"),
})
NEW_UNQUALIFIED_ROUTES = (
    NEW_FOOD_ROUTES | NEW_REGIMEN_ROUTES | NEW_COA_ROUTES |
    NEW_DEFAULT_ROUTES645 | NEW_BULK_ROUTES647
)


def _regimen_route_manifest():
    from scripts.tracker_csrf_route_inventory620 import extract
    return {
        (row["methods"][0], row["route"])
        for row in extract(ROOT / "app/routers/regimen635.py", ROOT)
        if len(row["methods"]) == 1
    }


def test_635_regimen_unsafe_routes_are_explicit_and_not_source_qualified():
    assert _regimen_route_manifest() == NEW_REGIMEN_ROUTES
    report = build()
    unqualified = {(r["method"], r["path"]) for r in report["remaining_routes"]}
    assert NEW_REGIMEN_ROUTES <= unqualified
    newly_mapped = {(r["method"], r["path"]) for r in report["new_627_positive_routes"]}
    assert not NEW_REGIMEN_ROUTES & newly_mapped


def gap_rows():
    # Old Release 627 used 144 + 17, a frozen inventory predating the
    # 652 catalog and 654+ Workout/COA/Food routes. Use the CURRENT
    # conservative reconciliation, not its obsolete static count.
    report = build()
    assert report["status"] == "BLOCKED_PENDING_FULL_DEV_AND_MANUAL_REVIEW"
    assert report["source_only"] is True
    assert report["current_unsafe_routes"] >= 202
    assert report["pre_627_unqualified_routes"] == 61
    rows = [(row["method"], row["path"])
            for row in report["remaining_routes"]]
    assert len(rows) == report["remaining_without_positive_source_witness"]
    assert len(rows) >= 92
    assert len(set(rows)) == len(rows)
    assert SESSION_OWNED <= set(rows)
    assert CURRENT_UNQUALIFIED_ADDITIONS <= set(rows)
    assert NEW_UNQUALIFIED_ROUTES <= set(rows)
    positives = {(row["method"], row["path"])
                 for row in report["new_627_positive_routes"]}
    assert not positives & set(rows)
    # Session-owned routes have their own mandatory signed scheme.
    # Ordinary unqualified routes still receive both runtime negative
    # tests below for every current conservative source declaration.
    return sorted(set(rows) - SESSION_OWNED)


UNQUALIFIED_GLOBAL_ROUTES = gap_rows()
assert len(UNQUALIFIED_GLOBAL_ROUTES) >= 86


@pytest.fixture(scope="module")
def strict_client(tmp_path_factory):
    # The fixture never supplies a database with real user data.
    # The built-in Lifespan migration operates only on the configured app DB;
    # use monkeypatch to isolate any persistence and signing key artifacts.
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("TRACKER_CSRF_ENFORCE", "1")
        monkeypatch.setattr(config, "DATA_DIR", tmp_path_factory.mktemp("csrf627"))
        monkeypatch.setattr(config, "AUTH_USER", "")
        monkeypatch.setattr(config, "AUTH_PASS", "")
        with TestClient(app) as client:
            yield client


def render(path):
    return re.sub(r"\\{[^{}]+\\}", "999999", path)


@pytest.mark.parametrize("method,path", UNQUALIFIED_GLOBAL_ROUTES,
                         ids=lambda value: str(value))
def test_627_untokened_write_fails_closed(strict_client, method, path):
    request_path = render(path)
    response = strict_client.request(
        method, request_path,
        content=b"placeholder=unused",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert response.status_code == 403, (method, path, response.status_code)
    assert response.headers[REPORT_HEADER] == "missing", (method, path)


@pytest.mark.parametrize("method,path", UNQUALIFIED_GLOBAL_ROUTES)
def test_627_invalid_signed_header_fails_closed(strict_client, method, path):
    # A cookie signed for this isolated client must not authorize a tampered
    # header, even when the browser presents the legitimate cookie.
    landing = strict_client.get("/labs")
    assert landing.status_code == 200
    assert COOKIE_NAME in strict_client.cookies
    response = strict_client.request(
        method, render(path),
        content=b"placeholder=unused",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            HEADER_NAME: "tampered-token",
        },
        follow_redirects=False,
    )
    assert response.status_code == 403, (method, path, response.status_code)
    assert response.headers[REPORT_HEADER] == "invalid", (method, path)


def test_627_session_routes_are_explicitly_excluded_from_global_matrix():
    assert len(SESSION_OWNED) == 6
    assert not set(UNQUALIFIED_GLOBAL_ROUTES) & SESSION_OWNED
    source = (ROOT / "app/csrf_enforcement520.py").read_text()
    for _, path in SESSION_OWNED:
        assert f'"{path}"' in source
    assert 'os.environ.get("TRACKER_CSRF_ENFORCE", "0")' in (
        ROOT / "app/main.py"
    ).read_text()
