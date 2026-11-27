"""Release 804: rendered visual hierarchy, phone controls and saved preferences."""
from pathlib import Path
import os

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright, expect

from app.main import app
from tests.test_calendar_action_buttons787 import rendered

ROOT = Path(__file__).resolve().parents[1]


def test_804_assets_and_existing_workflows():
    base = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")
    assert base.count("tracker-refinement804.css?v=804") == 1
    assert base.count("tracker-personalization804.js?v=804") == 1
    assert base.count('id="tracker-preference-summary804"') == 1
    assert base.count('id="tracker-advanced-navigation804"') == 1
    assert '<details class="tracker-preference-details804"' in base
    assert '<summary>Customize navigation</summary>' in base
    assert 'id="nav-category-preferences"' in base
    assert 'id="nav-visibility-preferences"' in base
    assert 'id="tracker-focus-toggle"' in base
    assert 'id="dashboard-customize"' in base
    for path in ("/", "/mobile", "/calendar", "/workouts/quick"):
        with TestClient(app) as client:
            response = client.get(path)
            assert response.status_code == 200, path
            html = response.text
            assert 'tracker-refinement804.css?v=804' in html
            assert 'tracker-personalization804.js?v=804' in html
            assert 'id="workspace-settings-toggle"' in html
            assert 'id="workspace-settings-panel"' in html
            assert 'href="/mobile"' in html
            assert 'href="/calendar"' in html


@pytest.mark.parametrize("width,theme,density", [
    (320, "dark", "compact"),
    (390, "light", "balanced"),
    (430, "dark", "balanced"),
    (1024, "light", "compact"),
])
def test_804_browser_mobile_and_personalization(width, theme, density):
    with TestClient(app) as client:
        markup, css = rendered(client, "/mobile")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": width, "height": 800},
                                    color_scheme=theme)
            page.route("**/*", lambda route: route.abort())
            page.set_content(markup)
            page.add_style_tag(content=css)
            page.evaluate("""args => {
                document.documentElement.dataset.theme = args[0];
                document.documentElement.dataset.density = args[1];
                document.documentElement.dataset.themePreference = args[0];
                document.querySelectorAll('[data-theme-choice]').forEach(el =>
                    el.setAttribute('aria-pressed', String(el.dataset.themeChoice === args[0])));
                document.querySelectorAll('[data-density-choice]').forEach(el =>
                    el.setAttribute('aria-pressed', String(el.dataset.densityChoice === args[1])));
            }""", [theme, density])
            page.add_script_tag(content=(ROOT / "app/static/tracker_focus.js").read_text())
            page.add_script_tag(content=(
                ROOT / "app/static/js/tracker-personalization804.js"
            ).read_text())
            print(f"\nTARGETED_804_W{width}_BROWSER_READY=PASSED", flush=True)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
            prefs = page.locator("#workspace-settings-panel")
            prefs.evaluate("(el) => { el.hidden = false; }")
            print(f"\nTARGETED_804_W{width}_PANEL_VISIBLE=PASSED", flush=True)
            expect(page.locator("#tracker-preference-summary804")).to_contain_text(
                "Compact" if density == "compact" else "Balanced"
            )
            expect(page.locator("#tracker-preference-summary804")).to_contain_text(
                "Dark" if theme == "dark" else "Light"
            )
            print(f"\nTARGETED_804_W{width}_SUMMARY=PASSED", flush=True)
            advanced = page.locator("#tracker-advanced-navigation804")
            assert not advanced.evaluate("(el) => el.open")
            advanced.evaluate("(el) => {el.open = true}")
            assert advanced.evaluate("(el) => el.open")
            print(f"\nTARGETED_804_W{width}_ADVANCED_OPEN=PASSED", flush=True)
            focus = page.locator("#tracker-focus-toggle")
            focus.evaluate("""el => {
                el.checked = false;
                el.dispatchEvent(new Event("change", {bubbles: true}));
            }""")
            expect(page.locator("#tracker-preference-summary804")).to_contain_text("All pages")
            print(f"\nTARGETED_804_W{width}_FOCUS_CHANGE=PASSED", flush=True)
            assert prefs.evaluate("(el) => getComputedStyle(el).overflowY") == "auto"
            assert prefs.evaluate("(el) => el.getBoundingClientRect().height <= innerHeight + 1")
            print(f"\nTARGETED_804_W{width}_PANEL_GEOMETRY=PASSED", flush=True)
            if width <= 760:
                dock_ok = page.locator(".tracker-mobile-dock a, .tracker-mobile-dock button").evaluate_all(
                    "nodes => nodes.every(el => el.getBoundingClientRect().height >= 44)"
                )
                print(f"\\nTARGETED_804_W{width}_DOCK={'PASSED' if dock_ok else 'FAILED'}", flush=True)
                assert dock_ok
                density_ok = page.locator("#workspace-settings-panel .density-options button").evaluate_all(
                    "nodes => nodes.every(el => el.getBoundingClientRect().height >= 44)"
                )
                print(f"\\nTARGETED_804_W{width}_DENSITY={'PASSED' if density_ok else 'FAILED'}", flush=True)
                assert density_ok
            else:
                expect(page.locator(".tracker-mobile-dock")).to_be_hidden()
            print(f"\nTARGETED_804_W{width}_RENDERED_COMPLETE=PASSED", flush=True)
        finally:
            browser.close()
