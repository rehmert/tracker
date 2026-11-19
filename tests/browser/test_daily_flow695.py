"""Release 695: real Chromium UI checks against isolated candidate only."""
import os

import pytest

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect, sync_playwright

pytestmark = pytest.mark.skipif(
    os.environ.get("TRACKER_TEST_ISOLATED") != "1",
    reason="Release 695 browser tests require a disposable candidate server",
)

BASE_URL = os.environ.get("TRACKER_TEST_URL", "").rstrip("/")


@pytest.mark.parametrize("width", (320, 390, 768, 1280))
def test_695_today_actions_remain_accessible_without_horizontal_overflow(width):
    assert BASE_URL.startswith("http://127.0.0.1:")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": width, "height": 850})
            response = page.goto(BASE_URL + "/mobile", wait_until="networkidle")
            assert response is not None and response.status == 200

            actions = page.locator(".tracker-daily509 nav.tracker-daily-actions a")
            expect(actions).to_have_count(7)
            assert actions.all_text_contents() == [
                "Log Vitals", "Log Dose", "Log Food", "Log Water",
                "Log Workout Set", "Log Supplements / Meds", "All Actions",
            ]
            assert actions.evaluate_all(
                "els => els.every(a => a.getBoundingClientRect().height >= 44)"
            )
            links = actions.evaluate_all(
                "els => els.map(a => a.getAttribute('href'))"
            )
            assert links == [
                "#mobile-quick-vitals", "/doses#quick-dose-entry",
                "/food#food-quick-log", "/food#food-water", "/workouts/quick",
                "/regimen#reg635-today", "/quick-entry",
            ]
            assert page.locator(".ux674-actions").count() == 0
            expect(page.locator(".ux674-summary .ux695-summary-link")).to_have_count(3)
            position = page.evaluate("""() => {
                const y = s => document.querySelector(s).getBoundingClientRect().top + scrollY;
                return {
                    status: y('.tracker-daily-glance601'),
                    actions: y('.tracker-daily-actions'),
                    summary: y('.ux674-dashboard'),
                    overflow: document.documentElement.scrollWidth > innerWidth + 1
                };
            }""")
            assert position["status"] < position["actions"] < position["summary"]
            assert not position["overflow"], (width, position)
            if width <= 760:
                columns = page.locator(".tracker-daily-actions").evaluate(
                    "el => getComputedStyle(el).gridTemplateColumns.split(' ').length"
                )
                assert columns == 2
            page.locator('.tracker-daily-actions a[href="#mobile-quick-vitals"]').click()
            expect(page).to_have_url(BASE_URL + "/mobile#mobile-quick-vitals")
            expect(page.locator("#mobile-quick-vitals")).to_be_visible()
        finally:
            browser.close()


def test_695_quick_entry_search_finds_workout_and_regimen_actions():
    assert BASE_URL.startswith("http://127.0.0.1:")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            response = page.goto(BASE_URL + "/quick-entry", wait_until="networkidle")
            assert response is not None and response.status == 200
            search = page.locator("[data-quick-search]")
            daily = page.locator('button[data-quick-category="daily"]')
            daily.click()
            for keyword, href in (
                ("workout", "/workouts/quick"),
                ("supplement", "/regimen#reg635-today"),
            ):
                search.fill(keyword)
                results = page.locator('#tracker-quick-actions a[data-quick-action]:visible')
                expect(results).to_have_count(1)
                expect(results).to_have_attribute("href", href)
                assert results.first.get_attribute("data-quick-daily") is not None
            page.locator("[data-quick-reset]").click()
            expect(daily).to_have_attribute("aria-pressed", "false")
            expect(page.locator('button[data-quick-category="all"]')).to_have_attribute(
                "aria-pressed", "true"
            )
        finally:
            browser.close()
