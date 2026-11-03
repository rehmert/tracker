"""Chromium UI regression checks for read-only lab comparison reviewing."""
import csv
from io import StringIO
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.browser

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "app/static/js/tracker-lab-compare-review.js"


def page_html():
    return """<!doctype html><html><body>
    <section id="lab-compare-results" data-report-a-date="2026-11-03"
             data-report-b-date="2026-07-07">
      <div id="lab-compare-toolbar">
        <input id="lab-compare-search" type="search">
        <select id="lab-compare-filter">
          <option value="all">All</option>
          <option value="comparable">Comparable</option>
          <option value="different">Different</option>
          <option value="same">Same</option>
          <option value="needs-review">Review</option>
          <option value="incompatible">Incompatible</option>
          <option value="only-a">Only A</option>
          <option value="only-b">Only B</option>
        </select>
        <select id="lab-compare-sort">
          <option value="name-asc">A–Z</option>
          <option value="name-desc">Z–A</option>
          <option value="review-first">Review first</option>
        </select>
        <button id="lab-compare-reset">Reset</button>
        <button id="lab-compare-export">Export filtered CSV</button>
      </div>
      <p id="lab-compare-count"></p>
      <p id="lab-compare-empty" hidden>No matches.</p>
      <table id="lab-compare-table"><tbody>
        <tr id="ferritin" data-lab-compare-row data-analyte="Ferritin"
            data-state="incompatible" data-a-value="200" data-a-unit="ng/mL"
            data-b-value="250" data-b-unit="mg/L"
            data-b-converted="" data-delta="">
            <td>Ferritin</td><td>200</td><td>250</td></tr>
        <tr id="testosterone" data-lab-compare-row data-analyte="Testosterone"
            data-state="different" data-a-value="600" data-a-unit="ng/dL"
            data-b-value="20.8" data-b-unit="nmol/L"
            data-b-converted="599.94" data-delta="0.06">
            <td>Testosterone</td><td>600</td><td>20.8</td></tr>
        <tr id="tsh" data-lab-compare-row data-analyte="TSH"
            data-state="same" data-a-value="0.2" data-a-unit="mIU/L"
            data-b-value="0.2" data-b-unit="mIU/L"
            data-b-converted="0.2" data-delta="0">
            <td>TSH</td><td>0.2</td><td>0.2</td></tr>
        <tr id="albumin" data-lab-compare-row data-analyte="Albumin"
            data-state="only-a" data-a-value="4.1" data-a-unit="g/dL"
            data-b-value="" data-b-unit=""
            data-b-converted="" data-delta="">
            <td>Albumin</td><td>4.1</td><td>—</td></tr>
        <tr id="psa" data-lab-compare-row data-analyte="PSA"
            data-state="only-b" data-a-value="" data-a-unit=""
            data-b-value="0.54" data-b-unit="ng/mL"
            data-b-converted="" data-delta="">
            <td>PSA</td><td>—</td><td>0.54</td></tr>
        <tr id="formula" data-lab-compare-row data-analyte='=HYPERLINK("x")'
            data-state="different" data-a-value="-3.5" data-a-unit="units"
            data-b-value="-2" data-b-unit="units"
            data-b-converted="-2" data-delta="-1.5">
            <td>Formula-like analyte</td><td>-3.5</td><td>-2</td></tr>
      </tbody></table>
    </section>
    </body></html>"""


@pytest.fixture
def ui():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.set_content(page_html())
        page.add_script_tag(content=SCRIPT.read_text())
        yield page, errors
        browser.close()


def displayed(page):
    return page.locator('[data-lab-compare-row]:not([hidden])').evaluate_all(
        "(elements) => elements.map(item => item.id)"
    )


def test_missing_and_incompatible_review_filter_and_reset(ui):
    page, errors = ui
    assert len(displayed(page)) == 6
    page.locator("#lab-compare-filter").select_option("needs-review")
    assert displayed(page) == ["albumin", "ferritin", "psa"]
    assert "3 of 6" in page.locator("#lab-compare-count").inner_text()

    page.locator("#lab-compare-filter").select_option("comparable")
    assert displayed(page) == ["formula", "testosterone", "tsh"]

    page.locator("#lab-compare-search").fill("TSH")
    assert displayed(page) == ["tsh"]
    page.locator("#lab-compare-search").fill("not present")
    assert displayed(page) == []
    assert page.locator("#lab-compare-empty").is_visible()
    assert page.locator("#lab-compare-export").is_disabled()

    page.locator("#lab-compare-reset").click()
    assert len(displayed(page)) == 6
    assert page.locator("#lab-compare-reset").is_disabled()
    assert not errors, errors


def test_sort_by_review_priority_and_name(ui):
    page, errors = ui
    page.locator("#lab-compare-sort").select_option("review-first")
    assert displayed(page)[:3] == ["ferritin", "albumin", "psa"]
    page.locator("#lab-compare-sort").select_option("name-desc")
    assert displayed(page)[0] == "tsh"
    assert not errors, errors


def test_filtered_csv_preserves_numeric_delta_and_escapes_formula(ui):
    page, errors = ui
    page.locator("#lab-compare-filter").select_option("different")
    assert displayed(page) == ["formula", "testosterone"]
    with page.expect_download() as download:
        page.locator("#lab-compare-export").click()
    item = download.value
    assert item.suggested_filename == "tracker-lab-report-comparison.csv"
    data = Path(item.path()).read_bytes()
    assert data.startswith(b"\xef\xbb\xbf")
    lines = list(csv.reader(StringIO(data.decode("utf-8-sig"))))
    assert len(lines) == 3
    assert lines[0][:3] == ["Report A date", "Report B date", "Analyte"]
    assert lines[1][:3] == ["2026-11-03", "2026-07-07", "'=HYPERLINK(\"x\")"]
    assert lines[1][3:6] == ["-3.5", "units", "-2"]
    assert lines[1][8] == "-1.5"  # Negative numeric values remain numeric.
    assert lines[1][-1] == "Nonzero difference"
    assert lines[2][2] == "Testosterone"
    assert not errors, errors


def test_empty_comparison_disables_export():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.set_content(page_html().replace(
            page_html().split("<tbody>", 1)[1].split("</tbody>", 1)[0], ""
        ))
        page.add_script_tag(content=SCRIPT.read_text())
        assert page.locator("#lab-compare-export").is_disabled()
        assert "0 of 0" in page.locator("#lab-compare-count").inner_text()
        assert page.locator("#lab-compare-empty").is_visible()
        assert not errors, errors
        browser.close()
