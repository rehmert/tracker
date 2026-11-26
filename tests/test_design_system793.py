"""Release 793: canonical navigation, theme and responsive shell."""
from pathlib import Path
import os

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright, expect

from app.main import app
from app.navigation import NAVIGATION, current_navigation, directory_groups
from tests.test_calendar_action_buttons787 import rendered

ROOT = Path(__file__).resolve().parents[1]


def test_registry_has_unique_routes_and_specific_active_destination():
    rows = [row for _, _, links in NAVIGATION for row in links]
    paths = [row[0] for row in rows]
    assert len(paths) == len(set(paths)) == 56
    assert len(NAVIGATION) == 7
    assert len([row for row in rows if row[2]]) == 18
    assert current_navigation("/vials/4") == "/vials"
    assert current_navigation("/reports/trends") == "/reports"
    assert current_navigation("/vials-other") is None
    assert current_navigation("/integrations/google-tasks") == "/integrations/google-tasks"
    assert {href for _, links in directory_groups() for _, href in links} == set(paths) | {"/"}
    with TestClient(app) as client:
        for path in ("/", "/mobile", "/protocols", "/vials", "/workflow-hub", "/integrations/google-tasks"):
            response = client.get(path)
            assert response.status_code == 200, path
            assert response.text.count('tracker-design-system793.css?v=793') == 1
            assert 'tracker-brand-refresh.css?v=34.28' not in response.text
            assert 'tracker-headings531.css?v=531' not in response.text
            for href in paths:
                assert f'data-nav-key="{href}"' in response.text


@pytest.mark.parametrize("width,theme,density", [
    (320,"dark","compact"), (390,"light","balanced"), (430,"dark","compact"),
    (768,"light","balanced"), (1024,"dark","compact"),
    (1440,"light","balanced"), (1920,"dark","compact"),
])
def test_rendered_theme_and_focused_navigation(width, theme, density):
    with TestClient(app) as client:
        markup, css = rendered(client, "/mobile")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None)
        try:
            page = browser.new_page(viewport={"width":width,"height":900}, color_scheme=theme)
            page.route("**/*", lambda route: route.abort())
            page.set_content(markup)
            page.add_style_tag(content=css)
            page.evaluate("""args => {
                document.documentElement.dataset.theme = args[0];
                document.documentElement.dataset.density = args[1];
            }""", [theme,density])
            page.add_script_tag(content=(ROOT/"app/static/tracker_focus.js").read_text())
            expect(page.locator('#nav-sortable li[data-nav-key="/mobile"]')).not_to_have_class("tracker-focus-hidden")
            expect(page.locator('#nav-sortable li[data-nav-key="/forecast-audit"]')).to_have_class("tracker-focus-hidden")
            assert page.locator('#nav-sortable li[data-nav-key="/forecast-audit"] a').count() == 1
            assert page.evaluate("""() => getComputedStyle(document.documentElement).getPropertyValue('--paper').trim()""") == ("#101820" if theme == "dark" else "#f2f5f7")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
            grid = page.locator("nav.tracker-quick-actions790")
            expect(grid).to_be_visible()
            assert grid.evaluate("""el => {
                const a=[...el.querySelectorAll(':scope > a')].map(x=>x.getBoundingClientRect());
                return a.filter(x=>Math.abs(x.y-a[0].y)<2).length >= 2;
            }""")
            if width <= 760:
                dock = page.locator(".tracker-mobile-dock")
                expect(dock).to_be_visible()
                assert dock.locator("svg").count() == 5
                assert dock.locator("a,button").evaluate_all("nodes=>nodes.every(n=>n.getBoundingClientRect().height>=44)")
            else:
                expect(page.locator(".tracker-mobile-dock")).to_be_hidden()
            page.locator("#tracker-focus-toggle").evaluate("el => {el.checked=false;el.dispatchEvent(new Event('change'))}")
            expect(page.locator('#nav-sortable li[data-nav-key="/forecast-audit"]')).not_to_have_class("tracker-focus-hidden")
        finally:
            browser.close()
