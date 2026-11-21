"""Release 716: real signed, mobile Chromium workout editing and machine insertion.

Runs ONLY on the disposable strict-CSRF browser-QA service, HTTP and HTTPS.
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
    and DATA.is_dir() and DATA.name == "data" and not DATA.is_symlink()
    and DATA.parent.parent == Path("/tmp").resolve()
    and re.fullmatch(r"tracker-browser-qa[.][A-Za-z0-9_]{8}", DATA.parent.name)
):
    raise RuntimeError("716 browser test refuses non-disposable strict QA")

pytestmark = pytest.mark.browser


def checkpoint716(scheme: str, step: str) -> None:
    """Record only predefined, non-sensitive steps in disposable browser QA."""
    allowed = {
        "MACHINE_ONE", "CATALOG", "ROUTINE_CREATED", "ROUTINE_READY",
        "STARTED", "LINKS", "EXISTING", "NEW", "FINISHED",
    }
    assert scheme in ("http", "https") and step in allowed
    with (DATA / "workout716-stages.txt").open("a", encoding="ascii") as stream:
        stream.write(f"TARGETED_716_{scheme.upper()}_{step}=PASSED\\n")


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_716_active_routine_machine_add_and_new_machine_on_phone(scheme):
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    unique = uuid4().hex[:10]
    first, second, third = (
        f"QA716-{scheme}-{unique}-{suffix}"
        for suffix in ("Press", "Row", "Curl")
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            ignore_https_errors=True, viewport={"width": 390, "height": 844},
            is_mobile=True, has_touch=True, device_scale_factor=2,
        )
        try:
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            # Create catalog equipment through the real, signed form.
            for name in (first, second):
                page.goto(base + "/workouts", wait_until="networkidle")
                form = page.locator("#workout-add-equipment656 form")
                form.locator('input[name="name"]').fill(name)
                form.locator('input[name="gym"]').fill("QA716 Gym")
                with page.expect_response(
                    lambda r: r.request.method == "POST"
                    and urlsplit(r.url).path == "/workouts/equipment"
                ) as pending:
                    form.get_by_role("button", name="Add Equipment").click()
                assert pending.value.status == 303
                checkpoint716(scheme, "MACHINE_ONE" if name == first else "CATALOG")

            # A saved routine initially has only the Press.
            page.goto(base + "/workouts/routines", wait_until="networkidle")
            create = page.locator('form[action="/workouts/routines"]')
            create.locator('input[name="name"]').fill("QA716 routine " + unique)
            create.get_by_role("button", name="Create Routine").click()
            page.wait_for_url(re.compile(re.escape(base) + r"/workouts/routines/\d+(?:[?].*)?$"))
            routine_path = urlsplit(page.url).path
            checkpoint716(scheme, "ROUTINE_CREATED")
            add = page.locator('form[action="' + routine_path + '/equipment"]')
            add.locator('select[name="equipment_id"]').select_option(label=first + " — QA716 Gym")
            add.get_by_role("button", name="Add to Routine").click()
            page.wait_for_load_state("networkidle")
            checkpoint716(scheme, "ROUTINE_READY")
            page.locator('form[action="' + routine_path + '/start"]').get_by_role(
                "button", name="Start Routine"
            ).click()
            page.wait_for_load_state("networkidle")
            checkpoint716(scheme, "STARTED")

            # The active workout exposes both edit tools and in-place add.
            page.goto(base + "/workouts/quick", wait_until="networkidle")
            assert page.locator('a[href="/workouts#workout-sets657"]').count() == 1
            assert page.locator(
                'a[href="' + routine_path + '#routine-exercises655"]'
            ).count() == 1
            checkpoint716(scheme, "LINKS")
            panel = page.locator("#workout716-add-machine")
            expect(panel).not_to_have_attribute("open", "")
            panel.locator("summary").first.click()
            choose = panel.locator('form[action="/workouts/quick/machines"]')
            choose.locator('select[name="equipment_id"]').select_option(label=second + " · QA716 Gym")
            with page.expect_response(
                lambda r: r.request.method == "POST"
                and urlsplit(r.url).path == "/workouts/quick/machines"
            ) as pending:
                choose.get_by_role("button", name="Add & Open").click()
            assert pending.value.status == 303
            page.wait_for_load_state("networkidle")
            assert page.locator(".workout659-machine-heading h2").inner_text() == second
            expect(page.locator(".workout659-progress")).to_contain_text("0 of 2 exercises logged")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            checkpoint716(scheme, "EXISTING")

            # A new machine can also be cataloged directly during this session.
            panel = page.locator("#workout716-add-machine")
            panel.locator("summary").first.click()
            new = panel.locator(".workout716-new")
            new.locator("summary").click()
            form = new.locator('form[action="/workouts/quick/machines/new"]')
            form.locator('input[name="name"]').fill(third)
            form.locator('input[name="gym"]').fill("QA716 Gym")
            form.locator('input[name="manufacturer"]').fill("Nautilus")
            with page.expect_response(
                lambda r: r.request.method == "POST"
                and urlsplit(r.url).path == "/workouts/quick/machines/new"
            ) as pending:
                form.get_by_role("button", name="Create & Open Machine").click()
            assert pending.value.status == 303
            page.wait_for_load_state("networkidle")
            expect(page.locator(".workout659-machine-heading h2")).to_have_text(third)
            expect(page.locator(".workout659-progress")).to_contain_text("0 of 3 exercises logged")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            checkpoint716(scheme, "NEW")
            # Clear the active session so HTTP and HTTPS witnesses are isolated.
            finish_form = page.locator('form[action="/workouts/quick/finish"]')
            finish_form.locator("summary").click()
            finish_form.get_by_role("button", name="Finish Workout", exact=True).click()
            page.wait_for_load_state("networkidle")
            checkpoint716(scheme, "FINISHED")
        finally:
            context.close()
            browser.close()
