"""Isolated Chromium checks for Vitals CSV and empty-result controls."""
import csv
import io
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "app/static/js/tracker-vitals-tools.js"


def html(table_rows):
    return f"""<!doctype html><html><body>
      <div data-vitals-toolbar>
        <label><input data-vitals-search type="search"></label>
        <label><select data-vitals-type>
          <option value="all">All</option><option value="weight">Weight</option>
          <option value="bp">BP</option><option value="pulse">Pulse</option>
        </select></label>
        <label><input data-vitals-from type="date"></label>
        <label><input data-vitals-through type="date"></label>
        <label><select data-vitals-sort>
          <option value="date-desc">Newest</option>
          <option value="date-asc">Oldest</option>
        </select></label>
        <button data-vitals-reset>Reset</button>
        <button data-vitals-export>Export CSV</button>
        <span data-vitals-count></span>
      </div>
      <p data-vitals-date-error hidden>Invalid dates</p>
      <div>
        <strong data-vitals-weight-compare>—</strong>
        <strong data-vitals-bp-compare>—</strong>
        <strong data-vitals-pulse-compare>—</strong>
      </div>
      <table data-vitals-table data-vitals-weight-unit="lb">
        <thead><tr><th>When</th><th>Weight</th><th>BP</th>
        <th>Pulse</th><th>Context</th><th>Notes</th><th>Actions</th></tr></thead>
        <tbody>{table_rows}</tbody>
      </table>
      <nav data-reading-pager hidden><button data-reading-prev>Previous</button><span data-reading-page></span><button data-reading-next>Next</button></nav>
      <table data-vitals-dose-table><tbody>{''.join(f'<tr><td>Dose group {i}</td></tr>' for i in range(8))}</tbody></table>
      <nav data-dose-pager hidden><button data-dose-prev>Previous</button><span data-dose-page></span><button data-dose-next>Next</button></nav>
      <table data-vitals-marker-table><tbody>{''.join(f'<tr><td>Event {i}</td></tr>' for i in range(12))}</tbody></table>
      <nav data-marker-pager hidden><button data-marker-prev>Previous</button><span data-marker-page></span><button data-marker-next>Next</button></nav>
    </body></html>"""


@pytest.fixture
def browser():
    with sync_playwright() as playwright:
        launched = playwright.chromium.launch(headless=True)
        try:
            yield launched
        finally:
            launched.close()


def test_csv_has_iso_dates_and_weight_unit(browser):
    page = browser.new_page(accept_downloads=True)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    rows = '''
    <tr data-vitals-when="2026-10-31T09:15:00">
      <td>2026-10-31 09:15 AM EDT</td><td>180.0</td><td>120/80</td>
      <td>70</td><td>Before coffee</td><td>=HYPERLINK("x")</td><td>Edit</td>
    </tr>
    <tr data-vitals-when="2026-10-30T08:00:00">
      <td>2026-10-30 08:00 AM EDT</td><td>181.0</td><td>—</td>
      <td>—</td><td>Earlier</td><td>Fine</td><td>Edit</td>
    </tr>'''
    page.set_content(html(rows))
    page.add_script_tag(path=str(SCRIPT))
    assert "2 of 2 readings" in page.locator("[data-vitals-count]").inner_text()
    with page.expect_download() as info:
        page.locator("[data-vitals-export]").click()
    raw = Path(info.value.path()).read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    parsed = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    assert parsed[0][:2] == ["When (local)", "Weight (lb)"]
    assert parsed[1][0] == "2026-10-31T09:15:00"
    assert parsed[1][5] == "'=HYPERLINK(\"x\")"
    assert not errors, errors
    page.close()


def test_empty_table_shows_zero_and_disables_csv(browser):
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.set_content(html('<tr><td colspan="7" class="empty">No readings in this range.</td></tr>'))
    page.add_script_tag(path=str(SCRIPT))
    assert page.locator("[data-vitals-count]").inner_text() == "0 of 0 readings"
    assert page.locator("[data-vitals-export]").is_disabled()
    assert not errors, errors
    page.close()


