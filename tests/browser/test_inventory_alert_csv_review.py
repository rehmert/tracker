"""Chromium checks for the filtered Inventory Alerts CSV and priority breakdown."""
import csv
from io import StringIO
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "app/static/js/tracker-inventory-alert-triage.js"


def alert_html(rows):
    return f"""<!doctype html><html><body>
    <main>
      <div class="scroll">
        <table class="alert-table"><thead>
          <tr><th>Priority</th><th>Category</th><th>Item</th>
              <th>Reason</th><th>Relevant date</th></tr>
        </thead><tbody>{rows}</tbody></table>
      </div>
    </main>
    </body></html>"""


ROWS = """
  <tr><td><span class="alert-critical">Critical</span></td>
    <td>Vial</td><td><a href="/vials/1">=HYPERLINK("x")</a></td>
    <td>Expiration passed</td><td>2026-11-01</td></tr>
  <tr><td><span class="alert-warning">Warning</span></td>
    <td>Supply</td><td><a href="/supplies">Needle, bulk</a></td>
    <td>Estimated depletion in 3.5 days</td><td>2026-11-06</td></tr>
  <tr><td><span class="alert-warning">Warning</span></td>
    <td>Vial</td><td><a href="/vials/2">Vitamin vials</a></td>
    <td>Beyond-use date in 7 days</td><td>2026-11-10</td></tr>
"""


@pytest.fixture
def browser():
    with sync_playwright() as p:
        instance = p.chromium.launch(headless=True)
        try:
            yield instance
        finally:
            instance.close()


def page_with_script(browser, rows=ROWS):
    page = browser.new_page(accept_downloads=True)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.set_content(alert_html(rows))
    page.add_script_tag(content=SCRIPT.read_text())
    return page, errors


def test_export_respects_filters_counts_and_preserves_csv_safety(browser):
    page, errors = page_with_script(browser)
    assert "3 of 3 alerts shown" in page.locator(".tracker-triage-count").inner_text()
    assert "1 critical" in page.locator(".tracker-triage-breakdown").inner_text()
    assert "2 warning" in page.locator(".tracker-triage-breakdown").inner_text()

    page.locator("#tracker-triage-priority").select_option("Critical")
    assert "1 of 3" in page.locator(".tracker-triage-count").inner_text()
    assert "1 critical" in page.locator(".tracker-triage-breakdown").inner_text()
    assert "warning" not in page.locator(".tracker-triage-breakdown").inner_text()

    with page.expect_download() as download:
        page.locator("#tracker-triage-export").click()
    item = download.value
    assert item.suggested_filename == "tracker-inventory-alerts-filtered.csv"
    raw = Path(item.path()).read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(StringIO(raw.decode("utf-8-sig"))))
    assert len(rows) == 2
    assert rows[0] == ["Priority", "Category", "Item", "Reason", "Relevant date"]
    assert rows[1] == [
        "Critical", "Vial", "'=HYPERLINK(\"x\")",
        "Expiration passed", "2026-11-01"
    ]

    page.locator("#tracker-triage-priority").select_option("")
    page.locator("#tracker-triage-category").select_option("Supply")
    with page.expect_download() as download:
        page.locator("#tracker-triage-export").click()
    records = list(csv.reader(StringIO(
        Path(download.value.path()).read_text(encoding="utf-8-sig")
    )))
    assert len(records) == 2
    assert records[1][2] == "Needle, bulk"
    assert records[1][3] == "Estimated depletion in 3.5 days"

    page.locator("#tracker-triage-search").fill("nothing matches")
    assert "0 of 3" in page.locator(".tracker-triage-count").inner_text()
    assert page.locator("#tracker-triage-export").is_disabled()
    assert page.locator(".tracker-triage-empty").is_visible()
    page.locator(".tracker-triage-reset").click()
    assert "3 of 3" in page.locator(".tracker-triage-count").inner_text()
    assert page.locator("#tracker-triage-export").is_enabled()
    assert not errors, errors
    page.close()


def test_empty_alerts_do_not_create_inert_toolbar(browser):
    page, errors = page_with_script(
        browser, '<tr><td colspan="5">No alerts for this horizon</td></tr>'
    )
    assert page.locator(".tracker-triage-toolbar").count() == 0
    assert page.locator("#tracker-triage-export").count() == 0
    assert page.locator(".alert-table").is_visible()
    assert not errors, errors
    page.close()
