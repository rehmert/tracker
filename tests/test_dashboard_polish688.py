"""Release 688: dashboard chrome, shortcuts, customization and workout density."""
from pathlib import Path
import os
import re
from types import SimpleNamespace

import pytest
from jinja2 import Environment
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

BASE = read("app/templates/base.html")
DASH = read("app/templates/dashboard.html")
WORKOUT = read("app/templates/_workout_dashboard661.html")
CSS688 = read("app/static/css/tracker-dashboard-polish688.css")
DAILY = read("app/static/css/tracker-daily-flow559.css")
WORKOUT_CSS = read("app/static/css/tracker-workout-dashboard661.css")
STYLE_FILES = [
    "app/static/app.css",
    "app/static/css/tracker-page-navigation.css",
    "app/static/css/tracker-layout-density685.css",
    "app/static/css/tracker-compact-aggressive686.css",
    "app/static/css/tracker-shortcuts-toolbar687.css",
    "app/static/css/tracker-dashboard-polish688.css",
    "app/static/css/tracker-daily-flow559.css",
]
SCRIPTS = [
    "app/static/workspace_toolbar.js",
    "app/static/personalize.js",
    "app/static/js/tracker-page-navigation.js",
    "app/static/js/tracker-section-deep-links.js",
]
EXPECTED = [
    ("Calendar", "/calendar"),
    ("Dose Workspace", "/dose-workspace"),
    ("Inventory", "/replenishment-review"),
    ("Lab Results", "/labs"),
    ("Log Dose", "/doses#quick-dose-entry"),
    ("Log Food", "/food#food-quick-log"),
    ("Log Vitals", "/mobile#mobile-quick-vitals"),
    ("Log Water", "/food#food-water"),
    ("Progress", "/health-insights"),
    ("Today", "/mobile"),
    ("Vial Inventory", "/vials"),
]


def shortcut_html():
    start = DASH.index('<section class="tracker-daily-flow559"')
    end = DASH.index("</section>", start) + len("</section>")
    return DASH[start:end]


def toolbar_html(path="/"):
    start = BASE.index('<div class="workspace-toolbar"')
    end = BASE.index('<nav class="ux-breadcrumbs"', start)
    template = BASE[start:end]
    return Environment(autoescape=True).from_string(template).render(
        path=path, tracker_session_login_enabled=lambda: True,
    )


def workout_html():
    jinja = Environment(autoescape=True)
    jinja.filters["dt"] = lambda value: str(value)
    values = SimpleNamespace(
        in_progress=False,
        sessions7=0, days7=0, sessions28=0,
        days28=0, sets28=0, reps28=0, recent=[],
    )
    return jinja.from_string(WORKOUT).render(workout_summary=values)


def test_688_source_and_template_contract():
    assert BASE.count("/static/css/tracker-dashboard-polish688.css?v=688") == 1
    assert BASE.index("tracker-dashboard-polish688.css?v=688") > BASE.index(
        "tracker-shortcuts-toolbar687.css?v=687"
    )
    assert 'id="dashboard-customize"' not in DASH
    assert BASE.count('id="dashboard-customize"') == 1
    assert BASE.count('id="dashboard-customize-panel"') == 1
    assert "{% if path == '/' %}" in BASE
    assert '<div class="dashboard-personalize">' not in DASH
    assert "Open Rapid Gym Mode" not in WORKOUT
    assert "'Rapid Gym Mode'" in WORKOUT
    links = re.findall(
        r'<a href="([^"]+)"><strong>([^<]+)</strong></a>',
        shortcut_html(),
    )
    assert [(label, url) for url, label in links] == EXPECTED
    assert "<span>" not in shortcut_html()
    assert "display: none" not in CSS688
    assert "font-size: 0" not in CSS688


def document():
    return (
        '<!doctype html><html data-density="compact"><head>'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>*{box-sizing:border-box}body{margin:0}'
        '#main-content{padding:8px;min-width:0;width:100%}'
        '</style></head><body><main id="main-content">'
        + toolbar_html()
        + '<div id="tracker-page-jump-slot"></div>'
        + shortcut_html()
        + workout_html()
        + '<section data-dashboard-panel="10" data-dashboard-title="Overview"><h2>Overview Details</h2></section>'
        + '<section data-dashboard-panel="11" data-dashboard-title="Additional"><h2>Additional Details</h2></section>'
        + '</main></body></html>'
    )


