"""Release 729: mobile manual Labs cards and existing FormData in Chromium."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
ROW = ROOT / "app/templates/_lab_row.html"
SHARED = ROOT / "app/static/css/tracker-mobile-ux673.css"
PAGE = ROOT / "app/static/css/tracker-lab-navigation.css"
pytestmark = pytest.mark.browser


def row_markup(name, value):
    return Environment().from_string(ROW.read_text(encoding="utf-8")).render(
        row=SimpleNamespace(analyte=name, value=value, unit="mIU/L",
                            ref_low="0.4", ref_high="4.5")
    )


@pytest.mark.parametrize("scheme", ("light", "dark"))
@pytest.mark.parametrize("density", ("compact", "balanced", "comfortable"))
def test_729_phone_cards_and_desktop_preserve_form_values(scheme, density):
    first, second = row_markup("TSH", "1.25"), row_markup("Free T4", "0.91")
    html = (
        '<!doctype html><html><head>'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<style>body{margin:0;padding:12px}*{box-sizing:border-box}'
        'main{max-width:960px;margin:0 auto}'
        'table{border-collapse:collapse;width:100%}'
        'input{padding:6px;border:1px solid #889;min-width:50px}'
        '</style></head><body><main id="main-content">'
        '<form method="post" action="/labs" data-lab-manual-entry>'
        '<div class="scroll"><table class="items ux673-card-table tracker-lab-result-cards729">'
        '<thead><tr><th>Analyte</th><th>Value</th><th>Unit</th>'
        '<th>Printed range, low</th><th>Printed range, high</th><th></th></tr></thead>'
        '<tbody id="lab-rows">' + first + '</tbody></table></div>'
        '</form></main></body></html>'
    )
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            for width in (320, 390, 430, 760, 1024):
                page = browser.new_page(
                    viewport={"width": width, "height": 844},
                    color_scheme=scheme,
                )
                try:
                    page.set_content(html)
                    page.evaluate(
                        "(density) => document.documentElement.dataset.density = density",
                        density,
                    )
                    page.add_style_tag(content=SHARED.read_text(encoding="utf-8"))
                    page.add_style_tag(content=PAGE.read_text(encoding="utf-8"))
                    rows = page.locator("#lab-rows tr")
                    expect(rows).to_have_count(1)
                    mobile = width <= 760
                    assert rows.first.evaluate(
                        "(el) => getComputedStyle(el).display"
                    ) == ("grid" if mobile else "table-row")
                    assert page.locator("thead").is_hidden() == mobile
                    inputs = rows.first.locator("input")
                    expect(inputs).to_have_count(5)
                    if mobile:
                        for index in range(5):
                            assert inputs.nth(index).evaluate(
                                "(el) => el.getBoundingClientRect().height >= 44"
                            ), (width, density, scheme, index)
                        assert rows.first.get_by_role("button", name="Remove").evaluate(
                            "(el) => el.getBoundingClientRect().height >= 44"
                        )
                        assert rows.first.locator('td[data-ux673-full]').count() == 1
                    page.locator("#lab-rows").evaluate(
                        "(el, markup) => el.insertAdjacentHTML('beforeend', markup)",
                        second,
                    )
                    expect(rows).to_have_count(2)
                    assert rows.nth(1).evaluate(
                        "(el) => getComputedStyle(el).display"
                    ) == ("grid" if mobile else "table-row")
                    assert rows.nth(1).locator('input[name="analyte"]').input_value() == "Free T4"
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= innerWidth"
                    ), (width, density, scheme)
                    assert page.locator('form[action="/labs"]').evaluate(
                        "form => new FormData(form).getAll('analyte')"
                    ) == ["TSH", "Free T4"]
                finally:
                    page.close()
        finally:
            browser.close()
