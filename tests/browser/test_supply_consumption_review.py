"""Chromium checks for client-only supply consumption review and CSV."""
import csv
from io import StringIO
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "app/static/js/tracker-supply-consumption-review.js"


def html(body):
    return f"""<!doctype html><html><body>
      <section id="supply-consumption-review">
        <input id="supply-consumption-search" type="search">
        <select id="supply-consumption-kind"><option value="">All types</option></select>
        <select id="supply-consumption-filter">
          <option value="all">All</option>
          <option value="no-usage">No usage</option>
          <option value="zero-stock">Zero remaining</option>
          <option value="short-7">Up to 7 days</option>
          <option value="short-30">Up to 30 days</option>
          <option value="long-30">More than 30 days</option>
        </select>
        <select id="supply-consumption-sort">
          <option value="name-asc">Name A-Z</option>
          <option value="name-desc">Name Z-A</option>
          <option value="used-desc">Most used</option>
          <option value="remaining-asc">Least remaining</option>
          <option value="coverage-asc">Least coverage</option>
          <option value="coverage-desc">Most coverage</option>
        </select>
        <button id="supply-consumption-reset">Reset</button>
        <button id="supply-consumption-export">Export CSV</button>
        <strong id="supply-consumption-total"></strong>
        <strong id="supply-consumption-used"></strong>
        <strong id="supply-consumption-zero"></strong>
        <strong id="supply-consumption-short"></strong>
        <p id="supply-consumption-count"></p>
        <p id="supply-consumption-empty" hidden>No matches.</p>
        <table id="supply-consumption-table" data-period-days="30">
          <tbody>{body}</tbody>
        </table>
      </section>
    </body></html>"""


ROWS = """
<tr id="needles" data-supply-consumption-row
    data-supply-name="Needles" data-supply-kind="needle"
    data-supply-used="12" data-supply-remaining="8"
    data-supply-rate="0.4" data-supply-coverage="20">
    <td>Needles</td><td>Needle</td><td>12</td><td>8</td><td>0.4</td><td>20 days</td></tr>
<tr id="syringes" data-supply-consumption-row
    data-supply-name="Syringes" data-supply-kind="syringe"
    data-supply-used="5" data-supply-remaining="0"
    data-supply-rate="0.16666" data-supply-coverage="0">
    <td>Syringes</td><td>Syringe</td><td>5</td><td>0</td><td>0.16666</td><td>0 days</td></tr>
<tr id="bac" data-supply-consumption-row
    data-supply-name="BAC Water" data-supply-kind="bac_water"
    data-supply-used="0" data-supply-remaining="30"
    data-supply-rate="0" data-supply-coverage="">
    <td>BAC Water</td><td>Bac water</td><td>0</td><td>30</td><td>0</td><td>No usage</td></tr>
<tr id="formula" data-supply-consumption-row
    data-supply-name='=HYPERLINK("x")' data-supply-kind="other"
    data-supply-used="2" data-supply-remaining="5"
    data-supply-rate="0.06666" data-supply-coverage="75">
    <td>=HYPERLINK("x")</td><td>Other</td><td>2</td><td>5</td><td>0.06666</td><td>75 days</td></tr>
"""


@pytest.fixture
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(headless=True)
        try:
            yield instance
        finally:
            instance.close()


def open_page(browser, rows=ROWS):
    page = browser.new_page(accept_downloads=True)
    errors = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    page.set_content(html(rows))
    page.add_script_tag(content=SCRIPT.read_text())
    return page, errors


def shown(page):
    return page.locator('[data-supply-consumption-row]:not([hidden])').evaluate_all(
        "(rows) => rows.map(row => row.id)"
    )


def test_filters_stats_and_reset(browser):
    page, errors = open_page(browser)
    assert len(shown(page)) == 4
    assert page.locator("#supply-consumption-total").inner_text() == "4"
    assert page.locator("#supply-consumption-used").inner_text() == "3"
    assert page.locator("#supply-consumption-zero").inner_text() == "1"
    assert page.locator("#supply-consumption-short").inner_text() == "2"

    page.locator("#supply-consumption-filter").select_option("no-usage")
    assert shown(page) == ["bac"]
    page.locator("#supply-consumption-filter").select_option("zero-stock")
    assert shown(page) == ["syringes"]
    page.locator("#supply-consumption-filter").select_option("short-7")
    assert shown(page) == ["syringes"]
    page.locator("#supply-consumption-filter").select_option("short-30")
    assert shown(page) == ["needles", "syringes"]
    page.locator("#supply-consumption-filter").select_option("long-30")
    assert shown(page) == ["formula"]

    page.locator("#supply-consumption-filter").select_option("all")
    page.locator("#supply-consumption-kind").select_option("needle")
    assert shown(page) == ["needles"]
    page.locator("#supply-consumption-kind").select_option("")
    page.locator("#supply-consumption-search").fill("not listed")
    assert shown(page) == []
    assert page.locator("#supply-consumption-empty").is_visible()
    assert page.locator("#supply-consumption-export").is_disabled()

    page.locator("#supply-consumption-reset").click()
    assert len(shown(page)) == 4
    assert page.locator("#supply-consumption-reset").is_disabled()
    assert page.locator("#supply-consumption-export").is_enabled()
    assert not errors, errors
    page.close()


def test_missing_coverage_sorts_last_and_most_used_first(browser):
    page, errors = open_page(browser)
    page.locator("#supply-consumption-sort").select_option("coverage-asc")
    assert shown(page) == ["syringes", "needles", "formula", "bac"]
    page.locator("#supply-consumption-sort").select_option("coverage-desc")
    assert shown(page) == ["formula", "needles", "syringes", "bac"]
    page.locator("#supply-consumption-sort").select_option("used-desc")
    assert shown(page) == ["needles", "syringes", "formula", "bac"]
    assert not errors, errors
    page.close()


def test_filtered_csv_preserves_numeric_values_and_escapes_formula(browser):
    page, errors = open_page(browser)
    page.locator("#supply-consumption-filter").select_option("long-30")
    with page.expect_download() as dl:
        page.locator("#supply-consumption-export").click()
    item = dl.value
    assert item.suggested_filename == "tracker-supply-consumption-filtered.csv"
    raw = Path(item.path()).read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    data = list(csv.reader(StringIO(raw.decode("utf-8-sig"))))
    assert len(data) == 2
    assert data[0][:4] == ["Period days", "Supply", "Type", "Used in period"]
    assert data[1] == [
        "30", "'=HYPERLINK(\"x\")", "Other", "2", "5",
        "0.06666", "75", "Historical rate estimate"
    ]
    page.locator("#supply-consumption-filter").select_option("no-usage")
    with page.expect_download() as dl:
        page.locator("#supply-consumption-export").click()
    data = list(csv.reader(StringIO(
        Path(dl.value.path()).read_text(encoding="utf-8-sig")
    )))
    assert len(data) == 2
    assert data[1][1] == "BAC Water"
    assert data[1][6] == ""
    assert data[1][7] == "No recorded usage in period"
    assert not errors, errors
    page.close()


def test_empty_table_does_not_show_export(browser):
    page, errors = open_page(
        browser, '<tr><td colspan="6">No supplies recorded.</td></tr>'
    )
    assert page.locator("#supply-consumption-total").inner_text() == "0"
    assert page.locator("#supply-consumption-export").is_disabled()
    assert page.locator("#supply-consumption-empty").is_hidden()
    assert shown(page) == []
    assert not errors, errors
    page.close()
