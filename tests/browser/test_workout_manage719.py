"""Release 719: strict signed Chromium proof for accidental session deletion.

Only disposable isolated test URLs and private QA data are accepted.
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
    raise RuntimeError("719 browser test refuses non-disposable QA")
pytestmark = pytest.mark.browser


def mark719(scheme: str, stage: str) -> None:
    # Fixed milestones only; no browser response content or personal data.
    with (DATA / "workout719-stages.txt").open("a", encoding="utf-8") as out:
        out.write(f"TARGETED_719_{scheme.upper()}_{stage}=PASSED\n")


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_719_delete_accidental_and_completed_sessions_from_phone(scheme):
    base = HTTP_URL if scheme == "http" else HTTPS_URL
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
            page.goto(base + "/", wait_until="networkidle")
            mark719(scheme, "HOME_LOADED")
            recent = page.locator("#tracker-workout-recent661")
            expect(recent).to_be_visible()
            assert not recent.evaluate("(el) => el.open")
            recent.locator("summary").click()
            assert recent.evaluate("(el) => el.open")
            mark719(scheme, "HOME_EXPANDED")

            page.goto(base + "/workouts", wait_until="networkidle")
            name = "QA719 Press " + uuid4().hex[:12]
            creation = page.locator("#workout-add-equipment656 form")
            creation.locator('input[name="name"]').fill(name)
            creation.locator('input[name="gym"]').fill("QA719 Gym")
            with page.expect_response(lambda r:
                    r.request.method == "POST" and
                    urlsplit(r.url).path == "/workouts/equipment") as posted_machine:
                creation.get_by_role("button", name="Add Equipment").click()
            assert posted_machine.value.status == 303
            mark719(scheme, "MACHINE")

            page.goto(base + "/workouts/quick", wait_until="networkidle")
            page.get_by_role("button", name="Start Free Workout").click()
            page.wait_for_load_state("networkidle")
            sid = page.locator("#workout659-root").get_attribute("data-session-id")
            assert sid and sid.isdecimal()
            mark719(scheme, "STARTED")
            delete = page.locator(f"form#workout719-delete-{sid}")
            expect(delete.get_by_role("button", name="Delete", exact=True)).to_be_visible()
            mark719(scheme, "DELETE_LINK")
            mark719(scheme, "ACTIVE_FORM")
            expect(delete.locator('input[name="reason"]')).to_have_value("Started by mistake")
            # Cancel is a genuine no-op; the session remains active.
            page.once("dialog", lambda dialog: dialog.dismiss())
            delete.get_by_role("button", name="Delete", exact=True).click()
            expect(delete).to_be_visible()
            assert urlsplit(page.url).path == "/workouts/quick"
            page.once("dialog", lambda dialog: dialog.accept())
            with page.expect_response(lambda r:
                    r.request.method == "POST" and
                    urlsplit(r.url).path == f"/workouts/sessions/{sid}/delete") as posted:
                delete.get_by_role("button", name="Delete", exact=True).click()
            assert posted.value.status == 303
            mark719(scheme, "ACTIVE_POST")
            page.wait_for_load_state("networkidle")
            assert urlsplit(page.url).path == "/workouts"
            assert page.locator(f"#workout719-delete-{sid}").count() == 0
            mark719(scheme, "ACTIVE_RETURN")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")

            # A finished workout with a recorded set is also deletable.
            page.goto(base + "/workouts/quick", wait_until="networkidle")
            page.get_by_role("button", name="Start Free Workout").click()
            page.wait_for_load_state("networkidle")
            other = page.locator("#workout659-root").get_attribute("data-session-id")
            assert other and other.isdecimal()
            mark719(scheme, "RESTARTED")
            machine_option = page.locator("#workout659-machine-select option").filter(
                has_text=name
            )
            expect(machine_option).to_have_count(1)
            eid = machine_option.get_attribute("value")
            assert eid and eid.isdecimal()
            page.goto(base + f"/workouts/quick?machine={eid}", wait_until="networkidle")
            sets = page.locator("#workout659-log-form")
            sets.locator('input[name="weight_lb"]').fill("85")
            sets.locator('input[name="reps"]').fill("10")
            with page.expect_response(lambda r:
                    r.request.method == "POST" and
                    urlsplit(r.url).path == "/workouts/quick/sets") as logged:
                sets.get_by_role("button", name="Save Set").click()
            assert logged.value.status == 303
            mark719(scheme, "LOGGED")
            page.wait_for_load_state("networkidle")
            page.locator('form[action="/workouts/quick/finish"]').locator(
                'button[formaction="/workouts/finish-review"]').click()
            page.wait_for_load_state("networkidle")
            assert urlsplit(page.url).path == f"/workouts/sessions/{other}/review"
            mark719(scheme, "FINISHED")
            page.goto(base + "/workouts", wait_until="networkidle")
            # Delete is immediately next to Edit Workout, not buried in a disclosure.
            history = page.locator(
                f'.workout717-history-row:has(a[href="/workouts/sessions/{other}/review"])'
            )
            actions = history.locator(".workout720-row-actions")
            expect(actions.get_by_role("link", name="Edit Workout")).to_be_visible()
            deletion = actions.locator(f"form#workout719-delete-{other}")
            expect(deletion.get_by_role("button", name="Delete", exact=True)).to_be_visible()
            assert history.locator("details.workout719-delete").count() == 0
            mark719(scheme, "FINISHED_FORM")
            page.once("dialog", lambda dialog: dialog.dismiss())
            deletion.get_by_role("button", name="Delete", exact=True).click()
            expect(actions.get_by_role("link", name="Edit Workout")).to_be_visible()
            page.once("dialog", lambda dialog: dialog.accept())
            with page.expect_response(lambda r:
                    r.request.method == "POST" and
                    urlsplit(r.url).path == f"/workouts/sessions/{other}/delete") as done:
                deletion.get_by_role("button", name="Delete", exact=True).click()
            assert done.value.status == 303
            mark719(scheme, "FINISHED_POST")
            page.wait_for_load_state("networkidle")
            assert urlsplit(page.url).path == "/workouts"
            page.goto(base + "/", wait_until="networkidle")
            recent = page.locator("#tracker-workout-recent661")
            assert not recent.evaluate("(el) => el.open")
            recent.locator("summary").click()
            assert page.locator(
                f'#tracker-workout-recent661 a[href="/workouts/sessions/{other}"]'
            ).count() == 0
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            mark719(scheme, "END")
        finally:
            context.close()
            browser.close()
