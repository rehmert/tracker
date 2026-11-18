"""Release 682: CSS source order and computed size of Overview workout shortcuts."""
from pathlib import Path
import os

import pytest
from jinja2 import Environment
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "app/static/css"


def test_682_overview_moves_workout_styles_to_head_before_681():
    dashboard = (ROOT / "app/templates/dashboard.html").read_text()
    base = (ROOT / "app/templates/base.html").read_text()
    link = 'tracker-workout-dashboard661.css?v=678'
    assert dashboard.count(link) == 1
    head = dashboard.split("{% block page_assets %}", 1)[1].split(
        "{% endblock %}", 1
    )[0]
    content = dashboard.split("{% block content %}", 1)[1]
    assert link in head
    assert link not in content
    assert base.index("{% block page_assets %}") < base.index(
        "tracker-workout-nav-density681.css?v=681"
    )
    Environment().parse(dashboard)


@pytest.mark.parametrize("width", [320, 390, 768, 1280])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_682_overview_shortcuts_are_content_fit_in_actual_css_order(width, scheme):
    original = (CSS / "tracker-workout-dashboard661.css").read_text()
    compact = (CSS / "tracker-workout-nav-density681.css").read_text()
    theme = ("--surface:#fff;--ink:#172b39;--teal:#1265ad"
             if scheme == "light" else
             "--surface:#182530;--ink:#f5f7fa;--teal:#78baff")
    html = f"""<!doctype html><html><head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>:root{{{theme}}}*{{box-sizing:border-box}}
        body{{margin:0;font:16px system-ui;background:var(--surface);color:var(--ink)}}
        main{{padding:12px}}</style></head><body>
        <main id="main-content"><section id="tracker-workout-dashboard661">
          <nav class="tracker-workout-actions661 tracker-workout-shortcuts678">
            <a href="#gym"><strong>Open Rapid Gym Mode</strong></a>
            <a href="#progress"><strong>Strength Progress</strong></a>
            <a href="#insights"><strong>28-Day Insights</strong></a>
            <a href="#calendar"><strong>Workout Calendar</strong></a>
            <a href="#all"><strong>All Workouts</strong></a>
          </nav></section></main></body></html>"""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": width, "height": 840},
                                    color_scheme=scheme)
            page.set_content(html)
            page.add_style_tag(content=original)
            page.add_style_tag(content=compact)
            nav = page.locator(".tracker-workout-shortcuts678")
            assert nav.evaluate("e => getComputedStyle(e).display") == "flex"
            controls = nav.locator(":scope > a")
            dims = controls.evaluate_all("""els => els.map(e => {
                const r=e.getBoundingClientRect();
                return {width:r.width,height:r.height};
            })""")
            assert all(x["height"] >= 44 for x in dims), dims
            assert all(x["width"] < 240 for x in dims), dims
            assert page.evaluate(
                "() => document.documentElement.scrollWidth <= innerWidth + 1"
            )
        finally:
            browser.close()
