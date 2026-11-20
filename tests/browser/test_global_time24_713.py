"""Release 713: every Tracker time entry is HH:MM without native AM/PM UI.

Runs only on disposable, isolated, localhost strict-CSRF browser QA.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from playwright.sync_api import expect, sync_playwright

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
    and DATA.name == "data" and DATA.is_dir() and not DATA.is_symlink()
    and DATA.parent.parent == Path("/tmp").resolve()
    and re.fullmatch(r"tracker-browser-qa[.][A-Za-z0-9_]{8}", DATA.parent.name)
):
    raise RuntimeError("713 browser test refuses non-disposable strict QA")

pytestmark = pytest.mark.browser


def seed_time_entry_fixtures():
    """Only disposable browser QA data, making conditional time fields visible."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.models import RegimenItem
    from app.workout_models654 import WorkoutEquipment654

    db_path = (DATA / "tracker.db").resolve()
    assert db_path.is_file() and db_path.parent == DATA
    engine = create_engine("sqlite:///" + str(db_path))
    with Session(engine) as db:
        db.add(RegimenItem(
            kind="supplement", name="QA713 24h catalog " + uuid4().hex[:12],
            active=True,
        ))
        db.add(WorkoutEquipment654(
            gym="QA713 Gym", name="QA713 Machine " + uuid4().hex[:12],
            kind="selectorized",
        ))
        db.commit()
    engine.dispose()


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_713_all_native_time_fields_use_24hour_text_controls(scheme):
    seed_time_entry_fixtures()
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        try:
            page = context.new_page()
            stage = "PAGE_SETUP"
            for path in ("/doses", "/vitals", "/regimen", "/workouts/backfill", "/pk", "/mobile"):
                stage = "PAGE_" + path.strip("/").replace("/", "_").upper()
                stage += "_HTTP"
                response = page.goto(base + path, wait_until="networkidle")
                assert response is not None and response.status == 200, (path, response)
                stage = "PAGE_" + path.strip("/").replace("/", "_").upper() + "_FIELDS"
                originals = page.locator(
                    'input[type="datetime-local"], input[type="time"]'
                )
                if path == "/regimen" and originals.count() == 0:
                    stage = "PAGE_REGIMEN_FIXTURE"
                    item_form = page.locator('form[action="/regimen/items"]')
                    item_form.locator('[name="kind"]').select_option("supplement")
                    item_form.locator('[name="name"]').fill("QA time entry " + scheme)
                    item_form.get_by_role("button", name="Add catalog item").click()
                    expect(page.locator('input[name="at_time"]')).to_have_count(1)
                    stage = "PAGE_REGIMEN_FIELDS"
                count = originals.count()
                assert count > 0, ("No time fields present to verify", path)
                stage = "PAGE_" + path.strip("/").replace("/", "_").upper() + "_ENHANCED"
                for i in range(count):
                    native = originals.nth(i)
                    expect(native).to_have_attribute("data-tracker24h-enhanced", "true")
                    stage = "PAGE_" + path.strip("/").replace("/", "_").upper() + "_HIDDEN"
                    assert not native.is_visible(), (path, i)
                    stage = "PAGE_" + path.strip("/").replace("/", "_").upper() + "_ENHANCED"
                stage = "PAGE_" + path.strip("/").replace("/", "_").upper() + "_PROXYCOUNT"
                assert page.locator(".tracker-time24-input713").count() == count, path
                stage = "PAGE_" + path.strip("/").replace("/", "_").upper() + "_SCRIPT"
                assert "tracker-time24-global713.js?v=713" in page.content()

            stage = "PK_PROGRAMMATIC_SYNC"
            pk_response = page.goto(base + "/pk", wait_until="networkidle")
            assert pk_response is not None and pk_response.status == 200
            # PK's non-form datetime is enhanced, and programmatic changes
            # propagate without ever asking for AM or PM.
            page.locator('.pk-tab[data-pk-mode="custom"]').click()
            expect(page.locator("#whatIfCard")).to_be_visible()
            stage = "PK_FIELD"
            pk_start = page.locator("#wiStart")
            assert pk_start.count() == 1
            stage = "PK_ASSIGN"
            pk_start.evaluate("""el => {
              el.value='2026-11-20T19:37';
              el.dispatchEvent(new Event('change', {bubbles:true}));
            }""")
            label = page.locator("label:has(#wiStart)")
            clock = label.locator(".tracker-time24-input713")
            date = label.locator(".tracker-time24-date")
            stage = "PK_INITIAL_CLOCK"
            expect(clock).to_have_value("19:37")
            stage = "PK_INITIAL_DATE"
            expect(date).to_have_value("2026-11-20")
            stage = "PK_EDIT_CLOCK"
            clock.fill("22:09")
            stage = "PK_EDIT_NATIVE"
            expect(pk_start).to_have_value("2026-11-20T22:09")
            stage = "PK_INVALID_INPUT"
            clock.fill("29:09")
            stage = "PK_INVALID_NATIVE"
            expect(pk_start).to_have_value("")
            stage = "PK_INVALID_VALIDITY"
            assert clock.evaluate("el => !el.checkValidity()")
            stage = "PK_RECOVER_INPUT"
            clock.fill("00:05")
            stage = "PK_RECOVER_NATIVE"
            expect(pk_start).to_have_value("2026-11-20T00:05")

            stage = "DYNAMIC_CONTROL"
            # Dynamic controls (workout rows / HTMX forms) receive the same
            # enhancement, without adding a duplicate named POST field.
            page.evaluate("""() => {
              const label=document.createElement('label');
              label.textContent='QA dynamic time';
              const original=document.createElement('input');
              original.type='time';
              original.name='qa713_time';
              original.value='18:30';
              label.append(original);
              document.querySelector('main').append(label);
            }""")
            native = page.locator('input[name="qa713_time"]')
            expect(native).to_have_attribute("data-tracker24h-enhanced", "true")
            visible = page.locator("label:has([name='qa713_time']) .tracker-time24-input713")
            expect(visible).to_have_value("18:30")
            visible.fill("23:59")
            expect(native).to_have_value("23:59")
            visible.fill("24:00")
            expect(native).to_have_value("")
            assert visible.evaluate("el => !el.checkValidity()")
            print("RELEASE_713_24H_BROWSER=PASSED_" + scheme, flush=True)
        except Exception:
            print("TARGETED_713_TIME24_" + stage + "=FAILED", flush=True)
            raise
        finally:
            context.close()
            browser.close()
