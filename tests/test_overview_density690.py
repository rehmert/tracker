"""Release 690: real rendered heights for Overview Workout Activity and At a glance."""
from pathlib import Path
from types import SimpleNamespace
import os

import pytest
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app" / "templates"
BASE_CSS = [
    "app/static/app.css",
    "app/static/css/tracker-workout-dashboard661.css",
    "app/static/css/tracker-workout-nav-density681.css",
    "app/static/css/tracker-layout-density685.css",
    "app/static/css/tracker-compact-aggressive686.css",
    "app/static/css/tracker-shortcuts-toolbar687.css",
    "app/static/css/tracker-dashboard-polish688.css",
    "app/static/css/tracker-workout-footnote689.css",
    "app/static/css/tracker-daily-flow559.css",
]
NEW_CSS = "app/static/css/tracker-overview-density690.css"


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def render_fragments():
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    env.filters["dt"] = str
    env.filters["n1"] = lambda value: f"{value:.1f}"
    env.filters["money"] = lambda value: "$" + f"{value:,.2f}"
    workout = env.from_string(
        read("app/templates/_workout_dashboard661.html")
    ).render(workout_summary=SimpleNamespace(
        in_progress=False, sessions7=0, days7=0,
        sessions28=0, days28=0, sets28=0, reps28=0, recent=[],
        recent_expanded=True,  # The density test measures the expanded empty-state button.
    ))
    dash = read("app/templates/dashboard.html")
    start = dash.index('<section data-dashboard-panel="1" data-dashboard-title="At a glance"')
    stop = dash.index("</section>", start) + len("</section>")
    spark = (
        '<svg class="metric-sparkline" viewBox="0 0 140 46" role="img" '
        'aria-label="Recorded 30-day trend"><path '
        'd="M0 18 L30 24 L60 10 L90 28 L140 20" '
        'stroke="currentColor" fill="none"/></svg>'
    )
    glance = env.from_string(dash[start:stop]).render(
        vitals=SimpleNamespace(
            weight=267.7, unit="lb",
            bp=SimpleNamespace(systolic=115, diastolic=64), pulse=80,
        ),
        vital_trends=SimpleNamespace(
            weight=SimpleNamespace(change30=-8.0),
            systolic=SimpleNamespace(avg30=122),
            pulse=SimpleNamespace(avg30=82),
        ),
        metric_sparklines={"weight": spark, "bp": spark, "pulse": spark},
        inventory_value=2564.66, total_spend=2669.68,
        active=[1, 2, 3], no_coa=35,
    )
    return workout + glance


def measure(page):
    return page.evaluate("""() => {
        const workout = document.querySelector('#tracker-workout-dashboard661');
        const glance = document.querySelector('[data-dashboard-title="At a glance"]');
        const nav = workout.querySelector('nav.tracker-workout-shortcuts678');
        const action = workout.querySelector('.tracker-workout-empty-action678');
        const footnote = workout.querySelector('.tracker-workout-footnote661');
        const card = glance.querySelector('.insight-card');
        const inventory = glance.querySelector('.dashboard-metrics > div');
        const sparks = [...glance.querySelectorAll('svg.metric-sparkline')];
        return {
            workoutHeight: workout.getBoundingClientRect().height,
            insightHeight: card.getBoundingClientRect().height,
            inventoryHeight: inventory.getBoundingClientRect().height,
            sparklineHeight: sparks[0].getBoundingClientRect().height,
            sparklineCount: sparks.length,
            actionHeight: action.getBoundingClientRect().height,
            footnoteGap: footnote.getBoundingClientRect().top -
                action.getBoundingClientRect().bottom,
            navHeights: [...nav.querySelectorAll('a')].map(
                item => item.getBoundingClientRect().height
            ),
            horizontalOverflow: document.documentElement.scrollWidth > innerWidth + 1,
        };
    }""")


def test_690_dashboard_asset_and_content_contract():
    dashboard = read("app/templates/dashboard.html")
    assert dashboard.count("/static/css/tracker-overview-density690.css?v=690") == 1
    assert dashboard.index("tracker-overview-density690.css?v=690") > dashboard.index(
        "tracker-daily-flow559.css?v=559"
    )
    assert dashboard.index("tracker-workout-dashboard661.css?v=721") < dashboard.index(
        "{% block content %}"
    )
    css = read(NEW_CSS)
    assert "#main-content #tracker-workout-dashboard661" in css
    assert '.metric-section[data-dashboard-title="At a glance"]' in css
    assert "min-height: 44px" in css
    assert "display: none" not in css
    assert "visibility: hidden" not in css
    assert "overflow: hidden" not in css
    assert "A training day is a calendar date" in render_fragments()
    assert "Total spent (landed)" in render_fragments()


@pytest.mark.parametrize("density,width", [
    ("compact", 320), ("compact", 390), ("compact", 768), ("compact", 1275),
    ("balanced", 390), ("balanced", 768), ("balanced", 1275),
    ("comfortable", 390), ("comfortable", 1275),
])
def test_690_measured_height_reduction_and_touch_targets(density, width):
    doc = (
        f'<!doctype html><html data-density="{density}"><head>'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>*{box-sizing:border-box}body{margin:0}'
        '#main-content{padding:8px;min-width:0;width:100%}</style>'
        '</head><body><main id="main-content">'
        + render_fragments() + '</main></body></html>'
    )
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": width, "height": 1000})
            page.set_content(doc)
            for path in BASE_CSS:
                page.add_style_tag(content=read(path))
            before = measure(page)
            page.add_style_tag(content=read(NEW_CSS))
            after = measure(page)
            expect(page.locator("#tracker-workout-dashboard661")).to_be_visible()
            expect(page.locator(".insight-card")).to_have_count(3)
            expect(page.locator(".dashboard-metrics > div")).to_have_count(4)
            assert before["sparklineCount"] == after["sparklineCount"] == 3
            assert 0 < after["sparklineHeight"] <= 26, (density, width, after)
            assert all(h >= 44 for h in after["navHeights"]), (density, width, after)
            assert after["actionHeight"] >= 44, (density, width, after)
            assert 0 <= after["footnoteGap"] <= 12, (density, width, after)
            assert not after["horizontalOverflow"], (density, width, after)
            assert before["workoutHeight"] - after["workoutHeight"] >= 12, (
                density, width, before, after,
            )
            assert before["insightHeight"] - after["insightHeight"] >= 18, (
                density, width, before, after,
            )
            assert after["inventoryHeight"] < before["inventoryHeight"], (
                density, width, before, after,
            )
        finally:
            browser.close()
