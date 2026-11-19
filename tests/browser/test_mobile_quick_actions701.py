"""Release 701: isolated real-page mobile Log sheet navigation and tap targets.

This browser test is permitted only by the guarded preview with a private
loopback server and an empty disposable database. Never POST or save records.
"""
from urllib.parse import urlparse
import os

import pytest
from playwright.sync_api import expect, sync_playwright

URL = os.environ.get("TRACKER_TEST_URL", "")
pytestmark = pytest.mark.skipif(
    os.environ.get("TRACKER_TEST_ISOLATED") != "1"
    or not URL.startswith("http://127.0.0.1:"),
    reason="Release 701 browser test requires isolated localhost server",
)
ACTIONS = (
    ("/food#food-quick-log", "Food"),
    ("/doses#quick-dose-entry", "Dose"),
    ("/labs/new#lab-manual-entry", "Labs"),
    ("/workouts/quick", "Log Workout Set"),
    ("/regimen#reg635-today", "Log Supplements / Meds"),
    ("/quick-entry", "All actions"),
)
WIDTHS = (320, 390, 430, 760)
THEMES = ("light", "dark")
DENSITIES = ("compact", "balanced", "comfortable")


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("theme", THEMES)
def test_701_mobile_log_sheet_navigation_actions_and_forms(width, theme):
    posts = []
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            context = browser.new_context(
                viewport={"width": width, "height": 844},
                device_scale_factor=1,
                color_scheme=theme,
                reduced_motion="reduce",
            )
            def permit_local(route):
                dest = urlparse(route.request.url)
                if dest.scheme == "http" and dest.hostname == "127.0.0.1" and dest.netloc == urlparse(URL).netloc:
                    route.continue_()
                else:
                    route.abort()
            context.route("**/*", permit_local)
            page = context.new_page()
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.on("request", lambda request: posts.append(request.url)
                    if request.method.upper() != "GET" else None)
            response = page.goto(URL + "/mobile", wait_until="domcontentloaded")
            assert response is not None and response.status == 200
            dock = page.locator("#tracker-mobile-add528")
            overlay = page.locator("#tracker-mobile-quick528")
            choices = overlay.locator("[data-quick528-choices]")
            expect(dock).to_be_visible()
            expect(overlay).to_be_hidden()
            assert overlay.locator("[data-quick528-form]").count() == 3

            for density in DENSITIES:
                page.evaluate(
                    "(density) => { document.documentElement.dataset.density = density; }",
                    density,
                )
                dock.click()
                expect(overlay).to_be_visible()
                expect(dock).to_have_attribute("aria-expanded", "true")
                expect(choices).to_be_visible()
                expect(overlay.locator('.tracker-quick528-sheet[role="dialog"]')).to_be_visible()
                assert choices.locator("[data-quick528-choice]").count() == 3

                links = choices.locator("a[href]")
                assert links.count() == len(ACTIONS)
                assert links.evaluate_all(
                    "(els) => els.map(el => [el.getAttribute('href'), el.textContent.trim()])"
                ) == [list(action) for action in ACTIONS]

                for href, _ in ACTIONS:
                    link = choices.locator(f'a[href="{href}"]')
                    expect(link).to_be_visible()
                    area = link.bounding_box()
                    assert area is not None and area["height"] >= 44
                    assert area["width"] >= 44

                dims = page.evaluate("""() => {
                    const sheet = document.querySelector('.tracker-quick528-sheet');
                    const rect = sheet.getBoundingClientRect();
                    return {
                        left: rect.left, right: rect.right,
                        width: innerWidth,
                        contentOverflow: sheet.scrollWidth > sheet.clientWidth + 1,
                    };
                }""")
                assert dims["left"] >= -1, (width, theme, density, dims)
                assert dims["right"] <= dims["width"] + 1, (width, theme, density, dims)
                assert not dims["contentOverflow"], (width, theme, density, dims)

                # Existing embedded recording flows remain usable and do not
                # save anything until a form is actually submitted.
                choices.locator('[data-quick528-choice="weight"]').click()
                expect(overlay.locator('[data-quick528-form="weight"]')).to_be_visible()
                expect(overlay.locator('[data-quick528-form="bp"]')).to_be_hidden()
                expect(overlay.locator('[data-quick528-form="water"]')).to_be_hidden()
                overlay.locator("[data-quick528-back]").click()
                expect(choices).to_be_visible()
                page.keyboard.press("Escape")
                expect(overlay).to_be_hidden()
                expect(dock).to_have_attribute("aria-expanded", "false")

            assert posts == [], "Opening and navigating the Log sheet must not POST"
            assert not errors, errors
            context.close()
        finally:
            browser.close()


def test_701_desktop_log_link_retains_quick_entry_fallback():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": 1024, "height": 800})
            page.route("**/*", lambda route: route.continue_()
                       if urlparse(route.request.url).netloc == urlparse(URL).netloc
                       else route.abort())
            response = page.goto(URL + "/mobile", wait_until="domcontentloaded")
            assert response is not None and response.status == 200
            dock = page.locator("#tracker-mobile-add528")
            expect(page.locator("#tracker-mobile-quick528")).to_be_hidden()
            expect(dock).to_have_attribute("href", "/quick-entry")
            # The dock is mobile-only; desktop users retain existing
            # page/toolbar navigation without a new modal.
            page.evaluate("() => document.querySelector('#tracker-mobile-add528').click()")
            expect(page).to_have_url(URL + "/quick-entry")
        finally:
            browser.close()
