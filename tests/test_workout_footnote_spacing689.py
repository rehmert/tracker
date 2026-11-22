"""Release 689: real Workout Activity empty-state action-to-footnote spacing."""
import os
from pathlib import Path

import pytest
from jinja2 import Environment
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
def src(path):
    return (ROOT / path).read_text(encoding="utf-8")

CSS = [
    "app/static/app.css",
    "app/static/css/tracker-layout-density685.css",
    "app/static/css/tracker-compact-aggressive686.css",
    "app/static/css/tracker-shortcuts-toolbar687.css",
    "app/static/css/tracker-dashboard-polish688.css",
    "app/static/css/tracker-workout-footnote689.css",
    "app/static/css/tracker-workout-dashboard661.css",
]


def workout_fragment():
    env = Environment(autoescape=True)
    env.filters["dt"] = lambda value: str(value)
    return env.from_string(
        src("app/templates/_workout_dashboard661.html")
    ).render(workout_summary={
        "sessions7": 0, "days7": 0, "sessions28": 0,
        "days28": 0, "sets28": 0, "reps28": 0,
        "recent": [], "in_progress": False,
    })


def test_689_style_link_is_versioned_and_scoped():
    base = src("app/templates/base.html")
    css = src("app/static/css/tracker-workout-footnote689.css")
    assert base.count("/static/css/tracker-global-density-bundle746.css?v=746") == 1
    assert "#tracker-workout-dashboard661 .tracker-workout-recent661 > p:last-child" in css
    assert "#tracker-workout-dashboard661 > .tracker-workout-footnote661" in css
    assert "display: none" not in css
    assert "position:" not in css


@pytest.mark.parametrize("density,width", [
    ("compact", 320), ("compact", 390), ("compact", 768),
    ("compact", 1440), ("balanced", 390), ("balanced", 1440),
    ("comfortable", 390), ("comfortable", 1440),
])
def test_689_empty_workout_action_to_explanation_gap(density, width):
    fragment = workout_fragment()
    assert "Log a Previous Workout" in fragment
    assert "A training day is a calendar date" in fragment
    html = (
        f'<!doctype html><html data-density="{density}"><head>'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<style>*{box-sizing:border-box}body{margin:0}'
        '#main-content{padding:8px;min-width:0;width:100%}'
        '</style></head><body><main id="main-content">'
        + fragment + '</main></body></html>'
    )
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.set_content(html)
            for name in CSS:
                page.add_style_tag(content=src(name))
            button = page.locator(
                "#tracker-workout-dashboard661 .tracker-workout-empty-action678"
            )
            footnote = page.locator(
                "#tracker-workout-dashboard661 > .tracker-workout-footnote661"
            )
            expect(button).to_be_visible()
            expect(footnote).to_be_visible()
            measures = page.evaluate("""() => {
                const section = document.querySelector('#tracker-workout-dashboard661');
                const action = section.querySelector('.tracker-workout-empty-action678');
                const wrapper = action.closest('p');
                const note = section.querySelector('.tracker-workout-footnote661');
                const a = action.getBoundingClientRect();
                const n = note.getBoundingClientRect();
                const w = getComputedStyle(wrapper);
                const f = getComputedStyle(note);
                return {
                    gap: n.top - a.bottom,
                    actionHeight: a.height,
                    wrapperMarginBottom: parseFloat(w.marginBottom),
                    footnoteMarginTop: parseFloat(f.marginTop),
                    horizontalOverflow: document.documentElement.scrollWidth > innerWidth + 1
                };
            }""")
            assert 0 <= measures["gap"] <= 12, (density, width, measures)
            assert measures["wrapperMarginBottom"] == 0, (density, width, measures)
            assert measures["footnoteMarginTop"] <= 6, (density, width, measures)
            assert measures["actionHeight"] >= 44, (density, width, measures)
            assert not measures["horizontalOverflow"], (density, width, measures)
        finally:
            browser.close()
