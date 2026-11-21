"""Release 717: signed mobile Chromium edit/remove of a completed workout.

Runs only against an isolated strict-CSRF QA server, on HTTP and HTTPS.
"""
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
    raise RuntimeError("717 browser test refuses a non-disposable strict QA service")

pytestmark = pytest.mark.browser


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_717_edit_finished_workout_and_remove_extra_set_on_phone(scheme):
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    name = "QA717 Row " + uuid4().hex[:12]
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
            new_machine = page.locator("#workout-add-equipment656 form")
            new_machine.locator('input[name="name"]').fill(name)
            new_machine.locator('input[name="gym"]').fill("QA717 Gym")
            with page.expect_response(lambda r:
                    r.request.method == "POST" and
                    urlsplit(r.url).path == "/workouts/equipment") as pending:
                new_machine.get_by_role("button", name="Add Equipment").click()
            assert pending.value.status == 303

            page.goto(base + "/workouts/quick", wait_until="networkidle")
            page.get_by_role("button", name="Start Free Workout").click()
            page.wait_for_load_state("networkidle")
            sid = page.locator("#workout659-root").get_attribute("data-session-id")
            assert sid and sid.isdecimal()
            choice = page.locator("#workout659-machine-select")
            machine_option = choice.locator("option").filter(has_text=name)
            assert machine_option.count() == 1
            equipment_id = machine_option.get_attribute("value")
            assert equipment_id and equipment_id.isdecimal()
            page.goto(base + f"/workouts/quick?machine={equipment_id}", wait_until="networkidle")

            for _ in range(2):
                logging = page.locator("#workout659-log-form")
                logging.locator('input[name="weight_lb"]').fill("95")
                logging.locator('input[name="reps"]').fill("10")
                with page.expect_response(lambda r:
                        r.request.method == "POST" and
                        urlsplit(r.url).path == "/workouts/quick/sets") as recorded:
                    logging.get_by_role("button", name="Save Set").click()
                assert recorded.value.status == 303
                page.wait_for_load_state("networkidle")

            finish = page.locator('form[action="/workouts/quick/finish"]')
            finish.locator('button[formaction="/workouts/finish-review"]').click()
            page.wait_for_load_state("networkidle")
            assert urlsplit(page.url).path == f"/workouts/sessions/{sid}/review"
            expect(page.locator('.workout663-totals > div').nth(1).locator("strong")).to_have_text("2")

            # Starting from Workouts, the completed-session edit link is direct.
            page.goto(base + "/workouts", wait_until="networkidle")
            edit_link = page.locator(f'a[href="/workouts/sessions/{sid}/correct"]')
            expect(edit_link).to_be_visible()
            edit_link.click()
            page.wait_for_load_state("networkidle")
            assert urlsplit(page.url).path == f"/workouts/sessions/{sid}/correct"
            expect(page.locator(".workout717-set")).to_have_count(2)
            extra = page.locator(".workout717-set").last
            extra.locator("details.workout717-actions > summary").click()
            form = extra.locator('form.workout717-remove-form')
            expect(form.locator('input[name="reason"]')).to_have_value("Extra set logged")
            form.locator('input[name="confirm_remove"]').check()
            with page.expect_response(lambda r:
                    r.request.method == "POST" and
                    re.fullmatch(rf"/workouts/sessions/{sid}/sets/\d+/remove",
                                 urlsplit(r.url).path)) as removal:
                form.get_by_role("button", name="Remove This Set").click()
            assert removal.value.status == 303
            page.wait_for_load_state("networkidle")
            expect(page.locator(".workout717-set")).to_have_count(1)
            expect(page.locator(".workout717-count")).to_contain_text("1 recorded set remaining")
            expect(page.locator(".workout717-removal-event")).to_have_count(1)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")

            page.goto(base + f"/workouts/sessions/{sid}/review", wait_until="networkidle")
            expect(page.locator('.workout663-totals > div').nth(1).locator("strong")).to_have_text("1")
            assert not errors, errors
        finally:
            context.close()
            browser.close()
