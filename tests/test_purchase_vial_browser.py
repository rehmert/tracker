"""Live purchase form quantity and pricing calculations (no database)."""
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app/static/js/tracker-purchase-vials.js"
TEMPLATE = ROOT / "app/templates/purchase_detail.html"


def fixture_html():
    return """<!doctype html><html><body>
    <form id="purchase-vial-form" data-currency="$">
      <label id="purchase-vial-quantity-field">
        <input name="quantity" type="number" value="1"></label>
      <label id="purchase-vial-kits-field" hidden>
        <input name="kit_count" type="number" value="1" disabled></label>
      <select name="kit_size">
        <option value="1">Individual</option><option value="5">Half</option>
        <option value="10">Full</option></select>
      <select name="price_basis">
        <option value="per_vial">Per vial</option>
        <option value="per_half_kit">Per half kit</option>
        <option value="per_full_kit">Per full kit</option>
      </select>
      <input name="price_amount" value="0" type="number">
      <span id="purchase-vial-price-label"></span>
      <small id="purchase-vial-price-help"></small>
      <p id="purchase-vial-preview" role="status"></p>
      <button id="purchase-vial-submit" type="submit"></button>
    </form>
    </body></html>"""


@pytest.fixture
def page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        tab = browser.new_page()
        errors = []
        tab.on("pageerror", lambda error: errors.append(str(error)))
        tab.set_content(fixture_html())
        tab.add_script_tag(path=str(SOURCE))
        yield tab, errors
        browser.close()


def test_quantity_and_price_update_for_each_package_size(page):
    tab, errors = page
    assert "1 individual vial" in tab.locator("#purchase-vial-preview").inner_text()
    tab.locator('[name="quantity"]').fill("4")
    tab.locator('[name="price_amount"]').fill("3.25")
    assert "$13.00" in tab.locator("#purchase-vial-preview").inner_text()

    tab.locator('[name="kit_size"]').select_option("5")
    assert tab.locator('[name="quantity"]').is_disabled()
    assert tab.locator('[name="kit_count"]').is_enabled()
    assert not tab.locator("#purchase-vial-kits-field").is_hidden()
    tab.locator('[name="kit_count"]').fill("2")
    tab.locator('[name="price_basis"]').select_option("per_half_kit")
    tab.locator('[name="price_amount"]').fill("12.01")
    assert "10 vials" in tab.locator("#purchase-vial-preview").inner_text()
    assert "$24.02" in tab.locator("#purchase-vial-preview").inner_text()
    assert tab.locator("#purchase-vial-submit").inner_text() == "Add 10 vials"

    tab.locator('[name="kit_size"]').select_option("10")
    assert tab.locator('[name="price_basis"]').input_value() == "per_vial"
    tab.locator('[name="price_basis"]').select_option("per_full_kit")
    assert "20 vials" in tab.locator("#purchase-vial-preview").inner_text()
    assert "$24.02" in tab.locator("#purchase-vial-preview").inner_text()
    assert not errors, errors


def test_invalid_price_and_quantity_show_guidance(page):
    tab, errors = page
    tab.locator('[name="quantity"]').fill("0")
    assert "valid quantity" in tab.locator("#purchase-vial-preview").inner_text()
    tab.locator('[name="quantity"]').fill("2")
    tab.locator('[name="price_amount"]').fill("-1")
    assert "nonnegative price" in tab.locator("#purchase-vial-preview").inner_text()
    assert not errors, errors


def test_purchase_ux_script_is_loaded_outside_title():
    html = TEMPLATE.read_text(encoding="utf-8")
    title = html.split("{% block title %}", 1)[1].split("{% endblock %}", 1)[0]
    content = html.split("{% block content %}", 1)[1]
    assert "<script" not in title
    assert 'src="/static/bulk_purchase_ux.js' in content
    assert 'src="/static/js/tracker-purchase-vials.js' in content
