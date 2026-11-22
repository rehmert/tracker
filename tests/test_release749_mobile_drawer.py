"""Release 749: content-fit portrait drawer and full scroll access.

Chromium tests use synthetic navigation and actual shared CSS order; no live
server, health data, or network access is required.
"""
from pathlib import Path
import re
import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "app/templates/base.html"
CSS749 = ROOT / "app/static/css/tracker-mobile-drawer749.css"


def _shared_css():
    template = BASE.read_text(encoding="utf-8")
    sources = re.findall(r'href="(/static/[^"]+\.css(?:\?[^"]*)?)"', template)
    assert any("tracker-mobile-drawer749.css?v=749" in url for url in sources)
    sheets = []
    for url in sources:
        file = ROOT / ("app" + url.split("?", 1)[0])
        if file.is_file():
            sheets.append((url, file.read_text(encoding="utf-8")))
    old = "\n".join(content for url, content in sheets
                    if "tracker-mobile-drawer749.css" not in url)
    return old, CSS749.read_text(encoding="utf-8")


def _fixture(expanded=False):
    links = "".join(
        f'<li><a href="#item-{index}" style="min-height:44px">'
        f'<span class="nav-text">Synthetic item {index}</span></a></li>'
        for index in range(36)
    )
    sections = "".join(
        '<section class="nav-section' + (' nav-expanded' if expanded else '') + '">'
        f'<button class="nav-section-toggle" type="button">Category {index}</button>'
        '<ul class="nav-links nav-group">' + (links if index == 0 else '') + '</ul>'
        '</section>'
        for index in range(7)
    )
    return (
        '<!doctype html><html data-density="compact"><head>'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '</head><body>'
        '<div id="app-shell" class="shell sidebar-mobile-open">'
        '<button class="sidebar-backdrop" aria-label="Close navigation"></button>'
        '<nav id="app-sidebar" class="rail" aria-label="Main navigation">'
        '<div class="rail-top"><span class="rail-kicker">YOUR WORKSPACE</span></div>'
        '<a class="brand" href="/">Tracker</a>'
        '<div class="nav-scroll">'
        '<ul class="nav-links nav-pinned"><li><a href="/">Dashboard</a></li></ul>'
        '<div id="nav-sortable">' + sections + '</div>'
        '</div></nav><main id="main-content">Synthetic page</main></div>'
        '</body></html>'
    )


def _metrics(page):
    return page.evaluate("""() => {
      const rail = document.querySelector('#app-sidebar');
      const scroll = rail.querySelector('.nav-scroll');
      const a = rail.getBoundingClientRect();
      const b = scroll.getBoundingClientRect();
      return {
        railHeight:a.height, railBottom:a.bottom, navBottom:b.bottom,
        scrollHeight:scroll.scrollHeight, clientHeight:scroll.clientHeight,
        width:a.width, viewportHeight:innerHeight,
        viewportWidth:innerWidth,
        pageScrollWidth:document.documentElement.scrollWidth,
        railPosition:getComputedStyle(rail).position,
        railBottomCSS:getComputedStyle(rail).bottom
      };
    }""")


def test_749_stylesheet_last_and_mobile_only():
    html = BASE.read_text(encoding="utf-8")
    assert html.count("tracker-mobile-drawer749.css?v=749") == 1
    assert html.index("tracker-global-density-bundle746.css?v=746") < html.index(
        "tracker-mobile-drawer749.css?v=749"
    )
    original = (ROOT / "app/static/app.css").read_text()
    assert "max-height: 55vh" in original
    css = CSS749.read_text()
    assert "max-height: none" in css and "height: auto" in css
    assert "@media screen and (max-width: 760px)" in css
    assert "100dvh" in css and "display: none" not in css


@pytest.mark.parametrize("width,height", [
    (320, 640), (390, 844), (430, 932), (760, 1024)
])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_749_portrait_short_drawer_has_no_white_band(width, height, scheme):
    old, fix = _shared_css()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": width, "height": height},
                                    color_scheme=scheme)
            page.route("**/*", lambda route: route.abort())
            page.set_content(_fixture())
            page.add_style_tag(content=old)
            before = _metrics(page)
            assert before["railHeight"] >= height - 1, before
            page.add_style_tag(content=fix)
            after = _metrics(page)
            # A 320px-wide, short-height phone may need the entire
            # viewport for its seven categories; it must be able to scroll.
            # Taller portrait phones should instead fit their short menu
            # without leaving the legacy empty white band.
            assert 0 < after["railHeight"] <= height + 1, after
            assert after["railBottom"] - after["navBottom"] < 45, after
            if after["scrollHeight"] > after["clientHeight"] + 2:
                assert after["clientHeight"] > 0, after
            else:
                assert after["scrollHeight"] <= after["clientHeight"] + 2, after
                if height >= 800:
                    assert after["railHeight"] < height - 40, after
            assert after["pageScrollWidth"] <= width + 1, after
            assert 0 < after["width"] <= width, after
            assert after["railPosition"] == "fixed", after
            # CSS specifies bottom:auto, but Chromium returns its resolved
            # pixel offset from getComputedStyle() for fixed positioning.
            # The visible improvement is measured from element rectangles.
            assert before["railBottom"] - before["navBottom"] > (
                after["railBottom"] - after["navBottom"] + 50
            ), (before, after)
            toggle = page.locator(".nav-section-toggle").first
            toggle.focus()
            assert toggle.evaluate("(el) => document.activeElement === el")
            page.close()
        finally:
            browser.close()


@pytest.mark.parametrize("width,height", [(390, 844), (640, 390)])
def test_749_expanded_menu_scrolls_to_last_item(width, height):
    old, fix = _shared_css()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.route("**/*", lambda route: route.abort())
            page.set_content(_fixture(expanded=True))
            page.add_style_tag(content=old)
            page.add_style_tag(content=fix)
            metrics = _metrics(page)
            assert metrics["railHeight"] <= height + 1, metrics
            assert metrics["clientHeight"] > 0, metrics
            assert metrics["scrollHeight"] > metrics["clientHeight"] + 200, metrics
            assert metrics["pageScrollWidth"] <= width + 1, metrics
            scroll = page.locator("#app-sidebar .nav-scroll")
            scroll.evaluate("(node) => node.scrollTop = node.scrollHeight")
            assert scroll.evaluate("(node) => node.scrollTop > 100")
            final_link = page.locator('a[href="#item-35"]')
            assert final_link.is_visible()
            final_link.focus()
            assert final_link.evaluate("(el) => document.activeElement === el")
            page.close()
        finally:
            browser.close()


def test_749_desktop_sidebar_unchanged():
    old, fix = _shared_css()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1024, "height": 768})
            page.route("**/*", lambda route: route.abort())
            page.set_content(_fixture())
            page.add_style_tag(content=old)
            before = _metrics(page)
            page.add_style_tag(content=fix)
            after = _metrics(page)
            assert before == after, (before, after)
            page.close()
        finally:
            browser.close()