@pytest.mark.parametrize("width", [320, 390, 768, 1024, 1280, 1440, 1920])
def test_688_real_template_controls_and_compact_metrics(width):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": width, "height": 950})
            page.route("https://tracker.test/", lambda route: route.fulfill(
                status=200, content_type="text/html", body=document()
            ))
            page.goto("https://tracker.test/")
            for path in STYLE_FILES:
                page.add_style_tag(content=read(path))
            for path in SCRIPTS:
                page.add_script_tag(content=read(path))
            expect(page.locator("#tracker-page-jump-select")).to_be_visible()
            expect(page.locator(".tracker-copy-section-link")).to_be_visible()
            expect(page.locator(".workspace-toolbar #dashboard-customize")).to_have_count(1)
            expect(page.locator(".dashboard-personalize")).to_have_count(0)
            expect(page.locator(".tracker-daily-flow559-links a")).to_have_count(11)
            assert page.locator(".tracker-daily-flow559-links a").all_text_contents() == [
                label for label, _ in EXPECTED
            ]
            assert page.locator(".tracker-daily-flow559-links a span").count() == 0
            expect(page.get_by_role("link", name="Rapid Gym Mode")).to_have_attribute(
                "href", "/workouts/quick"
            )
            widths = page.evaluate("""() => {
                const q=s=>document.querySelector(s);
                const c=s=>getComputedStyle(q(s));
                const r=s=>q(s).getBoundingClientRect();
                const names=['.tracker-account-action687',
                  '.workspace-toolbar form button','#ux-add-toggle',
                  '#command-open','#nav-filter','#workspace-settings-toggle'];
                return {
                  controls:names.map(x=>({
                    height:r(x).height,radius:c(x).borderTopLeftRadius,
                    border:c(x).borderTopWidth
                  })),
                  jumpHeight:r('.tracker-page-jump').height,
                  jumpBorder:c('.tracker-page-jump').borderTopWidth,
                  shortcutHeights:[...document.querySelectorAll(
                    '.tracker-daily-flow559-links a')].map(e=>e.getBoundingClientRect().height),
                  shortcutAlign:c('.tracker-daily-flow559-links a').alignItems,
                  metricPadding:parseFloat(c('.tracker-workout-summary661>div').paddingTop),
                  metricGap:parseFloat(c('.tracker-workout-summary661').columnGap),
                  metricColumns:c('.tracker-workout-summary661').gridTemplateColumns.split(' ').length,
                  overflow:document.documentElement.scrollWidth>innerWidth+1
                };
            }""")
            assert all(43 <= a["height"] <= 45 for a in widths["controls"]), (width, widths)
            assert len({a["radius"] for a in widths["controls"]}) == 1, (width, widths)
            assert len({a["border"] for a in widths["controls"]}) == 1, (width, widths)
            assert widths["jumpHeight"] <= (105 if width <= 600 else 60), (width, widths)
            assert widths["jumpBorder"] == "0px", (width, widths)
            assert widths["shortcutAlign"] == "center"
            assert all(h >= 44 for h in widths["shortcutHeights"]), (width, widths)
            assert widths["metricPadding"] <= (6 if width <= 760 else 5), (width, widths)
            assert widths["metricGap"] <= 6, (width, widths)
            if width >= 1200:
                assert widths["metricColumns"] == 6, (width, widths)
            assert not widths["overflow"], (width, widths)

            page.locator("#workspace-settings-toggle").click()
            expect(page.locator("#workspace-settings-panel")).to_be_visible()
            page.locator("#dashboard-customize").click()
            expect(page.locator("#dashboard-customize-panel")).to_be_visible()
            expect(page.locator("#dashboard-customize-list .customize-row")).to_have_count(3)
            page.locator("#dashboard-customize").click()
            expect(page.locator("#dashboard-customize-panel")).to_be_hidden()
            page.locator("#workspace-settings-close").click()
            expect(page.locator("#workspace-settings-panel")).to_be_hidden()
        finally:
            browser.close()


def test_688_non_dashboard_preferences_have_no_dashboard_customization():
    assert 'id="dashboard-customize"' not in toolbar_html(path="/vials")
    assert 'id="dashboard-customize-panel"' not in toolbar_html(path="/workouts")
