"""Release 726: lab action links, More disclosure and touch sizes in Chromium."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "app/templates/labs.html"
LAB_CSS = ROOT / "app/static/css/tracker-labs-overview.css"
ACTION_CSS = ROOT / "app/static/css/tracker-integrated-flow696.css"
pytestmark = pytest.mark.browser


def rendered_actions():
    text = TEMPLATE.read_text(encoding="utf-8")
    begin = text.index('<nav class="row tracker-flow696-actions labs726-actions"')
    end = text.index("</nav>", begin) + len("</nav>")
    return Environment().from_string(text[begin:end]).render(
        cards=[SimpleNamespace(name="TSH")], reports=[SimpleNamespace(id=42)]
    )


@pytest.mark.parametrize("scheme", ("light", "dark"))
def test_726_labs_nav_mobile_disclosure_sizes_no_overflow(scheme):
    nav = rendered_actions()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for width in (320, 390, 430, 760, 1024):
                page = browser.new_page(
                    viewport={"width":width, "height":800},
                    color_scheme=scheme,
                )
                try:
                    page.set_content(
                        '<!doctype html><html><head>'
                        '<meta name="viewport" content="width=device-width, initial-scale=1">'
                        '<style>body { margin:0; padding:12px; }</style>'
                        '</head><body>' + nav + '</body></html>'
                    )
                    page.add_style_tag(content=ACTION_CSS.read_text(encoding="utf-8"))
                    page.add_style_tag(content=LAB_CSS.read_text(encoding="utf-8"))
                    actions = page.get_by_role("navigation", name="Lab report actions")
                    expect(actions.locator(":scope > a")).to_have_count(2)
                    more = actions.locator("details.labs726-more")
                    expect(more.locator("summary")).to_be_visible()
                    expect(more).not_to_have_attribute("open", "")
                    expect(more.get_by_role("link", name="Compare two reports")).to_be_hidden()
                    controls = actions.locator(":scope > a, :scope > details > summary")
                    assert controls.count() == 3
                    for i in range(controls.count()):
                        assert controls.nth(i).evaluate(
                            "(el) => el.getBoundingClientRect().height >= 44"
                        ), (scheme, width, i)
                    more.locator("summary").click()
                    expect(more.get_by_role("link", name="Compare two reports")).to_be_visible()
                    expect(more.get_by_role("link", name="Analyte trends")).to_be_visible()
                    expect(more.get_by_role("link", name="Reuse latest report layout")).to_be_visible()
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= innerWidth"
                    ), (scheme, width)
                    more.locator("summary").click()
                    expect(more).not_to_have_attribute("open", "")
                finally:
                    page.close()
        finally:
            browser.close()
