"""Chromium checks for read-only Lab overview filtering and sorting.

Kept under tests/browser because the deployment's backend test gate
intentionally excludes Playwright dependencies.
"""
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "app/static/js/tracker-labs-overview.js"

HTML = """<!doctype html><html><body>
  <div id="labs-trend-controls">
    <input id="labs-analyte-search">
    <select id="labs-range-filter">
      <option value="all">All</option>
      <option value="outside">Outside</option>
      <option value="above">Above</option>
      <option value="below">Below</option>
      <option value="within">Within</option>
      <option value="unknown">No range</option>
    </select>
    <select id="labs-trend-sort">
      <option value="recent">Recent</option>
      <option value="name-asc">A-Z</option>
      <option value="name-desc">Z-A</option>
      <option value="results-desc">Most</option>
    </select>
    <button id="labs-trend-clear">Reset</button>
  </div>
  <p id="labs-trend-count"></p>
  <p id="labs-trend-empty" hidden>No results</p>
  <div id="labs-trend-grid">
    <article id="lab-tsh" data-labs-trend-card data-lab-name="TSH"
      data-lab-status="below" data-lab-date="2026-11-01" data-lab-results="3">TSH</article>
    <article id="lab-igf" data-labs-trend-card data-lab-name="IGF-1"
      data-lab-status="unknown" data-lab-date="2026-10-27" data-lab-results="2">IGF-1</article>
    <article id="lab-ferritin" data-labs-trend-card data-lab-name="Ferritin"
      data-lab-status="above" data-lab-date="2026-11-02" data-lab-results="1">Ferritin</article>
    <article id="lab-glucose" data-labs-trend-card data-lab-name="Glucose"
      data-lab-status="within" data-lab-date="2026-10-29" data-lab-results="4">Glucose</article>
  </div>
  <input id="labs-report-search">
  <button id="labs-reports-clear">Clear</button>
  <span id="labs-reports-count"></span>
  <p id="labs-reports-empty" hidden>No matches</p>
  <table id="labs-reports-table"><tbody>
    <tr id="report-one" data-labs-report-row data-lab-report-date="2026-11-01"
      data-lab-report-name="Current Diagnostics"><td>Nov 1 2026</td><td>Current Diagnostics</td></tr>
    <tr id="report-two" data-labs-report-row data-lab-report-date="2026-07-07"
      data-lab-report-name="Earlier Diagnostics"><td>Jul 7 2026</td><td>Earlier Diagnostics</td></tr>
  </tbody></table>
</body></html>"""


@pytest.fixture
def tab():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.set_content(HTML)
        page.add_script_tag(content=SCRIPT.read_text())
        yield page, errors
        browser.close()


def shown(page):
    return page.locator('[data-labs-trend-card]:not([hidden])').evaluate_all(
        "(nodes) => nodes.map(node => node.id)"
    )


def test_outside_range_and_reset(tab):
    page, errors = tab
    assert shown(page) == ["lab-ferritin", "lab-tsh", "lab-glucose", "lab-igf"]
    page.locator("#labs-range-filter").select_option("outside")
    assert shown(page) == ["lab-ferritin", "lab-tsh"]
    assert "2 of 4" in page.locator("#labs-trend-count").inner_text()
    page.locator("#labs-analyte-search").fill("TSH")
    assert shown(page) == ["lab-tsh"]
    page.locator("#labs-analyte-search").fill("not present")
    assert shown(page) == []
    assert page.locator("#labs-trend-empty").is_visible()
    page.locator("#labs-trend-clear").click()
    assert shown(page) == ["lab-ferritin", "lab-tsh", "lab-glucose", "lab-igf"]
    assert not errors, errors


def test_range_without_printed_reference_and_sort(tab):
    page, errors = tab
    page.locator("#labs-range-filter").select_option("unknown")
    assert shown(page) == ["lab-igf"]
    page.locator("#labs-range-filter").select_option("all")
    page.locator("#labs-trend-sort").select_option("results-desc")
    assert shown(page) == ["lab-glucose", "lab-tsh", "lab-igf", "lab-ferritin"]
    page.locator("#labs-trend-sort").select_option("name-asc")
    assert shown(page) == ["lab-ferritin", "lab-glucose", "lab-igf", "lab-tsh"]
    assert not errors, errors


def test_report_search_filters_without_altering_trends(tab):
    page, errors = tab
    page.locator("#labs-report-search").fill("2026-07")
    assert page.locator("#report-two").is_visible()
    assert page.locator("#report-one").is_hidden()
    assert "1 of 2" in page.locator("#labs-reports-count").inner_text()
    page.locator("#labs-report-search").fill("missing")
    assert page.locator("#labs-reports-empty").is_visible()
    page.locator("#labs-reports-clear").click()
    assert page.locator("#report-one").is_visible()
    assert page.locator("#report-two").is_visible()
    assert len(shown(page)) == 4
    assert not errors, errors
