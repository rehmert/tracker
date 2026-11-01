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
      <button id="bulk-jump-to-vials" type="button">Find vials</button>
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
          <div class="bulk-edit-navigation">
            <button type="button" data-bulk-focus-field="status">Status</button>
            <button type="button" data-bulk-focus-field="expires_on">Expiration</button>
            <button type="button" id="bulk-back-to-vials">Back to vials</button>
          </div>
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
            <details class="bulk-edit-group" data-dates><summary>Dates</summary>
              <label class="field bulk-edit-field" data-bulk-field="expires_on">
                <span>Expires on</span>
                <select name="mode_expires_on">
                  <option value="keep">Keep</option>
                  <option value="set">Set</option>
                  <option value="clear">Clear</option>
                </select>
                <input name="value_expires_on" type="date">
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
    # The bulk editor starts collapsed. Exercise the actual user workflow
    # rather than trying to fill an element hidden inside closed <details>.
    assert tab.locator("#bulk-open-editor").is_disabled()
    assert not tab.locator("#bulk-editor-panel").evaluate("(el) => el.open")
    tab.locator('.bulk-vial-check[value="1"]').check()
    tab.locator("#bulk-open-editor").click()
    assert tab.locator("#bulk-editor-panel").evaluate("(el) => el.open")
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



def review_script():
    source = TEMPLATE.read_text(encoding="utf-8")
    start = source.index("/* TRACKER_BULK_STAGE4_JS */")
    end = source.index("</script>", start)
    return source[start:end]


def review_html():
    return """<!doctype html><html><body>
      <form id="bulk-vials">
        <input id="bulk-preview-snapshot" type="hidden" name="bulk_preview_snapshot">
        <input class="bulk-vial-check" name="vial_ids" type="checkbox" checked value="1">
        <select name="mode_lot"><option value="set" selected>Set</option></select>
        <input name="value_lot" value="NEW">
        <button id="bulk-apply" type="submit">Review</button>
      </form>
      <dialog id="bulk-server-review">
        <p id="bulk-server-review-summary"></p>
        <p id="bulk-server-review-error"></p>
        <p id="bulk-review-field-summary"></p>
        <input id="bulk-review-search" type="search">
        <input id="bulk-review-show-unchanged" type="checkbox">
        <table><tbody id="bulk-server-review-rows"></tbody></table>
        <p id="bulk-review-visible-count"></p>
        <button id="bulk-review-more" type="button" hidden>Show 50 more</button>
        <button id="bulk-server-review-cancel">Cancel</button>
        <button id="bulk-server-review-confirm">Confirm and apply</button>
      </dialog>
    </body></html>"""


@pytest.mark.parametrize("all_unchanged", [False, True])
def test_server_review_shows_real_changes_by_default(all_unchanged):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        tab = browser.new_page()
        errors = []
        tab.on("pageerror", lambda error: errors.append(str(error)))
        tab.set_content(review_html())
        changed = not all_unchanged
        response = {
            "ok": True, "count": 2, "fields": 1, "snapshot": "saved-state",
            "rows": [
                {
                    "vial_id": 1, "compound": "A", "label": "One",
                    "field": "lot", "current": "OLD", "proposed": "NEW",
                    "changed": changed,
                },
                {
                    "vial_id": 2, "compound": "A", "label": "Two",
                    "field": "lot", "current": "NEW", "proposed": "NEW",
                    "changed": False,
                },
            ],
        }
        tab.evaluate("""data => {
            window.fetch = async () => ({
                ok: true,
                json: async () => data
            });
        }""", response)
        tab.add_script_tag(content=review_script())
        tab.locator("#bulk-apply").click()
        tab.locator("#bulk-server-review[open]").wait_for()
        assert tab.locator("#bulk-server-review").evaluate("(el) => el.open")
        assert tab.locator("#bulk-preview-snapshot").input_value() == "saved-state"
        if all_unchanged:
            assert tab.locator("#bulk-server-review-rows tr").count() == 0
            assert tab.locator("#bulk-server-review-confirm").is_disabled()
            assert "Nothing needs updating" in tab.locator(
                "#bulk-server-review-error"
            ).inner_text()
        else:
            assert tab.locator("#bulk-server-review-rows tr").count() == 1
            assert tab.locator("#bulk-server-review-confirm").is_enabled()
        assert "already matching" in tab.locator(
            "#bulk-server-review-summary"
        ).inner_text()
        tab.locator("#bulk-review-show-unchanged").check()
        assert tab.locator("#bulk-server-review-rows tr").count() == 2
        assert not errors, errors
        browser.close()

