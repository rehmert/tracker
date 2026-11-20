"""Release 713: every Tracker time entry is HH:MM without native AM/PM UI.

Runs only on disposable, isolated, localhost strict-CSRF browser QA.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
from urllib.parse import urlsplit

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


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_713_all_native_time_fields_use_24hour_text_controls(scheme):
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        try:
            page = context.new_page()
            for path in ("/doses", "/vitals", "/regimen", "/workouts/backfill", "/pk", "/mobile"):
                response = page.goto(base + path, wait_until="networkidle")
                assert response is not None and response.status == 200, (path, response)
                originals = page.locator(
                    'input[type="datetime-local"], input[type="time"]'
                )
                count = originals.count()
                assert count > 0, ("No time fields present to verify", path)
                for i in range(count):
                    native = originals.nth(i)
                    expect(native).to_have_attribute("data-tracker24h-enhanced", "true")
                    assert not native.is_visible(), (path, i)
                assert page.locator(".tracker-time24-input713").count() == count, path
                assert "tracker-time24-global713.js?v=713" in page.content()

            # PK's non-form datetime is enhanced, and programmatic changes
            # propagate without ever asking for AM or PM.
            pk_start = page.locator("#wiStart")
            assert pk_start.count() == 1
            pk_start.evaluate("""el => {
              el.value='2026-11-20T19:37';
              el.dispatchEvent(new Event('change', {bubbles:true}));
            }""")
            label = page.locator("label:has(#wiStart)")
            clock = label.locator(".tracker-time24-input713")
            date = label.locator(".tracker-time24-date")
            expect(clock).to_have_value("19:37")
            expect(date).to_have_value("2026-11-20")
            clock.fill("22:09")
            expect(pk_start).to_have_value("2026-11-20T22:09")
            clock.fill("29:09")
            expect(pk_start).to_have_value("")
            assert clock.evaluate("el => !el.checkValidity()")
            clock.fill("00:05")
            expect(pk_start).to_have_value("2026-11-20T00:05")

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
        finally:
            context.close()
            browser.close()
