"""Release 600 mobile density and select-scroll source contracts.

Real mobile viewport behavior is tested separately by the guarded Chromium
HTTP/HTTPS gate. These tests never connect to a running Tracker database.
"""
from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "app/templates/base.html"
CSS = ROOT / "app/static/css/tracker-mobile-density600.css"
JS = ROOT / "app/static/js/tracker-mobile-scroll600.js"
BROWSER = ROOT / "tests/browser/test_strict_csrf521.py"


def test_600_mobile_assets_are_loaded_after_existing_global_styles():
    html = BASE.read_text()
    assert html.count("tracker-mobile-density600.css?v=600") == 1
    assert html.count("tracker-mobile-scroll600.js?v=600") == 1
    assert html.index("tracker-section-explanations598.css?v=598") < html.index(
        "tracker-mobile-density600.css?v=600"
    )
    assert html.index("tracker-mobile-density600.css?v=600") < html.index(
        "tracker-mobile-scroll600.js?v=600"
    )
    Environment().parse(html)


def test_600_density_is_phone_only_keeps_forms_and_dock_usable():
    css = CSS.read_text()
    assert "@media screen and (max-width: 760px)" in css
    assert ":root[data-density] #main-content" in css
    assert "--tracker-mobile600-gap" in css
    assert "--tracker-mobile600-pad" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in css
    assert "data-density=\"comfortable\"" in css
    assert "data-density=\"compact\"" in css
    assert "min-height: 44px" in css
    assert "16px" in css
    assert "safe-area-inset-bottom" in css
    assert "overflow-x: auto" in css
    assert ".tracker-mobile-dock" not in css
    assert "display: none" not in css


def test_600_get_filter_position_is_opt_in_by_event_not_form_interception():
    js = JS.read_text()
    assert "window.matchMedia('(max-width: 760px)')" in js
    assert "HTMLSelectElement" in js
    assert "document.addEventListener('change'" in js
    assert "document.addEventListener('pointerdown'" in js
    assert "document.addEventListener('focusin'" in js
    assert "this.form.submit()" in js
    assert "submittedGetFilter(select)" in js
    assert "form.method.toLowerCase() !== 'get'" in js
    assert "sessionStorage.setItem" in js
    assert "sessionStorage.removeItem" in js
    assert "window.addEventListener('pageshow'" in js
    assert "window.scrollBy({top:" in js
    assert "requestAnimationFrame(() => requestAnimationFrame(" in js
    assert "tracker-page-jump-select" in js
    assert "location.hash" in js
    assert "localStorage" not in js
    assert "preventDefault" not in js
    assert "form.submit()" not in js.replace("this.form.submit()", "")
    assert "select.value" not in js
    assert "innerHTML" not in js


def test_600_real_browser_gate_covers_navigation_and_local_changes():
    browser = BROWSER.read_text()
    for name in (
        "test_600_mobile_get_filter_preserves_dropdown_position",
        "test_600_mobile_in_place_select_keeps_viewport_and_density",
    ):
        assert browser.count("def " + name + "(") == 1
        before = browser.split("def " + name + "(", 1)[0]
        assert '@pytest.mark.parametrize("scheme", ("http", "https"))' in before[-100:]
    assert "page.set_viewport_size({\"width\": 390, \"height\": 844})" in browser
    assert "page.expect_navigation(wait_until=\"networkidle\")" in browser
    assert 'select.select_option(chosen)' in browser
    assert 'select.select_option("b")' in browser
    assert "assert not errors, errors" in browser
