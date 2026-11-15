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
from scripts.tracker_csrf_gap_plan590 import build

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


def gap_rows():
    report = build()
    assert report["status"] == "BLOCKED_SOURCE_ONLY_NOT_GLOBAL_CLEARANCE"
    assert report["total_unsafe_routes"] == 144 + len(NEW_FOOD_ROUTES)
    assert report["remaining_without_source_witness"] == 61 + len(NEW_FOOD_ROUTES)
    rows = [(row["method"], row["path"]) for row in report["unqualified_routes"]]
    assert len(rows) == 61 + len(NEW_FOOD_ROUTES)
    assert len(set(rows)) == len(rows)
    assert set(rows) & SESSION_OWNED == SESSION_OWNED
    assert NEW_FOOD_ROUTES <= set(rows)
    # No baseline unqualified routes may disappear without an explicit
    # source-witness reconciliation, even if the total remains unchanged.
    return sorted(set(rows) - SESSION_OWNED)


UNQUALIFIED_GLOBAL_ROUTES = gap_rows()
assert len(UNQUALIFIED_GLOBAL_ROUTES) == 55 + len(NEW_FOOD_ROUTES)


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
