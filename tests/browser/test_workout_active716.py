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
        "STARTED", "LINKS", "PANEL", "SELECTED", "POSTED",
        "HEADING", "PROGRESS", "WIDTH", "EXISTING", "NEW", "FINISHED",
        "SERVER_OK", "SERVER_FAIL", "PAGE_GYM", "PAGE_OTHER",
        "HEADING_SAME", "HEADING_FIRST", "HEADING_OTHER", "HEADING_MISSING",
        "ID_MATCH", "ID_OTHER", "HEADING_ROW", "HEADING_PRESS",
        "HEADING_QA", "HEADING_NOT_QA", "LABEL_SECOND", "LABEL_OTHER",
    }
    assert scheme in ("http", "https") and step in allowed
    with (DATA / "workout716-stages.txt").open("a", encoding="ascii") as stream:
        stream.write(f"TARGETED_716_{scheme.upper()}_{step}=PASSED\n")


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
            checkpoint716(scheme, "PANEL")
            choose = panel.locator('form[action="/workouts/quick/machines"]')
            choose.locator('select[name="equipment_id"]').select_option(label=second + " · QA716 Gym")
            chosen_id = choose.locator('select[name="equipment_id"]').input_value()
            assert chosen_id.isdecimal()
            checkpoint716(scheme, "SELECTED")
            with page.expect_response(
                lambda r: r.request.method == "POST"
                and urlsplit(r.url).path == "/workouts/quick/machines"
            ) as pending:
                choose.get_by_role("button", name="Add & Open").click()
            assert pending.value.status == 303
            location = pending.value.headers.get("location", "")
            assert location.startswith(f"/workouts/quick?machine={chosen_id}")
            assert "err=" not in location
            page.wait_for_url(re.compile(
                re.escape(base) + r"/workouts/quick\?machine=" +
                re.escape(chosen_id) + r"(?:&.*)?$"
            ))
            page.wait_for_load_state("networkidle")
            checkpoint716(scheme, "POSTED")
            # Distinguish server render failure from a stale browser view
            # without recording user names, HTML, URLs or raw response content.
            server_get = page.request.get(base + location)
            checkpoint716(scheme, "SERVER_OK" if server_get.status == 200 else "SERVER_FAIL")
            title = page.locator("h1").first.inner_text() if page.locator("h1").count() else ""
            checkpoint716(scheme, "PAGE_GYM" if title.strip() == "Rapid Gym Mode" else "PAGE_OTHER")
            actual_selected = page.locator("#workout659-machine-select")
            checkpoint716(scheme, "ID_MATCH" if actual_selected.count() and
                          actual_selected.input_value() == chosen_id else "ID_OTHER")
            selected_option = page.locator(
                f'#workout659-machine-select option[value="{chosen_id}"]'
            )
            label = selected_option.inner_text() if selected_option.count() else ""
            checkpoint716(scheme, "LABEL_SECOND" if second in label else "LABEL_OTHER")
            heading = page.locator(".workout659-machine-heading h2")
            if heading.count() == 0:
                checkpoint716(scheme, "HEADING_MISSING")
            else:
                value = heading.inner_text().strip()
                checkpoint716(scheme, "HEADING_SAME" if value == second else
                              "HEADING_FIRST" if value == first else "HEADING_OTHER")
                checkpoint716(scheme, "HEADING_ROW" if value.endswith("-Row") else "HEADING_PRESS")
                checkpoint716(scheme, "HEADING_QA" if value.startswith("QA716-") else "HEADING_NOT_QA")
            expect(heading).to_have_text(second)
            checkpoint716(scheme, "HEADING")
            expect(page.locator(".workout659-progress")).to_contain_text("0 of 2 exercises logged")
            checkpoint716(scheme, "PROGRESS")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            checkpoint716(scheme, "WIDTH")
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
