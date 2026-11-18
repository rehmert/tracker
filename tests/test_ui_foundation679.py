"""Release 679: opt-in component source and computed-style contracts.

These tests use disposable Chromium DOM, not authenticated application pages.
They do not assert that any existing page has migrated to these classes.
"""
from pathlib import Path
import os
import pytest
from jinja2 import Environment
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "app/static/css/tracker-ui-foundation679.css"


def test_679_component_layer_is_loaded_and_namespaced():
    html = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    assert html.count("tracker-ui-foundation679.css?v=679") == 1
    assert html.index("tracker-ui-foundation679.css?v=679") < html.index(
        "tracker-shortcut-buttons676.css?v=676"
    )
    assert css.count("{") == css.count("}")
    for selector in (".tracker-ui-actions", ".tracker-ui-action",
                     ".tracker-ui-action--primary", ".tracker-ui-card",
                     ".tracker-ui-card__value", ".tracker-ui-feedback",
                     ".tracker-ui-field-error", ":focus-visible"):
        assert selector in css
    Environment().parse(html)


@pytest.mark.parametrize("width", [320, 390, 768, 1280])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_679_component_styles_are_readable_and_touch_friendly(width, theme):
    palette = (
        "--surface:#fff;--ink:#172b39;--wash:#edf3f9;--rule:#a9bacb;"
        "--teal:#145e9e;--teal-ink:#fff;"
        if theme == "light" else
        "--surface:#182530;--ink:#f5f7fa;--wash:#263645;--rule:#526779;"
        "--teal:#78baff;--teal-ink:#091725;"
    )
    markup = f"""<!doctype html><html><head>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    </head><body style="margin:0;padding:12px;box-sizing:border-box;{palette}">
    <main><nav class="tracker-ui-actions" aria-label="Actions">
    <a class="tracker-ui-action tracker-ui-action--primary" href="#target">Record Set</a>
    <button class="tracker-ui-action" type="button">More Details</button></nav>
    <section class="tracker-ui-card" aria-label="Metric">
    <div class="tracker-ui-card__label">Completed today</div>
    <div class="tracker-ui-card__value">12</div></section>
    <p class="tracker-ui-feedback" role="status">Saved successfully</p>
    <span id="target"></span></main></body></html>"""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": width, "height": 844})
            page.set_content(markup)
            page.add_style_tag(path=str(CSS))
            actions = page.locator(".tracker-ui-action")
            assert actions.count() == 2
            for index in range(actions.count()):
                action = actions.nth(index)
                assert action.evaluate("e => e.getBoundingClientRect().height >= 44")
                assert action.evaluate("e => getComputedStyle(e).textDecorationLine") == "none"
            assert page.locator(".tracker-ui-card").evaluate(
                "e => getComputedStyle(e).borderTopStyle"
            ) == "solid"
            assert page.evaluate(
                "() => document.documentElement.scrollWidth <= window.innerWidth + 1"
            )
            actions.first.focus()
            assert actions.first.evaluate(
                "e => getComputedStyle(e).outlineStyle"
            ) == "solid"
            assert page.locator(".tracker-ui-feedback").is_visible()
        finally:
            browser.close()
