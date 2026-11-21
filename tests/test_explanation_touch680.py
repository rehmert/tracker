"""Release 680: real browser checks for existing inline explanation expansion."""
from pathlib import Path
import os

from jinja2 import Environment
from playwright.sync_api import sync_playwright
import pytest

ROOT = Path(__file__).resolve().parents[1]
STYLES = ROOT / "app/static/css"
SCRIPT = ROOT / "app/static/js/tracker-section-explanations598.js"


def test_680_link_order_and_existing_js_preserved():
    base = (ROOT / "app/templates/base.html").read_text()
    css = (STYLES / "tracker-explanation-touch680.css").read_text()
    assert base.count("tracker-explanation-touch680.css?v=680") == 1
    assert base.index("tracker-ui-foundation679.css?v=743") < base.index(
        "tracker-explanation-touch680.css?v=680"
    )
    assert "tracker-section-explanations598.js?v=598" in base
    assert "tracker-explanation598-toggle:not([hidden])" in css
    assert css.count("{") == css.count("}")
    Environment().parse(base)


@pytest.mark.parametrize("width", (320, 390, 768, 1280))
@pytest.mark.parametrize("scheme", ("light", "dark"))
def test_680_more_less_is_44px_and_keyboard_accessible(width, scheme):
    color = ("--surface:#fff;--ink:#172b39;--wash:#edf3f9;--teal:#145e9e"
             if scheme == "light" else
             "--surface:#182530;--ink:#f5f7fa;--wash:#263645;--teal:#78baff")
    html = f"""<!doctype html><html><head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>body{{margin:0;{color};color:var(--ink);background:var(--surface);}}
        #main-content{{padding:12px;max-width:100%;box-sizing:border-box}}
        section{{max-width:100%}} p.note{{max-width:260px;font:16px/1.4 sans-serif}}</style>
        </head><body><main id="main-content">
        <section><h2>Explanation</h2>
        <p class="note">This is a deliberately lengthy section explanation containing
        many additional words to require more than one line of explanatory
        copy and to activate the existing More and Less disclosure behavior.</p>
        </section></main></body></html>"""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": width, "height": 844},
                                    color_scheme=scheme)
            page.set_content(html)
            page.add_style_tag(path=str(STYLES / "tracker-section-explanations598.css"))
            page.add_style_tag(path=str(STYLES / "tracker-explanation-touch680.css"))
            page.add_script_tag(path=str(SCRIPT))
            toggle = page.locator(".tracker-explanation598-toggle:visible")
            toggle.wait_for(state="visible")
            assert toggle.count() == 1
            assert toggle.inner_text() == "More"
            dims = toggle.evaluate("e => ({width:e.getBoundingClientRect().width,"
                                   "height:e.getBoundingClientRect().height})")
            assert dims["width"] >= 44, dims
            assert dims["height"] >= 44, dims
            toggle.focus()
            assert toggle.evaluate(
                "e => getComputedStyle(e).outlineStyle"
            ) == "solid"
            toggle.click()
            assert toggle.inner_text() == "Less"
            assert toggle.get_attribute("aria-expanded") == "true"
            toggle.click()
            assert toggle.inner_text() == "More"
            assert toggle.get_attribute("aria-expanded") == "false"
            assert page.evaluate(
                "() => document.documentElement.scrollWidth <= innerWidth + 1"
            )
        finally:
            browser.close()
