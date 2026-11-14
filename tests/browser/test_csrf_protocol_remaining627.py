"""Release 627: remaining protocol signed-workflow and CSRF-denial acceptance.

One disposable Chromium backend, real HTTP and HTTPS cookies and signing,
persisted database checks, no production data, no global enforcement changes.
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
    and HTTP.scheme == "http" and HTTPS.scheme == "https"
    and HTTP.hostname == HTTPS.hostname == "127.0.0.1"
    and HTTP.port not in (None, 8000)
    and HTTPS.port not in (None, 443, 8000, HTTP.port)
    and DATA.name == "data" and DATA.is_dir()
    and DATA.parent.parent == Path("/tmp").resolve()
    and re.fullmatch(r"tracker-browser-qa[.][A-Za-z0-9_]{8}", DATA.parent.name)
):
    raise RuntimeError("627 protocol acceptance requires isolated browser QA")

pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        chromium = playwright.chromium.launch(headless=True)
        yield chromium
        chromium.close()


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_627_remaining_protocol_signed_workflows_and_forged_denials(browser, scheme):
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    database = (DATA / "tracker.db").resolve()
    assert database.parent == DATA and database.is_file() and not database.is_symlink()

    def read(sql, params=()):
        with sqlite3.connect(database) as db:
            return db.execute(sql, params).fetchone()

    context = browser.new_context(ignore_https_errors=True)
    try:
        page = context.new_page()
        landing = page.goto(base + "/protocols", wait_until="networkidle")
        assert landing is not None and landing.status == 200
        token = page.evaluate("window.trackerCsrfToken?.() || ''")
        assert token.startswith("v1.")

        def signed(path, fields, expected=303):
            denied = page.request.post(base + path, form=fields, max_redirects=0)
            assert denied.status == 403, (scheme, path, "unsigned", denied.status)
            accepted = page.request.post(
                base + path, form=fields,
                headers={"X-Tracker-CSRF": token}, max_redirects=0,
            )
            assert accepted.status == expected, (scheme, path, accepted.status)
            assert accepted.headers.get("x-tracker-csrf-report") == "valid"
            return accepted

        name = "QA627 extra protocol " + scheme + " " + uuid4().hex[:10]
        response = signed("/protocols", {"name": name})
        location = urlsplit(response.headers["location"]).path
        assert re.fullmatch(r"/protocols/[0-9]+", location)
        pid = int(location.rsplit("/", 1)[-1])
        assert read("SELECT name FROM protocols WHERE id=?", (pid,)) == (name,)

        compound = read("SELECT id FROM compounds WHERE name='QA Alpha 511'")
        assert compound is not None
        row = {
            "compound_id": str(compound[0]), "amount": "1.5",
            "unit": "mg", "freq_count": "1", "freq_period": "day",
            "start_week": "1", "end_week": "",
        }

        # Stateless calculation must return a preview and persist no items.
        result = signed(location + "/calc", {"horizon_weeks": "12", **row}, 200)
        assert "text/html" in result.headers.get("content-type", "")
        assert read("SELECT count(*) FROM protocol_items WHERE protocol_id=?", (pid,)) == (0,)

        # Date-only update persists inclusive calendar bounds.
        signed(location + "/dates", {
            "start_date": "2026-11-15", "end_date": "2026-12-12",
            "duration_mode": "dates",
        })
        assert read(
            "SELECT start_date,end_date FROM protocols WHERE id=?", (pid,)
        ) == ("2026-11-15", "2026-12-12")

        # Save is a genuine signed mutation, not just a redirect.
        saved_name = name + " saved"
        signed(location + "/save", {
            "name": saved_name, "notes": "QA627 synthetic",
            "start_date": "2026-11-15", "end_date": "2026-12-12",
            "duration_mode": "dates", "horizon_weeks": "12", **row,
        })
        assert read(
            "SELECT name,notes FROM protocols WHERE id=?", (pid,)
        ) == (saved_name, "QA627 synthetic")
        assert read(
            "SELECT amount_value,amount_unit FROM protocol_items "
            "WHERE protocol_id=?", (pid,)
        ) == (1.5, "mg")

        # Save-and-add stores the submitted completed row without inventing
        # a second incomplete item. It redirects to a blank editor row.
        added = signed(location + "/add-item", {
            "name": saved_name, "notes": "QA627 add-item",
            "start_date": "2026-11-15", "end_date": "2026-12-12",
            "duration_mode": "dates", "horizon_weeks": "12", **row,
        })
        assert "add=1" in added.headers.get("location", "")
        assert read(
            "SELECT notes FROM protocols WHERE id=?", (pid,)
        ) == ("QA627 add-item",)
        assert read(
            "SELECT count(*) FROM protocol_items WHERE protocol_id=?", (pid,)
        ) == (1,)

        copied = signed(location + "/duplicate", {})
        copy_route = urlsplit(copied.headers["location"]).path
        assert re.fullmatch(r"/protocols/[0-9]+", copy_route)
        copy_id = int(copy_route.rsplit("/", 1)[-1])
        assert copy_id != pid
        assert read(
            "SELECT name,is_active FROM protocols WHERE id=?", (copy_id,)
        ) == (saved_name + " (copy)", 0)
        assert read(
            "SELECT count(*) FROM protocol_items WHERE protocol_id=?", (copy_id,)
        ) == (1,)

        # Clean up only the synthetic records from this test.
        signed(copy_route + "/delete", {})
        signed(location + "/delete", {})
        assert read("SELECT count(*) FROM protocols WHERE id IN (?,?)",
                    (pid, copy_id)) == (0,)
    finally:
        context.close()
