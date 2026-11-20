"""Release 707: twelve real positive strict-CSRF lifecycles, HTTP and HTTPS.

Nine regimen mutations and three COA test-type catalog writes each receive
a tokenless 403 before the same *valid* signed operation is persisted in a
private SQLite database. This does not certify other 80 historical route gaps.
"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from playwright.sync_api import sync_playwright

HTTP_URL = os.environ.get("TRACKER_TEST_URL", "").rstrip("/")
HTTPS_URL = os.environ.get("TRACKER_TEST_HTTPS_URL", "").rstrip("/")
DATA = Path(os.environ.get("TRACKER_BROWSER_QA_DATA_DIR", "/")).resolve()
HTTP, HTTPS = urlsplit(HTTP_URL), urlsplit(HTTPS_URL)

if not (
    os.environ.get("TRACKER_TEST_ISOLATED") == "1"
    and os.environ.get("TRACKER_TEST_STRICT_CSRF") == "1"
    and HTTP.scheme == "http"
    and HTTPS.scheme == "https"
    and HTTP.hostname == HTTPS.hostname == "127.0.0.1"
    and HTTP.port not in (None, 8000)
    and HTTPS.port not in (None, 443, 8000, HTTP.port)
    and DATA.name == "data"
    and DATA.is_dir()
    and not DATA.is_symlink()
    and DATA.parent.parent == Path("/tmp").resolve()
    and re.fullmatch(r"tracker-browser-qa[.][A-Za-z0-9_]{8}", DATA.parent.name)
):
    raise RuntimeError("707 signed-write qualification requires disposable strict Chromium QA")

DATABASE = DATA / "tracker.db"
pytestmark = pytest.mark.browser

REGIMEN_ROUTES = frozenset({
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
CATALOG_ROUTES = frozenset({
    ("POST", "/coa-test-types"),
    ("POST", "/coa-test-types/{type_id}/edit"),
    ("POST", "/coa-test-types/{type_id}/toggle"),
})
REQUIRED_ROUTES = REGIMEN_ROUTES | CATALOG_ROUTES
assert len(REQUIRED_ROUTES) == 12


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        chromium = playwright.chromium.launch(headless=True)
        yield chromium
        chromium.close()


def read(sql: str, args: tuple = ()):
    """Read only the verified disposable browser-QA SQLite database."""
    if (not DATABASE.is_file() or DATABASE.is_symlink()
            or DATABASE.resolve().parent != DATA):
        raise AssertionError("No private browser-QA database")
    with sqlite3.connect(DATABASE, timeout=20) as connection:
        return connection.execute(sql, args).fetchone()


def browser_context(browser, base: str, landing: str):
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    response = page.goto(base + landing, wait_until="networkidle")
    assert response is not None and response.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert isinstance(token, str) and token.startswith("v1.")
    # A real browser rendered the token, rather than the test minting it.
    cookie = next((c for c in context.cookies() if c["name"] == "tracker_csrf_v1"), None)
    assert cookie is not None and cookie["value"] == token
    return context, page, token


def signed_write(page, base, token, path, fields, state):
    """Require denial without token + unchanged persisted state, then success."""
    before = state()
    denial = page.request.post(base + path, form=fields, max_redirects=0)
    assert denial.status == 403, (path, "tokenless", denial.status)
    assert state() == before, (path, "unsigned write changed persisted data")

    forgery = page.request.post(
        base + path, form=fields, max_redirects=0,
        headers={"X-Tracker-CSRF": "forged-707-token"},
    )
    assert forgery.status == 403, (path, "forged", forgery.status)
    assert state() == before, (path, "forged write changed persisted data")

    accepted = page.request.post(
        base + path, form=fields, max_redirects=0,
        headers={"X-Tracker-CSRF": token},
    )
    assert accepted.status == 303, (path, "signed", accepted.status,
                                    accepted.text()[:240])
    assert accepted.headers.get("x-tracker-csrf-report") == "valid"
    return accepted


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_707_regimen_nine_valid_signed_persisted_lifecycles(browser, scheme):
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    context, page, token = browser_context(browser, base, "/regimen")
    seen = set()
    try:
        # Ensure the real rendered native form carries a browser-usable token.
        native = page.locator('form[action="/regimen/items"][method="post" i]')
        assert native.count() == 1
        assert native.locator('input[name="csrf_token"]').input_value() == token

        unique = uuid4().hex[:12]
        name = "QA707 regimen " + scheme + " " + unique
        item_fields = {"kind": "supplement", "name": name, "notes": "synthetic"}
        signed_write(page, base, token, "/regimen/items", item_fields,
                     lambda: read("SELECT COUNT(*) FROM regimen_items635 WHERE name=?", (name,)))
        seen.add(("POST", "/regimen/items"))
        item = read("SELECT id,kind,active FROM regimen_items635 WHERE name=?", (name,))
        assert item is not None and item[1:] == ("supplement", 1)
        item_id = item[0]

        updated = name + " edited"
        route = f"/regimen/items/{item_id}/edit"
        signed_write(page, base, token, route,
                     {"kind": "supplement", "name": updated, "active": "yes",
                      "notes": "QA707 edited"},
                     lambda: read("SELECT name,active,notes FROM regimen_items635 WHERE id=?",
                                  (item_id,)))
        seen.add(("POST", "/regimen/items/{item_id}/edit"))
        assert read("SELECT name,active,notes FROM regimen_items635 WHERE id=?",
                    (item_id,)) == (updated, 1, "QA707 edited")

        schedule_fields = {
            "item_id": str(item_id), "cadence": "daily",
            "start_on": "2026-11-15", "amount": "1 capsule", "meal": "",
        }
        signed_write(page, base, token, "/regimen/schedules", schedule_fields,
                     lambda: read("SELECT COUNT(*) FROM regimen_schedules635 WHERE item_id=?",
                                  (item_id,)))
        seen.add(("POST", "/regimen/schedules"))
        schedule = read(
            "SELECT id,cadence,amount,active FROM regimen_schedules635 WHERE item_id=?",
            (item_id,),
        )
        assert schedule is not None and schedule[1:] == ("daily", "1 capsule", 1)
        schedule_id = schedule[0]

        route = f"/regimen/schedules/{schedule_id}/edit"
        signed_write(page, base, token, route,
                     {**schedule_fields, "amount": "2 capsules", "active": "yes"},
                     lambda: read("SELECT amount,active FROM regimen_schedules635 WHERE id=?",
                                  (schedule_id,)))
        seen.add(("POST", "/regimen/schedules/{schedule_id}/edit"))
        assert read("SELECT amount,active FROM regimen_schedules635 WHERE id=?",
                    (schedule_id,)) == ("2 capsules", 1)

        entry_fields = {
            "item_id": str(item_id), "schedule_id": str(schedule_id),
            "logged_at": "2026-11-17T08:30", "outcome": "taken",
            "amount": "2 capsules", "meal": "breakfast", "notes": "QA707 synthetic",
        }
        signed_write(page, base, token, "/regimen/entries", entry_fields,
                     lambda: read("SELECT COUNT(*) FROM regimen_entries635 WHERE item_id=?",
                                  (item_id,)))
        seen.add(("POST", "/regimen/entries"))
        entry = read(
            "SELECT id,outcome,amount,meal FROM regimen_entries635 WHERE item_id=?",
            (item_id,),
        )
        assert entry is not None and entry[1:] == ("taken", "2 capsules", "breakfast")
        entry_id = entry[0]

        route = f"/regimen/entries/{entry_id}/edit"
        signed_write(page, base, token, route,
                     {**entry_fields, "logged_at": "2026-11-17T09:30",
                      "notes": "QA707 corrected"},
                     lambda: read("SELECT notes,logged_at FROM regimen_entries635 WHERE id=?",
                                  (entry_id,)))
        seen.add(("POST", "/regimen/entries/{entry_id}/edit"))
        corrected = read("SELECT notes,logged_at FROM regimen_entries635 WHERE id=?",
                         (entry_id,))
        assert corrected is not None and corrected[0] == "QA707 corrected"
        assert str(corrected[1]).startswith("2026-11-17 09:30")

        route = f"/regimen/entries/{entry_id}/delete"
        signed_write(page, base, token, route, {},
                     lambda: read("SELECT COUNT(*) FROM regimen_entries635 WHERE id=?",
                                  (entry_id,)))
        seen.add(("POST", "/regimen/entries/{entry_id}/delete"))
        assert read("SELECT COUNT(*) FROM regimen_entries635 WHERE id=?",
                    (entry_id,)) == (0,)

        route = f"/regimen/schedules/{schedule_id}/stop"
        signed_write(page, base, token, route, {},
                     lambda: read("SELECT active FROM regimen_schedules635 WHERE id=?",
                                  (schedule_id,)))
        seen.add(("POST", "/regimen/schedules/{schedule_id}/stop"))
        assert read("SELECT active FROM regimen_schedules635 WHERE id=?",
                    (schedule_id,)) == (0,)

        route = f"/regimen/items/{item_id}/archive"
        signed_write(page, base, token, route, {},
                     lambda: read("SELECT active FROM regimen_items635 WHERE id=?",
                                  (item_id,)))
        seen.add(("POST", "/regimen/items/{item_id}/archive"))
        assert read("SELECT active FROM regimen_items635 WHERE id=?", (item_id,)) == (0,)

        assert seen == REGIMEN_ROUTES
        print("CSRF_707_REGIMEN_SIGNED_POSITIVE_ROUTES=9", flush=True)
    finally:
        context.close()


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_707_coa_catalog_three_valid_signed_persisted_lifecycles(browser, scheme):
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    context, page, token = browser_context(browser, base, "/coa-test-types")
    seen = set()
    try:
        native = page.locator('form[action="/coa-test-types"][method="post" i]')
        assert native.count() == 1
        assert native.locator('input[name="csrf_token"]').input_value() == token

        label = "QA707 Type " + scheme + " " + uuid4().hex[:12]
        fields = {"label": label, "group_name": "Specialized analysis"}
        signed_write(page, base, token, "/coa-test-types", fields,
                     lambda: read(
                         "SELECT COUNT(*) FROM coa_test_type_catalog652 WHERE label=?",
                         (label,),
                     ))
        seen.add(("POST", "/coa-test-types"))
        row = read(
            "SELECT id,label,group_name,active FROM coa_test_type_catalog652 WHERE label=?",
            (label,),
        )
        assert row is not None and row[1:] == (label, "Specialized analysis", 1)
        ident = row[0]

        updated = label + " revised"
        path = f"/coa-test-types/{ident}/edit"
        signed_write(page, base, token, path,
                     {"label": updated, "group_name": "Core analysis"},
                     lambda: read(
                         "SELECT label,group_name,active FROM coa_test_type_catalog652 WHERE id=?",
                         (ident,),
                     ))
        seen.add(("POST", "/coa-test-types/{type_id}/edit"))
        assert read(
            "SELECT label,group_name,active FROM coa_test_type_catalog652 WHERE id=?",
            (ident,),
        ) == (updated, "Core analysis", 1)

        path = f"/coa-test-types/{ident}/toggle"
        signed_write(page, base, token, path, {},
                     lambda: read("SELECT active FROM coa_test_type_catalog652 WHERE id=?",
                                  (ident,)))
        seen.add(("POST", "/coa-test-types/{type_id}/toggle"))
        assert read("SELECT active FROM coa_test_type_catalog652 WHERE id=?",
                    (ident,)) == (0,)
        assert seen == CATALOG_ROUTES
        print("CSRF_707_COA_TEST_CATALOG_SIGNED_POSITIVE_ROUTES=3", flush=True)
    finally:
        context.close()
