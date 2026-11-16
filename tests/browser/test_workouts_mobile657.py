"""Release 657 phone-sized Chromium E2E QA on a disposable isolated DEV server.

Never point at live Tracker or PROD. Browser writes are allowed only against
the runner-created /tmp/tracker-mobileqa657.*/data private SQLite database.
This emulates Android/iPhone viewports; it is not a real camera hardware test.
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote, urlsplit
import uuid

import pytest
from playwright.sync_api import expect, sync_playwright

URL = os.environ.get("TRACKER_TEST_HTTPS_URL", "").rstrip("/")
DATA = Path(os.environ.get("TRACKER_BROWSER_QA_DATA_DIR", "/")).resolve()
parts = urlsplit(URL)
if not (
    os.environ.get("TRACKER_TEST_ISOLATED") == "1"
    and parts.scheme == "https"
    and parts.hostname == "127.0.0.1"
    and parts.port is not None
    and parts.port >= 1024
    and DATA.is_dir()
    and DATA.name == "data"
    and DATA.parent.name.startswith("tracker-mobileqa657.")
    and DATA.parent.parent == Path("/tmp")
):
    raise RuntimeError("Refusing mobile QA writes outside disposable loopback data")


@pytest.mark.parametrize(
    "device,width,height",
    [("Android", 393, 852), ("iPhone", 390, 844)],
)
def test_mobile_workout_real_browser_flow(device, width, height):
    suffix = uuid.uuid4().hex[:8]
    names = [f"QA657 {device} Chest {suffix}", f"QA657 {device} Row {suffix}"]
    routine_name = f"QA657 {device} Routine {suffix}"
    qr = f"https://example.invalid/nautilus/{suffix}?model=7&key=abc"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": width, "height": height},
            screen={"width": width, "height": height},
            device_scale_factor=3, is_mobile=True, has_touch=True,
            ignore_https_errors=True,
        )
        tab = context.new_page()
        errors = []
        tab.on("pageerror", lambda error: errors.append(str(error)))

        def no_external_requests(route):
            if urlsplit(route.request.url).hostname != "127.0.0.1":
                route.abort()
            else:
                route.continue_()

        tab.route("**/*", no_external_requests)

        def load(path):
            response = tab.goto(URL + path, wait_until="domcontentloaded")
            assert response is not None and response.status == 200, (
                path, response.status if response else None,
                tab.locator("body").inner_text()[:200],
            )
            return response

        def submit(form, button):
            form.get_by_role("button", name=button).click()
            tab.wait_for_load_state("domcontentloaded")
            assert urlsplit(tab.url).hostname == "127.0.0.1", tab.url

        try:
            load("/workouts")
            expect(tab.get_by_role("heading", name="Workouts", exact=True)).to_be_visible()
            expect(tab.locator('input[name="code"]')).to_be_visible()

            for i, name in enumerate(names):
                form = tab.locator('form[action="/workouts/equipment"]')
                form.locator('input[name="name"]').fill(name)
                form.locator('input[name="gym"]').fill("Mobile QA disposable gym")
                if i == 0:
                    form.locator('input[name="qr_value"]').fill(qr)
                else:
                    form.locator('input[name="qr_value"]').fill("")
                submit(form, "Add Equipment")
                assert "err=" not in tab.url, (device, tab.url)
                expect(tab.locator(".workout-machine654 summary strong").filter(
                    has_text=name
                )).to_have_count(1)

            ids = []
            for name in names:
                details = tab.locator(".workout-machine654").filter(
                    has=tab.locator("summary strong", has_text=name)
                )
                assert details.count() == 1
                ids.append(int(details.get_attribute("id").split("-")[-1]))

            # Exact-match QR lookup never opens the code's remote destination.
            load("/workouts/qr/scan?code=" + quote(qr, safe=""))
            assert f"machine={ids[0]}" in tab.url
            assert urlsplit(tab.url).hostname == "127.0.0.1"

            load("/workouts/routines")
            form = tab.locator('form[action="/workouts/routines"]')
            form.locator('input[name="name"]').fill(routine_name)
            submit(form, "Create Routine")
            routine_path = urlsplit(tab.url).path
            assert routine_path.startswith("/workouts/routines/"), routine_path
            for equipment_id in ids:
                form = tab.locator(f'form[action="{routine_path}/equipment"]')
                form.locator('select[name="equipment_id"]').select_option(str(equipment_id))
                submit(form, "Add to Routine")

            ordered = tab.locator("#routine-exercises655 .workout-routine-heading655 strong")
            assert ordered.all_inner_texts() == names
            submit(tab.locator(f'form[action="{routine_path}/start"]'), "Start Routine")
            assert f"machine={ids[0]}" in tab.url
            expect(tab.locator(".workout657-progress")).to_contain_text("0 of 2")

            first = tab.locator(f"#workout-machine-{ids[0]}")
            expect(first).to_have_attribute("open", "")
            first_form = first.locator('form[action="/workouts/sets"]')
            first_form.locator('input[name="weight_lb"]').fill("100")
            first_form.locator('input[name="reps"]').fill("12")
            first_form.locator('input[name="effort"]').fill("7")
            submit(first_form, "Save Set")
            expect(tab.locator(".workout657-progress")).to_contain_text("1 of 2")

            # A second set using native one-tap repeat.
            first = tab.locator(f"#workout-machine-{ids[0]}")
            submit(first.locator('form[action="/workouts/sets/repeat"]'), "Repeat Last Set")
            expect(tab.locator("#workout-sets657 .workout657-set")).to_have_count(2)

            # Correct the newest set. Preserve the original workout history.
            recorded = tab.locator("#workout-sets657 .workout657-set").first
            recorded.locator(".workout657-set-actions > summary").click()
            edit = recorded.locator('form[action$="/edit"]')
            edit.locator('input[name="weight_lb"]').fill("95.5")
            edit.locator('input[name="reps"]').fill("10")
            submit(edit, "Save Correction")
            assert "#workout-sets657" in tab.url
            expect(tab.locator("#workout-sets657")).to_contain_text("95.5 lb × 10 reps")

            recorded = tab.locator("#workout-sets657 .workout657-set").first
            recorded.locator(".workout657-set-actions > summary").click()
            removal = recorded.locator('form[action$="/delete"]')
            # Confirm is required in the browser and on the server.
            expect(removal.locator('input[name="confirm_delete"]')).not_to_be_checked()
            expect(removal.locator('input[name="confirm_delete"]')).to_have_attribute(
                "required", ""
            )
            removal.locator('input[name="confirm_delete"]').check()
            submit(removal, "Remove Set")
            expect(tab.locator("#workout-sets657 .workout657-set")).to_have_count(1)

            first = tab.locator(f"#workout-machine-{ids[0]}")
            first.locator(".workout657-next-link").click()
            tab.wait_for_load_state("domcontentloaded")
            assert f"machine={ids[1]}" in tab.url
            next_machine = tab.locator(f"#workout-machine-{ids[1]}")
            expect(next_machine).to_have_attribute("open", "")
            next_form = next_machine.locator('form[action="/workouts/sets"]')
            next_form.locator('input[name="weight_lb"]').fill("80")
            next_form.locator('input[name="reps"]').fill("10")
            submit(next_form, "Save Set")
            expect(tab.locator(".workout657-progress")).to_contain_text("2 of 2")

            submit(tab.locator('form[action="/workouts/finish"]'), "Finish Workout")
            expect(tab.locator(".workout-status654")).to_have_count(0)
            recent = tab.locator('a[href^="/workouts/sessions/"]').first
            recent.click()
            expect(tab.get_by_role("heading", name="Workout History")).to_be_visible()
            expect(tab.locator("body")).to_contain_text("100.0 lb")
            expect(tab.locator("body")).to_contain_text("80.0 lb")
            expect(tab.locator("body")).not_to_contain_text("95.5 lb")
            assert tab.locator('form[action*="/edit"]').count() == 0

            load(f"/workouts/equipment/{ids[0]}/progress")
            expect(tab.get_by_role("heading", name=f"{names[0]} — Progress")).to_be_visible()
            expect(tab.locator(".workout656-stats")).to_contain_text("1")
            expect(tab.locator(".workout656-stats")).to_contain_text("100.0 lb")

            unmapped = f"https://example.invalid/new/{suffix}?new=1&other=2"
            load("/workouts/qr/scan?code=" + quote(unmapped, safe=""))
            expect(tab.locator('input[name="qr_value"]').last).to_have_value(unmapped)
            expect(tab.locator(".workout656-mapping-message")).to_be_visible()

            assert not errors, (device, errors)
            print(f"WORKOUT_657_MOBILE_{device.upper()}=PASSED")
        finally:
            context.close()
            browser.close()
