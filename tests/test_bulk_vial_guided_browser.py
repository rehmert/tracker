"""Chromium regression checks for guided bulk-vial editing and persisted selection.

No production data, network, or live application are used.
"""
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/vials.html"
GUIDED = ROOT / "app/static/js/tracker-bulk-editor-guided.js"
SELECT = ROOT / "app/static/js/tracker-bulk-selection.js"


def editor_html():
    return """<!doctype html><html><body>
      <button id="bulk-select-all">Select all displayed</button>
      <button id="bulk-select-none">Clear selection</button>
      <button id="bulk-open-editor" disabled>Bulk edit selected</button>
      <span id="bulk-toolbar-count">0</span>
      <div id="bulk-selection-tools">
        <div class="inline">
          <select id="bulk7-compound"></select>
          <select id="bulk7-status"></select>
          <button id="bulk7-select">Select matching</button>
          <button id="bulk7-invert">Invert selection</button>
          <button id="bulk7-clear">Clear visible</button>
          <button id="bulk7-export">Export selected CSV</button>
        </div>
      </div>
      <p id="bulk7-summary"></p>
      <table id="tracker-vials-sortable"><thead><tr>
        <th><input id="bulk-all" type="checkbox"></th></tr></thead>
      <tbody>
        <tr data-attention-status="sealed">
          <td><input form="bulk-vials" class="bulk-vial-check" type="checkbox"
             name="vial_ids" value="1"></td>
          <td>Compound A</td><td><a>Vial A1</a></td>
        </tr>
        <tr data-attention-status="in_use">
          <td><input form="bulk-vials" class="bulk-vial-check" type="checkbox"
             name="vial_ids" value="2"></td>
          <td>Compound B</td><td><a>Vial B2</a></td>
        </tr>
      </tbody></table>
      <form id="bulk-vials">
        <input type="hidden" id="bulk-preview-snapshot" value="old">
        <details id="bulk-editor-panel">
          <div id="bulk-selected-preview"></div>
          <span id="bulk-count"></span>
          <div id="bulk-edit-field-groups">
            <details class="bulk-edit-group" open><summary>Identification</summary>
              <label class="field bulk-edit-field" data-bulk-field="lot">
                <span>Lot</span>
                <select name="mode_lot">
                  <option value="keep">Keep</option>
                  <option value="set">Set</option>
                  <option value="clear">Clear</option>
                </select>
                <input name="value_lot" type="text">
              </label>
              <label class="field bulk-edit-field" data-bulk-field="status">
                <span>Status</span>
                <select name="mode_status">
                  <option value="keep">Keep</option><option value="set">Set</option>
                </select>
                <select name="value_status">
                  <option value="sealed">Sealed</option><option value="in_use">In use</option>
                </select>
              </label>
            </details>
          </div>
          <strong id="bulk-edits-count"></strong>
          <span id="bulk-edits-details"></span>
          <button type="button" id="bulk-edits-reset">Reset edits</button>
          <button id="bulk-apply">Preview</button>
        </details>
      </form>
    </body></html>"""


@pytest.fixture
def page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        tab = context.new_page()
        errors = []
        tab.on("pageerror", lambda error: errors.append(str(error)))
        tab.route(
            "http://tracker-guided.test/*",
            lambda route: route.fulfill(
                status=200, content_type="text/html", body=editor_html()
            ),
        )
        tab.goto("http://tracker-guided.test/vials")
        tab.add_script_tag(path=str(SELECT))
        tab.add_script_tag(path=str(GUIDED))
        yield tab, errors
        context.close()
        browser.close()


def test_entering_field_value_automatically_opts_in(page):
    tab, errors = page
    assert tab.locator('[name="mode_lot"]').input_value() == "keep"
    assert "No changes requested" in tab.locator("#bulk-edits-count").inner_text()
    tab.locator('[name="value_lot"]').fill("LOT-NEW")
    assert tab.locator('[name="mode_lot"]').input_value() == "set"
    assert "1 field to update" in tab.locator("#bulk-edits-count").inner_text()
    assert tab.locator('[data-bulk-field="lot"]').evaluate(
        "(element) => element.classList.contains('bulk-edit-active')"
    )
    tab.locator('[name="mode_lot"]').select_option("clear")
    assert "Lot: Clear" in tab.locator("#bulk-edits-details").inner_text()
    tab.locator("#bulk-edits-reset").click()
    assert tab.locator('[name="mode_lot"]').input_value() == "keep"
    assert tab.locator('[name="value_lot"]').input_value() == ""
    assert "No changes requested" in tab.locator("#bulk-edits-count").inner_text()
    assert not errors, errors


def test_select_all_clear_and_cross_view_edit(page):
    tab, errors = page
    tab.locator("#bulk-select-all").click()
    assert tab.locator(".bulk-vial-check:checked").count() == 2
    assert "2 selected across all views" in tab.locator("#bulk7-summary").inner_text()
    tab.locator("#bulk-select-none").click()
    assert tab.locator(".bulk-vial-check:checked").count() == 0

    # A saved selection from another inventory filter is still editable.
    tab.evaluate("""() => {
      sessionStorage.setItem("tracker.bulkVials.selection.v1",
        JSON.stringify({"99": {id:"99", compound:"Other", label:"Vial 99", status:"sealed"}}));
    }""")
    tab.reload()
    tab.add_script_tag(path=str(SELECT))
    tab.add_script_tag(path=str(GUIDED))
    assert "1 selected across all views" in tab.locator("#bulk7-summary").inner_text()
    tab.locator("#bulk-open-editor").click()
    assert tab.locator("#bulk-editor-panel").evaluate("(el) => el.open")
    assert tab.locator('[data-bulk-remove-id="99"]').count() == 1
    tab.locator('[data-bulk-remove-id="99"]').click()
    assert "0 selected across all views" in tab.locator("#bulk7-summary").inner_text()
    assert tab.locator('#bulk-open-editor').is_disabled()
    assert not errors, errors


def test_grouped_fields_preserve_all_backend_form_names():
    source = TEMPLATE.read_text(encoding="utf-8")
    assert "Identification & status" in source
    assert "Recorded dates" in source
    assert "Notes & COA preferences" in source
    assert 'name="mode_{{ key }}"' in source
    assert 'name="value_{{ key }}"' in source
    assert "bulk-review-show-unchanged" in source
    assert "if (!entry.changed && !showUnchanged.checked) continue" in source
    assert "confirmButton.disabled = changed === 0" in source
    assert "value.disabled = mode.value === \"clear\"" in source
