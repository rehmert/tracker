"""Chromium regression tests for the read-only purchase-history review."""
import csv
from io import StringIO
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.browser

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "app/static/js/tracker-purchase-history-review.js"


def html(rows):
    return f"""<!doctype html><html><body><main>
      <div data-purchase-review-toolbar>
        <input data-purchase-search type="search">
        <select data-purchase-vendor><option value="">All vendors</option></select>
        <select data-purchase-status>
          <option value="all">All orders</option>
          <option value="needs-items">Needs items</option>
          <option value="has-items">Items recorded</option>
        </select>
        <input data-purchase-from type="date">
        <input data-purchase-through type="date">
        <button data-purchase-reset>Reset</button>
        <button data-purchase-export>Export filtered CSV</button>
      </div>
      <p data-purchase-date-error hidden>Invalid date range</p>
      <strong data-purchase-visible-count></strong>
      <strong data-purchase-needs-count></strong>
      <strong data-purchase-visible-total></strong>
      <span data-purchase-results></span>
      <p data-purchase-empty hidden>No matches</p>
      <table data-purchase-history data-currency="$">
        <thead><tr>
          <th data-purchase-sort="date">Date</th>
          <th data-purchase-sort="vendor">Vendor</th>
          <th data-purchase-sort="order">Order</th>
          <th data-purchase-sort="vials">Vials</th>
          <th data-purchase-sort="supplies">Supplies</th>
          <th data-purchase-sort="total">Total</th>
          <th>Next step</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </main></body></html>"""


ROWS = """
<tr id="purchase-1" data-purchase-row data-purchase-id="1"
  data-purchase-date="2026-11-03" data-purchase-vendor="=HYPERLINK(&quot;x&quot;)"
  data-purchase-order="INV-1" data-purchase-vials="0" data-purchase-supplies="0"
  data-purchase-total-cents="0" data-purchase-status="needs-items">
  <td>2026-11-03</td><td>=HYPERLINK("x")</td><td>INV-1</td>
  <td>0</td><td>0</td><td>$0.00</td><td>Needs items</td>
</tr>
<tr id="purchase-2" data-purchase-row data-purchase-id="2"
  data-purchase-date="2026-11-02" data-purchase-vendor="Other Supplier"
  data-purchase-order="INV-2" data-purchase-vials="2" data-purchase-supplies="0"
  data-purchase-total-cents="5000" data-purchase-status="has-items">
  <td>2026-11-02</td><td>Other Supplier</td><td>INV-2</td>
  <td>2</td><td>0</td><td>$50.00</td><td>Review items</td>
</tr>
<tr id="purchase-3" data-purchase-row data-purchase-id="3"
  data-purchase-date="2026-10-01" data-purchase-vendor="Vendor B"
  data-purchase-order="INV-3" data-purchase-vials="5" data-purchase-supplies="1"
  data-purchase-total-cents="12500" data-purchase-status="has-items">
  <td>2026-10-01</td><td>Vendor B</td><td>INV-3</td>
  <td>5</td><td>1</td><td>$125.00</td><td>Review items</td>
</tr>
"""


@pytest.fixture
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(headless=True)
        try:
            yield instance
        finally:
            instance.close()


def page(browser, rows=ROWS):
    tab = browser.new_page(accept_downloads=True)
    errors = []
    tab.on("pageerror", lambda e: errors.append(str(e)))
    tab.set_content(html(rows))
    tab.add_script_tag(content=SCRIPT.read_text())
    return tab, errors


def visible(tab):
    return tab.locator('[data-purchase-row]:not([hidden])').evaluate_all(
        "(rows) => rows.map(row => row.id)"
    )


