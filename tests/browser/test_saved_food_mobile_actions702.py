"""Release 702: render the real Saved Food edit Jinja form with synthetic data.

Pure local Chromium fixture. No backend, no installed records, no HTTP and
no form submission: the only Save click is intercepted to inspect intent.
"""
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import DictLoader, Environment
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = (ROOT / "app/templates/food_saved_edit669.html").read_text(encoding="utf-8")
MOBILE_JS = (ROOT / "app/static/js/tracker-mobile-shell507.js").read_text(encoding="utf-8")
STYLES = [
    ROOT / "app/static/app.css",
    ROOT / "app/static/css/tracker-mobile-shell507.css",
    ROOT / "app/static/css/tracker-mobile-density600.css",
    ROOT / "app/static/css/tracker-mobile-ux673.css",
    ROOT / "app/static/css/tracker-saved-food-actions702.css",
]
WIDTHS = (320, 390, 430, 760)
DENSITIES = ("compact", "balanced", "comfortable")
THEMES = ("light", "dark")

# The actual editor template extends base.html. Supply a deliberately tiny
# standalone shell so the real form and buttons render without a server.
SHELL = """<!doctype html><html lang="en"><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
</head><body><div id="app-shell">
<button type="button" id="sidebar-open" hidden>Menu</button>
<main id="main-content">{% block content %}{% endblock %}</main>
<nav class="tracker-mobile-dock" aria-label="Mobile quick navigation">
<a href="/mobile">Today</a>
<button id="tracker-mobile-more" type="button">More</button>
</nav></div></body></html>"""

BASE_CSS = """
:root { --surface:#fff; --ink:#192c31; --rule:#cbd5e1;
--teal:#1265ad; --teal-ink:#fff; --wash:#f1f5f9; }
body { margin:0; font:16px/1.5 system-ui,sans-serif; }
#main-content { box-sizing:border-box; max-width:900px;
  margin:0 auto; padding:12px; }
.food-saved-edit669 label { display:block; margin:.35rem 0; }
.food-saved-edit669 input { display:block; box-sizing:border-box;
  min-height:44px; width:100%; padding:.4rem; }
.food-row { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.5rem; }
@media(max-width:760px) { .food-row { grid-template-columns:minmax(0,1fr); } }
"""

def render_editor() -> str:
    env = Environment(loader=DictLoader({
        "base.html": SHELL,
        "food_saved_edit669.html": TEMPLATE,
    }), autoescape=True)
    product = SimpleNamespace(
        id=52, name="Example Greek Yogurt", source="manual",
        barcode="123456789012", serving_description="1 container",
    )
    nutrients = {f"nutrient_{idx}": (f"Nutrient {idx}", "g")
                 for idx in range(16)}
    return env.get_template("food_saved_edit669.html").render(
        product=product, day="2026-11-19",
        version="a" * 64, saved=False, usage=2,
        nutrients=nutrients, values={},
    )


def test_702_template_fixture_has_one_original_submit_and_cancel():
    html = render_editor()
    assert html.count('type="submit" class="primary"') == 1
    assert html.count('class="tracker-food-editor-back702"') == 1
    assert html.count('class="ux673-action-row tracker-food-editor-actions702"') == 1
    assert html.count('name="version"') == 1
    assert "Example Greek Yogurt" in html


@pytest.mark.parametrize("width", WIDTHS + (1024,))
def test_702_mobile_food_editor_actions_reachable_without_duplicate_submit(width):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": width, "height": 844},
                                    reduced_motion="reduce")
            requests = []
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: requests.append(request.url))
            page.route("**/*", lambda route: route.abort())
            page.set_content(render_editor())
            page.add_style_tag(content=BASE_CSS)
            for style in STYLES:
                page.add_style_tag(content=style.read_text(encoding="utf-8"))
            page.add_script_tag(content=MOBILE_JS)
            form = page.locator('.food-saved-edit669 form')
            row = page.locator(".tracker-food-editor-actions702")
            submit = row.locator('button[type="submit"]')
            cancel = row.locator("a.btn")
            back = page.locator(".tracker-food-editor-back702")
            dock = page.locator(".tracker-mobile-dock")
            assert form.count() == row.count() == submit.count() == cancel.count() == back.count() == 1
            assert form.get_attribute("method") == "post"
            assert form.get_attribute("action") == "/food/saved/52/edit"
            assert form.locator('input[name="version"]').input_value() == "a" * 64
            assert cancel.get_attribute("href") == "/food?day=2026-11-19#food-search"
            assert back.get_attribute("href") == cancel.get_attribute("href")

            for density in DENSITIES:
                for theme in THEMES:
                    page.evaluate("""([density,theme]) => {
                        document.documentElement.dataset.density = density;
                        document.documentElement.dataset.theme = theme;
                    }""", [density, theme])
                    page.evaluate("() => window.scrollTo(0,0)")
                    if width <= 760:
                        expect(dock).to_be_visible()
                        expect(submit).to_be_visible()
                        expect(cancel).to_be_visible()
                        assert row.evaluate(
                            "el => getComputedStyle(el).position"
                        ) == "sticky"
                        assert row.evaluate(
                            "el => getComputedStyle(el).gridTemplateColumns !== 'none'"
                        )
                        for control in (submit, cancel, back):
                            box = control.bounding_box()
                            assert box is not None and box["height"] >= 44, (
                                width, density, theme, control, box
                            )
                        action_box = row.bounding_box()
                        dock_box = dock.bounding_box()
                        assert action_box is not None and dock_box is not None
                        assert action_box["y"] >= 0
                        assert action_box["y"] + action_box["height"] <= dock_box["y"] - 4, (
                            width, density, theme, action_box, dock_box
                        )
                    else:
                        expect(dock).to_be_hidden()
                        assert row.evaluate("el => getComputedStyle(el).position") == "static"

                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= innerWidth + 1"
                    ), (width, density, theme)

                    # A focused input hides the dock and disables sticky
                    # positioning, so the virtual keyboard cannot trap the bar.
                    if width <= 760:
                        form.locator('input[name="name"]').focus()
                        expect(dock).to_be_hidden()
                        assert row.evaluate(
                            "el => getComputedStyle(el).position"
                        ) == "static"
                        form.locator('input[name="name"]').evaluate("el => el.blur()")
                        page.wait_for_function("""() =>
                            !document.documentElement.classList.contains('tracker-mobile-editing')
                        """)
                        expect(dock).to_be_visible()
                        assert row.evaluate(
                            "el => getComputedStyle(el).position"
                        ) == "sticky"

            # Intercept submit rather than issuing a POST. Check the ORIGINAL
            # form event still fires once with the existing hidden fields.
            form.evaluate("""form => {
                window.__saveAttempts = 0;
                form.addEventListener('submit', event => {
                    event.preventDefault();
                    window.__saveAttempts += 1;
                    window.__saveData = [...new FormData(form).keys()];
                });
            }""")
            submit.click()
            assert page.evaluate("window.__saveAttempts") == 1
            assert page.evaluate(
                "() => ['day','version','name','serving_description'].every(k => window.__saveData.includes(k))"
            )
            assert not requests, requests
            assert not errors, errors
        finally:
            browser.close()
