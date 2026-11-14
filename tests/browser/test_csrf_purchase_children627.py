"""Release 627: signed purchase child inventory lifecycles over isolated Chromium.

All database access is limited to tracker-browser-qa.* disposable SQLite.
Covers purchase-specific supply edits/deletion and BAC water inventory.
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
    raise RuntimeError("627 purchase coverage requires disposable strict QA")

pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        chromium = playwright.chromium.launch(headless=True)
        yield chromium
        chromium.close()


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_627_purchase_children_signed_create_edit_delete_and_forgery(browser, scheme):
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    database = (DATA / "tracker.db").resolve()
    assert database.is_file() and not database.is_symlink()
    assert database.parent == DATA

    def query(sql, parameters=()):
        with sqlite3.connect(database) as connection:
            return connection.execute(sql, parameters).fetchone()

    context = browser.new_context(ignore_https_errors=True)
    try:
        page = context.new_page()
        response = page.goto(base + "/purchases", wait_until="networkidle")
        assert response and response.status == 200
        token = page.evaluate("window.trackerCsrfToken?.() || ''")
        assert token.startswith("v1.")

        def write(path, data):
            forged = page.request.post(base + path, form=data, max_redirects=0)
            assert forged.status == 403, ("missing token", path, forged.status)
            accepted = page.request.post(
                base + path, form=data, max_redirects=0,
                headers={"X-Tracker-CSRF": token},
            )
            assert accepted.status == 303, ("signed", path, accepted.status)
            assert accepted.headers.get("x-tracker-csrf-report") == "valid"
            return accepted

        unique = uuid4().hex[:12]
        vendor = "QA627 purchase " + scheme + " " + unique
        write("/purchases", {"vendor": vendor, "purchased_on": "2026-11-14"})
        purchased = query("SELECT id FROM purchases WHERE vendor=?", (vendor,))
        assert purchased is not None
        pid = purchased[0]

        supply_name = "QA627 pills " + unique
        supply_path = f"/purchases/{pid}/supplies"
        write(supply_path, {
            "name": supply_name, "kind": "pill",
            "quantity": "8", "unit_price": "0.75",
        })
        supply = query(
            "SELECT id, purchased_qty FROM supplies WHERE purchase_id=? AND name=?",
            (pid, supply_name),
        )
        assert supply is not None and supply[1] == 8.0
        sid = supply[0]

        edited_name = supply_name + " updated"
        write(f"/purchases/{pid}/supplies/{sid}/edit", {
            "name": edited_name, "kind": "pill",
            "quantity": "10", "unit_price": "0.75",
        })
        assert query(
            "SELECT name,purchased_qty,remaining_qty FROM supplies WHERE id=?",
            (sid,),
        ) == (edited_name, 10.0, 10.0)
        write(f"/purchases/{pid}/supplies/{sid}/delete", {})
        assert query("SELECT COUNT(*) FROM supplies WHERE id=?", (sid,)) == (0,)

        water_name = "QA627 BAC " + unique
        write(f"/purchases/{pid}/bac-water", {
            "vial_count": "2", "ml_per_vial": "30",
            "name": water_name, "price_per_vial": "4.00",
        })
        water = query(
            "SELECT id,purchased_qty FROM supplies WHERE purchase_id=? AND name=?",
            (pid, water_name),
        )
        assert water is not None and water[1] == 60.0
        write(f"/purchases/{pid}/supplies/{water[0]}/delete", {})
        assert query("SELECT COUNT(*) FROM supplies WHERE id=?", (water[0],)) == (0,)

        # Reuse only the two synthetic compound fixtures established by the
        # full isolated Chromium runner; never query installed inventory.
        compound = query(
            "SELECT id FROM compounds WHERE name='QA Alpha 511' LIMIT 1"
        )
        assert compound is not None
        vial_label = "QA627 vial " + unique
        write(f"/purchases/{pid}/vials", {
            "compound_id": str(compound[0]),
            "quantity": "1", "content_value": "10",
            "content_unit": "mg", "form": "lyophilized",
            "unit_price": "0", "label": vial_label,
        })
        vial = query(
            "SELECT id,content_value FROM vials WHERE purchase_id=? AND label=?",
            (pid, vial_label),
        )
        assert vial is not None and vial[1] == 10.0
        write(f"/purchases/{pid}/vials/{vial[0]}/delete", {})
        assert query("SELECT COUNT(*) FROM vials WHERE id=?", (vial[0],)) == (0,)

        write(f"/purchases/{pid}/delete", {})
        assert query("SELECT COUNT(*) FROM purchases WHERE id=?", (pid,)) == (0,)
    finally:
        context.close()