def test_date_filters_are_inclusive_and_reset_restores_readings(browser):
    page = browser.new_page(accept_downloads=True)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    rows = '''
    <tr data-vitals-when="2026-11-03T19:45:00">
      <td>Nov 3 Evening</td><td>179.0</td><td>119/79</td>
      <td>72</td><td>Evening</td><td>Fine</td><td>Edit</td>
    </tr>
    <tr data-vitals-when="2026-11-03T08:15:00">
      <td>Nov 3 Morning</td><td>180.0</td><td>120/80</td>
      <td>73</td><td>Morning</td><td>Good</td><td>Edit</td>
    </tr>
    <tr data-vitals-when="2026-10-31T08:00:00">
      <td>Oct 31</td><td>183.0</td><td>130/90</td>
      <td>80</td><td>Earlier</td><td>Fine</td><td>Edit</td>
    </tr>'''
    page.set_content(html(rows))
    page.add_script_tag(path=str(SCRIPT))
    assert "183.0 → 179.0 lb (-4.0 lb)" in page.locator(
        "[data-vitals-weight-compare]").inner_text()
    assert "130/90 → 119/79 mmHg" in page.locator(
        "[data-vitals-bp-compare]").inner_text()
    assert "80 → 72 bpm (-8 bpm)" in page.locator(
        "[data-vitals-pulse-compare]").inner_text()

    page.locator("[data-vitals-from]").fill("2026-11-03")
    page.locator("[data-vitals-through]").fill("2026-11-03")
    assert "2 of 3 readings" in page.locator("[data-vitals-count]").inner_text()
    assert "180.0 → 179.0 lb (-1.0 lb)" in page.locator(
        "[data-vitals-weight-compare]").inner_text()

    with page.expect_download() as info:
        page.locator("[data-vitals-export]").click()
    raw = Path(info.value.path()).read_bytes()
    parsed = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    assert len(parsed) == 3
    assert all(value[0].startswith("2026-11-03") for value in parsed[1:])
    assert not errors, errors
    page.close()


def test_invalid_date_range_disables_export_and_reset_clears_dates(browser):
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    rows = '''
    <tr data-vitals-when="2026-11-03T08:15:00">
      <td>Nov 3</td><td>180.0</td><td>120/80</td>
      <td>73</td><td>Morning</td><td>Good</td><td>Edit</td>
    </tr>
    <tr data-vitals-when="2026-10-31T08:00:00">
      <td>Oct 31</td><td>183.0</td><td>—</td>
      <td>—</td><td>Earlier</td><td>Fine</td><td>Edit</td>
    </tr>'''
    page.set_content(html(rows))
    page.add_script_tag(path=str(SCRIPT))
    page.locator("[data-vitals-from]").fill("2026-11-03")
    page.locator("[data-vitals-through]").fill("2026-11-01")

    assert page.locator("[data-vitals-date-error]").is_visible()
    assert "0 of 2 readings" in page.locator("[data-vitals-count]").inner_text()
    assert page.locator("[data-vitals-export]").is_disabled()
    assert "No matching measurements" in page.locator(
        "[data-vitals-weight-compare]").inner_text()

    page.locator("[data-vitals-reset]").click()
    assert page.locator("[data-vitals-from]").input_value() == ""
    assert page.locator("[data-vitals-through]").input_value() == ""
    assert page.locator("[data-vitals-date-error]").is_hidden()
    assert "2 of 2 readings" in page.locator("[data-vitals-count]").inner_text()
    assert page.locator("[data-vitals-export]").is_enabled()
    assert not errors, errors
    page.close()


def test_compare_uses_timestamps_not_table_sort_order(browser):
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    rows = '''
    <tr data-vitals-when="2026-11-03T08:15:00">
      <td>Nov 3</td><td>180.0</td><td>120/80</td>
      <td>73</td><td>Morning</td><td>Good</td><td>Edit</td>
    </tr>
    <tr data-vitals-when="2026-10-31T08:00:00">
      <td>Oct 31</td><td>183.0</td><td>130/90</td>
      <td>80</td><td>Earlier</td><td>Fine</td><td>Edit</td>
    </tr>'''
    page.set_content(html(rows))
    page.add_script_tag(path=str(SCRIPT))
    original_summary = page.locator(
        "[data-vitals-weight-compare]").inner_text()

    page.locator("[data-vitals-sort]").select_option("date-asc")
    assert page.locator("[data-vitals-weight-compare]").inner_text() == original_summary
    assert "183.0 → 180.0 lb (-3.0 lb)" in original_summary
    assert not errors, errors
    page.close()


def test_784_independent_pagers_and_all_matching_export(browser):
    page = browser.new_page(accept_downloads=True)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    rows = "".join(
        f'<tr id="vital-reading-{i}" data-vitals-when="2026-11-{i:02d}T08:00:00">'
        f'<td>Day {i}</td><td>{170+i}</td><td>120/80</td><td>70</td><td>Context</td>'
        f'<td data-vitals-full-notes="Hidden note {i}">More</td><td>Edit</td></tr>'
        for i in range(12, 0, -1)
    )
    page.set_content(html(rows))
    page.add_script_tag(path=str(SCRIPT))
    readings = page.locator("[data-vitals-table] tbody tr:not([hidden])")
    doses = page.locator("[data-vitals-dose-table] tbody tr:not([hidden])")
    assert readings.count() == doses.count() == 5
    assert readings.first.get_attribute("id") == "vital-reading-12"
    assert page.locator("[data-reading-page]").inner_text() == "1–5 of 12"
    page.locator("[data-reading-next]").click()
    assert readings.first.get_attribute("id") == "vital-reading-7"
    assert doses.first.inner_text() == "Dose group 0"
    page.locator("[data-dose-next]").click()
    assert doses.count() == 3
    assert readings.first.get_attribute("id") == "vital-reading-7"
    page.locator("[data-reading-next]").click()
    assert readings.count() == 2
    assert page.locator("[data-reading-next]").is_disabled()
    with page.expect_download() as info:
        page.locator("[data-vitals-export]").click()
    data = list(csv.reader(io.StringIO(Path(info.value.path()).read_text(encoding="utf-8-sig"))))
    assert len(data) == 13
    assert data[1][5] == "Hidden note 12"
    assert data[-1][5] == "Hidden note 1"
    page.locator("[data-vitals-search]").fill("Hidden note 1")
    assert readings.count() == 4
    assert page.locator("[data-reading-pager]").is_hidden()
    assert doses.count() == 3
    page.locator("[data-vitals-reset]").click()
    assert readings.count() == 5
    assert readings.first.get_attribute("id") == "vital-reading-12"
    assert not errors, errors
    page.close()


