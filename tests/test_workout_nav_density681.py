"""Release 681: focused Chromium checks for content-sized workout navigation."""
from pathlib import Path
import os

import pytest
from jinja2 import Environment
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "app/static/css"
STYLE_675 = (CSS / "tracker-action-nav675.css").read_text()
STYLE_676 = (CSS / "tracker-shortcut-buttons676.css").read_text()
STYLE_661 = (CSS / "tracker-workout-dashboard661.css").read_text()
STYLE_681 = (CSS / "tracker-workout-nav-density681.css").read_text()


def test_681_scope_and_stylesheet_order():
    base = (ROOT / "app/templates/base.html").read_text()
    assert base.count("tracker-workout-nav-density681.css?v=681") == 1
    assert base.index("tracker-shortcut-buttons676.css?v=676") < base.index(
        "tracker-workout-nav-density681.css?v=681"
    )
    assert "#main-content nav.ux675-actions.ux675-gym-top" in STYLE_681
    assert "#tracker-workout-dashboard661 nav.tracker-workout-shortcuts678" in STYLE_681
    assert ".workout659-main-button" not in STYLE_681
    Environment().parse(base)


@pytest.mark.parametrize("width", [320, 390, 768, 1280])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_681_gym_navigation_fits_labels_without_collapsing_menu(width, theme):
    tokens = (
        "--surface:#fff;--ink:#223;--teal:#1265ad;--rule:#cbd5e1;--wash:#f1f5f9"
        if theme == "light" else
        "--surface:#1c2832;--ink:#f5f6f8;--teal:#86bbfb;--rule:#5b6a79;--wash:#304050"
    )
    html = f"""<!doctype html><html><head>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <style>:root{{{tokens}}}*{{box-sizing:border-box}}
      body{{margin:0;font:16px system-ui;background:var(--surface);color:var(--ink)}}
      #main-content{{padding:12px}}</style></head><body>
      <main id="main-content">
      <nav class="ux675-actions ux675-gym-top" aria-label="Workout navigation">
        <a href="/workouts">Workouts</a>
        <a href="/workouts/analytics">Progress</a>
        <details class="ux675-more"><summary>More</summary>
          <div><a href="/workouts/insights">Insights</a>
          <a href="/workouts/calendar">Calendar</a>
          <a href="/workouts/backfill">Log Past Workout</a></div>
        </details>
      </nav></main></body></html>"""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": width, "height": 844})
            page.set_content(html)
            page.add_style_tag(content=STYLE_675 + STYLE_676 + STYLE_681)
            nav = page.locator("nav.ux675-gym-top")
            assert nav.evaluate("e => getComputedStyle(e).display") == "flex"
            controls = page.locator("nav.ux675-gym-top > a")
            sizes = controls.evaluate_all(
                "es=>es.map(e=>({w:e.getBoundingClientRect().width,"
                "h:e.getBoundingClientRect().height}))"
            )
            assert all(44 <= x["h"] <= 80 for x in sizes), sizes
            assert all(x["w"] < 220 for x in sizes), sizes
            menu = page.locator(".ux675-more")
            links = menu.locator("div > a")
            assert not links.first.is_visible()
            assert menu.locator("div").evaluate(
                "e=>getComputedStyle(e).display"
            ) == "none"
            menu.locator("summary").click()
            assert links.first.is_visible()
            menu_sizes = links.evaluate_all(
                "es=>es.map(e=>({w:e.getBoundingClientRect().width,"
                "h:e.getBoundingClientRect().height}))"
            )
            assert all(x["w"] >= 44 and x["h"] >= 44 for x in menu_sizes)
            assert page.evaluate(
                "() => document.documentElement.scrollWidth <= innerWidth + 1"
            )
        finally:
            browser.close()


@pytest.mark.parametrize("width", [390, 1280])
def test_681_overview_workout_shortcuts_content_fit(width):
    html = """<!doctype html><html><head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>:root{--surface:#fff;--border:#cad4dd;--ink:#203040;--teal:#1265ad}
    *{box-sizing:border-box}body{margin:0;font:16px system-ui}
    #main-content{padding:12px}</style></head><body><main id="main-content">
    <section id="tracker-workout-dashboard661">
    <nav class="tracker-workout-actions661 tracker-workout-shortcuts678">
    <a href="/workouts/quick"><strong>Open Rapid Gym Mode</strong></a>
    <a href="/workouts/analytics"><strong>Strength Progress</strong></a>
    <a href="/workouts/insights"><strong>28-Day Insights</strong></a>
    <a href="/workouts"><strong>All Workouts</strong></a>
    </nav></section></main></body></html>"""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": width, "height": 844})
            page.set_content(html)
            page.add_style_tag(content=STYLE_661 + STYLE_681)
            nav = page.locator(".tracker-workout-shortcuts678")
            assert nav.evaluate("e=>getComputedStyle(e).display") == "flex"
            sizes = nav.locator("> a").evaluate_all(
                "es=>es.map(e=>({w:e.getBoundingClientRect().width,"
                "h:e.getBoundingClientRect().height}))"
            )
            assert all(44 <= x["h"] <= 80 for x in sizes), sizes
            if width == 1280:
                assert all(x["w"] < 240 for x in sizes), sizes
            assert page.evaluate(
                "()=>document.documentElement.scrollWidth<=innerWidth+1"
            )
        finally:
            browser.close()
