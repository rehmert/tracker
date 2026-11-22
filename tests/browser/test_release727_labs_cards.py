"""Release 727: real responsive Labs report table cards and preserved links."""
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "app/templates/labs.html"
CSS = ROOT / "app/static/css/tracker-mobile-ux673.css"
pytestmark = pytest.mark.browser


def table_fragment():
    src = TEMPLATE.read_text(encoding="utf-8")
    a = src.index('<div class="scroll"><table class="ux673-card-table" id="labs-reports-table">')
    b = src.index("</table></div>", a) + len("</table></div>")
    env = Environment()
    env.filters["dt"] = lambda value: value.isoformat()
    reports = [
        SimpleNamespace(id=41, drawn_on=date(2026,11,20),
                        lab_name="Reference Lab", results=[1,2],
                        stored_name="report.pdf"),
        SimpleNamespace(id=42, drawn_on=date(2026,10,2),
                        lab_name="Second Lab", results=[1],
                        stored_name=None),
    ]
    return env.from_string(src[a:b]).render(reports=reports)


@pytest.mark.parametrize("scheme", ("light", "dark"))
@pytest.mark.parametrize("density", ("compact", "balanced", "comfortable"))
def test_727_labs_phone_cards_and_desktop_table(scheme,density):
    fragment = table_fragment()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for width in (320, 390, 430, 760, 1024):
                page = browser.new_page(viewport={"width":width,"height":844},
                                        color_scheme=scheme)
                try:
                    page.set_content(
                        '<!doctype html><html><head>'
                        '<meta name="viewport" content="width=device-width, initial-scale=1">'
                        '<style>body{margin:0;padding:12px} *{box-sizing:border-box}</style>'
                        '</head><body><main id="main-content">'+fragment+
                        '</main></body></html>'
                    )
                    page.evaluate(
                        "(density) => document.documentElement.dataset.density = density",
                        density,
                    )
                    page.add_style_tag(content=CSS.read_text(encoding="utf-8"))
                    table = page.locator("#labs-reports-table")
                    rows = table.locator("tbody tr[data-labs-report-row]")
                    expect(rows).to_have_count(2)
                    assert rows.first.locator("td").count()==5
                    assert rows.first.locator('td[data-label="Drawn"] a').get_attribute("href") == "/labs/41"
                    assert rows.nth(1).locator('td[data-label="Drawn"] a').get_attribute("href") == "/labs/42"
                    actions = rows.first.locator('td[data-label="Manage"] .tracker-macd741-action')
                    assert actions.count() == 3
                    assert [actions.nth(i).get_attribute("href") for i in range(3)] == [
                        "/labs/41#lab-details741", "/labs/41#lab-results741", "/labs/41#lab-delete741"
                    ]
                    mobile=width<=760
                    display=rows.first.evaluate("(el)=>getComputedStyle(el).display")
                    assert display == ("grid" if mobile else "table-row"), (
                        width,scheme,density,display
                    )
                    assert table.locator("thead").is_hidden() == mobile
                    if mobile:
                        assert rows.first.locator("td[data-label]").count()==5
                        assert all(links.evaluate_all(
                            "(els)=>els.map(el=>el.getBoundingClientRect().height>=44)"))
                            for links in [rows.first.locator("td[data-ux673-action] a")]
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= innerWidth"
                    ), (width,scheme,density)
                finally:
                    page.close()
        finally:
            browser.close()