def test_editor_comes_after_inventory_table():
    html = TEMPLATE.read_text(encoding="utf-8")
    assert html.index('id="tracker-vials-sortable"') < html.index('id="bulk-editor-panel"')
    assert html.index('id="bulk-selection-tools"') < html.index('id="tracker-vials-sortable"')
    assert html.count('id="bulk-vials"') == 1
    assert 'form="bulk-vials"' in html
    assert 'data-bulk-focus-field="expires_on"' in html
    assert 'id="bulk-jump-to-vials"' in html


def test_quick_edit_navigation_opens_dates_and_updates_selection(page):
    tab, errors = page
    tab.locator('.bulk-vial-check[value="1"]').check()
    tab.locator("#bulk-open-editor").click()
    assert not tab.locator(".bulk-edit-group[data-dates]").evaluate("(el) => el.open")
    tab.locator('[data-bulk-focus-field="expires_on"]').click()
    assert tab.locator(".bulk-edit-group[data-dates]").evaluate("(el) => el.open")
    tab.locator('[name="value_expires_on"]').fill("2027-12-31")
    assert tab.locator('[name="mode_expires_on"]').input_value() == "set"
    tab.locator('[data-bulk-focus-field="status"]').click()
    assert tab.locator('[name="mode_status"]').input_value() == "keep"
    assert "1 field to update" in tab.locator("#bulk-edits-count").inner_text()
    tab.locator('[name="value_status"]').select_option("in_use")
    assert tab.locator('[name="mode_status"]').input_value() == "set"
    assert "2 fields to update" in tab.locator("#bulk-edits-count").inner_text()
    tab.locator("#bulk-back-to-vials").click()
    assert tab.locator('.bulk-vial-check[value="1"]').evaluate(
        "(el) => el === document.activeElement"
    )
    assert not errors, errors



def test_vial_checkboxes_still_submit_when_form_is_below_table(page):
    tab, errors = page
    tab.locator('.bulk-vial-check[value="2"]').check()
    payload = tab.locator("#bulk-vials").evaluate(
        "(form) => new FormData(form).getAll('vial_ids')"
    )
    assert payload == ["2"]
    assert not errors, errors


def test_jump_to_table_focuses_first_vial_checkbox(page):
    tab, errors = page
    tab.locator("#bulk-jump-to-vials").click()
    focused = tab.evaluate(
        "() => document.activeElement?.classList.contains('bulk-vial-check')"
    )
    assert focused
    assert not errors, errors


def test_large_bulk_review_is_progressive_and_search_is_visual_only():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        tab = browser.new_page()
        errors = []
        tab.on("pageerror", lambda error: errors.append(str(error)))
        tab.set_content(review_html())
        preview = {
            "ok": True, "count": 125, "fields": 1,
            "snapshot": "review-125",
            "rows": [
                {
                    "vial_id": i, "compound": "Sample",
                    "label": f"Distinct vial {i:03d}",
                    "field": "lot", "current": "A",
                    "proposed": "B", "changed": True,
                }
                for i in range(1, 126)
            ]
        }
        tab.evaluate("""data => {
            window.fetch = async () => ({
                ok: true, json: async () => data
            });
        }""", preview)
        tab.add_script_tag(content=review_script())
        tab.locator("#bulk-apply").click()
        tab.locator("#bulk-server-review[open]").wait_for()
        assert tab.locator("#bulk-server-review-rows tr").count() == 50
        assert "Showing 50 of 125" in tab.locator(
            "#bulk-review-visible-count").inner_text()
        assert "lot (125)" in tab.locator(
            "#bulk-review-field-summary").inner_text()
        tab.locator("#bulk-review-more").click()
        assert tab.locator("#bulk-server-review-rows tr").count() == 100
        tab.locator("#bulk-review-more").click()
        assert tab.locator("#bulk-server-review-rows tr").count() == 125
        assert tab.locator("#bulk-review-more").is_hidden()

        tab.locator("#bulk-review-search").fill("Distinct vial 117")
        assert tab.locator("#bulk-server-review-rows tr").count() == 1
        assert "117" in tab.locator("#bulk-server-review-rows").inner_text()
        assert tab.locator("#bulk-server-review-confirm").is_enabled()
        assert tab.locator("#bulk-preview-snapshot").input_value() == "review-125"
        assert "125 individual value change" in tab.locator(
            "#bulk-server-review-summary").inner_text()

        tab.locator("#bulk-review-search").fill("not in any vial")
        assert tab.locator("#bulk-server-review-rows tr").count() == 0
        assert "Showing 0 of 0" in tab.locator(
            "#bulk-review-visible-count").inner_text()
        assert tab.locator("#bulk-server-review-confirm").is_enabled()
        assert not errors, errors
        browser.close()
