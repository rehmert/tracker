"""Release 718: signed mobile HTTP/HTTPS completed-session machine corrections."""
from __future__ import annotations

import os
import re
from pathlib import Path
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
    and DATA.is_dir() and DATA.name == "data" and not DATA.is_symlink()
    and DATA.parent.parent == Path("/tmp").resolve()
    and re.fullmatch(r"tracker-browser-qa[.][A-Za-z0-9_]{8}", DATA.parent.name)
):
    raise RuntimeError("718 browser test refuses a non-disposable strict QA service")

pytestmark = pytest.mark.browser


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_718_correct_whole_machine_and_single_set_in_completed_workout(scheme):
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    nonce = uuid4().hex[:12]
    wrong_name = "QA718 Wrong " + nonce
    right_name = "QA718 Right " + nonce
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            is_mobile=True, has_touch=True, device_scale_factor=2,
            ignore_https_errors=True,
        )
        try:
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(base + "/workouts", wait_until="networkidle")
            for name in (wrong_name, right_name):
                new = page.locator("#workout-add-equipment656 form")
                new.locator('input[name="name"]').fill(name)
                new.locator('input[name="gym"]').fill("QA718 Gym")
                with page.expect_response(lambda r:
                        r.request.method == "POST" and
                        urlsplit(r.url).path == "/workouts/equipment") as event:
                    new.get_by_role("button", name="Add Equipment").click()
                assert event.value.status == 303
                page.wait_for_load_state("networkidle")

            page.goto(base + "/workouts/quick", wait_until="networkidle")
            page.get_by_role("button", name="Start Free Workout").click()
            page.wait_for_load_state("networkidle")
            sid = page.locator("#workout659-root").get_attribute("data-session-id")
            assert sid and sid.isdecimal()
            option = page.locator("#workout659-machine-select option").filter(
                has_text=wrong_name
            )
            expect(option).to_have_count(1)
            machine_id = option.get_attribute("value")
            assert machine_id and machine_id.isdecimal()
            page.goto(base + f"/workouts/quick?machine={machine_id}",
                      wait_until="networkidle")
            for _ in range(3):
                form = page.locator("#workout659-log-form")
                form.locator('input[name="weight_lb"]').fill("85")
                form.locator('input[name="reps"]').fill("10")
                with page.expect_response(lambda r:
                        r.request.method == "POST" and
                        urlsplit(r.url).path == "/workouts/quick/sets") as logged:
                    form.get_by_role("button", name="Save Set").click()
                assert logged.value.status == 303
                page.wait_for_load_state("networkidle")
            page.locator('form[action="/workouts/quick/finish"]').locator(
                'button[formaction="/workouts/finish-review"]').click()
            page.wait_for_load_state("networkidle")
            expect(page.locator(".workout663-totals > div").first.locator("strong")).to_have_text("1")
            expect(page.locator(".workout663-totals > div").nth(1).locator("strong")).to_have_text("3")

            page.goto(base + "/workouts", wait_until="networkidle")
            page.locator(f'a[href="/workouts/sessions/{sid}/correct"]').click()
            page.wait_for_load_state("networkidle")
            group = page.locator(".workout718-bulk-machine").filter(has_text=wrong_name)
            expect(group).to_have_count(1)
            group.locator("summary").click()
            move = group.locator("form")
            move.locator('select[name="target_equipment_id"]').select_option(
                label=right_name + " · QA718 Gym"
            )
            move.locator('input[name="confirm_move"]').check()
            with page.expect_response(lambda r:
                    r.request.method == "POST" and
                    re.fullmatch(rf"/workouts/sessions/{sid}/machines/\d+/move-sets",
                                 urlsplit(r.url).path)) as moved:
                move.get_by_role("button", name="Move All 3 Sets").click()
            assert moved.value.status == 303
            page.wait_for_load_state("networkidle")
            expect(page.locator(".workout717-set")).to_have_count(3)
            expect(page.locator(".workout718-machine-event")).to_have_count(3)
            expect(page.locator(".workout717-set strong[data-no-title-case]").first).to_contain_text(right_name)

            one = page.locator(".workout717-set").first
            one.locator("details.workout717-actions > summary").click()
            change = one.locator("form.workout718-single-machine")
            change.locator('select[name="equipment_id"]').select_option(
                label=wrong_name + " · QA718 Gym"
            )
            with page.expect_response(lambda r:
                    r.request.method == "POST" and
                    re.fullmatch(rf"/workouts/sessions/{sid}/sets/\d+/machine",
                                 urlsplit(r.url).path)) as reassign:
                change.get_by_role("button", name="Save Correct Machine").click()
            assert reassign.value.status == 303
            page.wait_for_load_state("networkidle")
            expect(page.locator(".workout718-machine-event")).to_have_count(4)
            expect(page.locator(".workout717-set strong[data-no-title-case]").first).to_contain_text(wrong_name)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")

            page.goto(base + f"/workouts/sessions/{sid}/review", wait_until="networkidle")
            expect(page.locator(".workout663-totals > div").first.locator("strong")).to_have_text("2")
            expect(page.locator(".workout663-totals > div").nth(1).locator("strong")).to_have_text("3")
            assert "Completed" in page.locator(".workout663-heading").inner_text()
            assert not errors, errors
        finally:
            context.close()
            browser.close()