def test_filters_and_visible_totals_and_reset(browser):
    tab, errors = page(browser)
    assert visible(tab) == ["purchase-1", "purchase-2", "purchase-3"]
    assert tab.locator("[data-purchase-visible-total]").inner_text() == "$175.00"
    assert tab.locator("[data-purchase-needs-count]").inner_text() == "1"
    assert "3 of 3" in tab.locator("[data-purchase-results]").inner_text()

    tab.locator("select[data-purchase-status]").select_option("needs-items")
    assert visible(tab) == ["purchase-1"]
    assert tab.locator("[data-purchase-visible-total]").inner_text() == "$0.00"
    assert tab.locator("[data-purchase-needs-count]").inner_text() == "1"

    tab.locator("select[data-purchase-status]").select_option("all")
    tab.locator("[data-purchase-vendor]").select_option("other supplier")
    assert visible(tab) == ["purchase-2"]
    assert tab.locator("[data-purchase-visible-total]").inner_text() == "$50.00"

    tab.locator("[data-purchase-vendor]").select_option("")
    tab.locator("[data-purchase-from]").fill("2026-11-02")
    tab.locator("[data-purchase-through]").fill("2026-11-03")
    assert visible(tab) == ["purchase-1", "purchase-2"]
    assert tab.locator("[data-purchase-visible-total]").inner_text() == "$50.00"

    tab.locator("[data-purchase-through]").fill("2026-11-01")
    assert tab.locator("[data-purchase-date-error]").is_visible()
    assert visible(tab) == []
    assert tab.locator("[data-purchase-export]").is_disabled()
    assert tab.locator("[data-purchase-empty]").is_visible()

    tab.locator("[data-purchase-reset]").click()
    assert visible(tab) == ["purchase-1", "purchase-2", "purchase-3"]
    assert tab.locator("[data-purchase-from]").input_value() == ""
    assert tab.locator("[data-purchase-through]").input_value() == ""
    assert tab.locator("[data-purchase-date-error]").is_hidden()
    assert tab.locator("[data-purchase-export]").is_enabled()
    assert tab.locator("[data-purchase-visible-total]").inner_text() == "$175.00"
    assert not errors, errors
    tab.close()


def test_sort_headers_and_search_preserved(browser):
    tab, errors = page(browser)
    tab.locator('[data-purchase-sort="vials"] button').click()
    assert visible(tab) == ["purchase-1", "purchase-2", "purchase-3"]
    assert tab.locator('[data-purchase-sort="vials"]').get_attribute(
        "aria-sort") == "ascending"

    tab.locator('[data-purchase-sort="vials"] button').click()
    assert visible(tab) == ["purchase-3", "purchase-2", "purchase-1"]
    tab.locator("[data-purchase-search]").fill("INV-2")
    assert visible(tab) == ["purchase-2"]
    assert not errors, errors
    tab.close()


def test_csv_uses_filtered_rows_and_escapes_vendor_formula(browser):
    tab, errors = page(browser)
    tab.locator("select[data-purchase-status]").select_option("needs-items")
    with tab.expect_download() as download:
        tab.locator("[data-purchase-export]").click()
    item = download.value
    assert item.suggested_filename == "tracker-purchase-history-filtered.csv"
    raw = Path(item.path()).read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    values = list(csv.reader(StringIO(raw.decode("utf-8-sig"))))
    assert len(values) == 2
    assert values[0][:4] == [
        "Purchase ID", "Date", "Vendor", "Order reference"
    ]
    assert values[1] == [
        "1", "2026-11-03", "'=HYPERLINK(\"x\")",
        "INV-1", "0", "0", "0.00", "Needs items"
    ]

    tab.locator("select[data-purchase-status]").select_option("has-items")
    with tab.expect_download() as download2:
        tab.locator("[data-purchase-export]").click()
    values = list(csv.reader(StringIO(
        Path(download2.value.path()).read_text(encoding="utf-8-sig")
    )))
    assert len(values) == 3
    assert [r[6] for r in values[1:]] == ["50.00", "125.00"]
    assert not errors, errors
    tab.close()


def test_no_orders_keeps_empty_state_and_disables_export(browser):
    tab, errors = page(browser,
        '<tr><td colspan="7" class="empty">No purchases yet.</td></tr>')
    assert tab.locator("[data-purchase-visible-count]").inner_text() == "0"
    assert tab.locator("[data-purchase-visible-total]").inner_text() == "$0.00"
    assert tab.locator("[data-purchase-export]").is_disabled()
    assert tab.locator("#purchase-1").count() == 0
    assert not errors, errors
    tab.close()