def test_785_event_pagination_is_independent(browser):
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    rows = "".join(
        f'<tr data-vitals-when="2026-11-{i:02d}T08:00:00"><td>Day {i}</td><td>180</td>'
        '<td>120/80</td><td>70</td><td>Context</td><td></td><td>Edit</td></tr>'
        for i in range(12, 0, -1)
    )
    page.set_content(html(rows))
    page.add_script_tag(path=str(SCRIPT))
    markers = page.locator("[data-vitals-marker-table] tbody tr:not([hidden])")
    doses = page.locator("[data-vitals-dose-table] tbody tr:not([hidden])")
    readings = page.locator("[data-vitals-table] tbody tr:not([hidden])")
    assert markers.count() == doses.count() == readings.count() == 5
    assert markers.first.inner_text() == "Event 0"
    assert page.locator("[data-marker-prev]").is_disabled()
    assert page.locator("[data-marker-page]").inner_text() == "1–5 of 12"
    page.locator("[data-marker-next]").click()
    assert markers.first.inner_text() == "Event 5"
    page.locator("[data-marker-next]").click()
    assert markers.count() == 2
    assert page.locator("[data-marker-next]").is_disabled()
    page.locator("[data-dose-next]").click()
    page.locator("[data-reading-next]").click()
    assert markers.first.inner_text() == "Event 10"
    page.locator("[data-marker-prev]").click()
    assert markers.count() == 5
    assert markers.first.inner_text() == "Event 5"
    assert doses.first.inner_text() == "Dose group 5"
    assert readings.first.locator("td").first.inner_text() == "Day 7"
    page.locator("[data-vitals-reset]").click()
    assert markers.first.inner_text() == "Event 5"
    assert not errors, errors
    page.close()


def test_786_compact_vitals_rows_preserve_mobile_actions(browser):
    page = browser.new_page(viewport={"width": 1100, "height": 800})
    css = ROOT / "app/static/css/tracker-vitals-tools.css"
    rows = "".join(
        f'<tr data-vitals-when="2026-11-{i:02d}T08:00:00"><td>Day {i}</td><td>180</td>'
        '<td>120/80</td><td>70</td><td>Context</td><td class="vitals-notes783"><a href="#note">More</a></td>'
        '<td class="vitals-actions783"><form style="display:inline"><button>Edit</button></form><button>Delete</button></td></tr>'
        for i in range(8, 0, -1)
    )
    markup = html(rows).replace("<body>", '<body><main id="main-content">').replace("</body>", "</main></body>")
    page.set_content(markup)
    page.add_style_tag(content="table { border-collapse:collapse; font-size:16px; } td,th { padding:10px; line-height:1.5; } button { padding:8px; }")
    page.add_style_tag(path=str(css))
    page.add_script_tag(path=str(SCRIPT))
    for selector in ("[data-vitals-table]", "[data-vitals-dose-table]", "[data-vitals-marker-table]"):
        table = page.locator(selector)
        cell = table.locator("tbody tr:not([hidden]) td").first
        assert float(cell.evaluate("(el) => parseFloat(getComputedStyle(el).paddingTop)")) <= 3
        assert table.locator("tbody tr:not([hidden])").count() == 5
        assert table.locator("tbody tr[hidden]").first.bounding_box() is None
    assert page.locator("[data-vitals-table] tbody tr:not([hidden])").first.bounding_box()["height"] <= 36
    page.set_viewport_size({"width": 390, "height": 800})
    reading = page.locator("[data-vitals-table] tbody tr:not([hidden])").first
    assert reading.bounding_box()["height"] <= 125
    assert reading.locator("button").first.bounding_box()["height"] >= 44
    page.locator("[data-marker-next]").click()
    assert page.locator("[data-vitals-marker-table] tbody tr:not([hidden])").count() == 5
    page.close()
