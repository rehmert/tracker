"""Release 731: medication half-tablet controls in real Chromium.

Browser form-data checks use a disposable mock page and never save user data.
"""
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / "app/static/js/tracker-regimen-tablets731.js"
pytestmark = pytest.mark.browser

HTML = """<!doctype html><html><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}body{margin:0;padding:12px;font:16px sans-serif}
.reg731-panel{border:1px solid #aaa;border-radius:8px;padding:12px;display:grid;gap:8px}
.reg731-fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,175px),1fr));gap:8px}
.reg731-panel [hidden]{display:none!important}
.reg731-panel :is(input,select){min-height:44px;font-size:16px}
.field{display:grid;gap:5px}input,select{max-width:100%;width:100%}
</style></head><body><main>
<form id="schedule" method="post" action="/regimen/schedules">
<select name="item_id" data-reg731-item>
  <option value="1" data-reg731-kind="supplement">Vitamin</option>
  <option value="2" data-reg731-kind="medication" data-reg731-strength="20">Example Tablet</option>
</select>
<fieldset class="reg731-panel" data-reg731-panel data-reg731-type="schedule">
<select name="tablet_mode" data-reg731-mode>
<option value="manual" selected>Manual</option>
<option value="tablet">Tablet fractions</option></select>
<div data-reg731-manual><input name="amount" value="2 capsules" required></div>
<div data-reg731-tablet hidden>
<div class="reg731-fields">
<label class="field">Strength <input name="tablet_strength_mg" data-reg731-strength type="number" value=""></label>
<label class="field">Prescribed <input name="prescribed_dose_mg" data-reg731-prescribed type="number" value=""></label>
<label class="field">Count <input name="tablets_planned" data-reg731-count type="number" value="0.5"></label>
</div>
<output data-reg731-preview></output></div>
</fieldset><button type="submit">Save</button>
</form>
<form id="history" method="post" action="/regimen/entries/42/edit">
<fieldset class="reg731-panel" data-reg731-panel data-reg731-kind="medication" data-reg731-type="entry">
<select name="tablet_mode" data-reg731-mode><option value="manual">Manual</option>
<option value="tablet" selected>Tablet</option></select>
<div data-reg731-manual><input name="amount" value="0.5 tablets (10 mg)"></div>
<div data-reg731-tablet hidden>
<input data-reg731-strength name="tablet_strength_mg" value="20" type="number">
<input data-reg731-prescribed name="prescribed_dose_mg" value="10" type="number">
<input data-reg731-count name="tablet_count" value="0.5" type="number">
<output data-reg731-preview></output>
</div></fieldset><button type="submit">Save correction</button>
</form>
<form id="due" method="post" action="/regimen/entries">
<select name="outcome"><option value="taken">Taken</option><option value="skipped">Skipped</option></select>
<input name="tablet_mode" type="hidden" value="tablet">
<div class="reg731-panel" data-reg731-due data-reg731-strength="20" data-reg731-prescribed="10">
<input name="tablet_count" data-reg731-count type="number" value="0.5">
<output data-reg731-preview></output>
</div><button type="submit">Record</button>
</form>
<script>__SCRIPT__</script></main></body></html>"""


@pytest.fixture
def tab():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_content(HTML.replace("__SCRIPT__", JS.read_text()))
            yield page, errors
        finally:
            browser.close()


def test_731_half_tablet_entry_requires_real_medication_and_submits_quantities(tab):
    page, errors = tab
    form = page.locator("#schedule")
    mode = form.locator('[name="tablet_mode"]')
    tablet_option = mode.locator('option[value="tablet"]')
    expect(tablet_option).to_be_disabled()
    expect(form.locator('[name="amount"]')).to_be_enabled()
    form.locator('[name="item_id"]').select_option("2")
    expect(tablet_option).to_be_enabled()
    mode.select_option("tablet")
    expect(form.locator('[name="amount"]')).to_be_disabled()
    strength = form.locator('[name="tablet_strength_mg"]')
    expect(strength).to_have_value("20")
    form.locator('[name="prescribed_dose_mg"]').fill("10")
    expect(form.locator('[data-reg731-preview]')).to_contain_text(
        "0.5 tablets × 20 mg = 10 mg. Ordered: 10 mg."
    )
    data = form.evaluate(
        "(el) => Object.fromEntries(new FormData(el).entries())"
    )
    assert data["tablet_mode"] == "tablet"
    assert data["tablet_strength_mg"] == "20"
    assert data["prescribed_dose_mg"] == "10"
    assert data["tablets_planned"] == "0.5"
    assert "amount" not in data

    form.locator('[name="prescribed_dose_mg"]').fill("15")
    expect(form.locator('[data-reg731-preview]')).to_contain_text(
        "Does not match order"
    )
    mode.select_option("manual")
    expect(form.locator('[name="amount"]')).to_be_enabled()
    data = form.evaluate(
        "(el) => Object.fromEntries(new FormData(el).entries())"
    )
    assert data["amount"] == "2 capsules"
    assert "tablets_planned" not in data
    assert not errors, errors


def test_731_historical_correction_and_due_do_not_rewrite_prescription(tab):
    page, errors = tab
    history = page.locator("#history")
    expect(history.locator('[name="amount"]')).to_be_disabled()
    expect(history.locator('[data-reg731-preview]')).to_contain_text(
        "0.5 tablets × 20 mg = 10 mg"
    )
    history.locator('[name="tablet_count"]').fill("0.25")
    expect(history.locator('[data-reg731-preview]')).to_contain_text(
        "0.25 tablets × 20 mg = 5 mg. Ordered: 10 mg."
    )
    fields = history.evaluate(
        "(el) => Object.fromEntries(new FormData(el).entries())"
    )
    assert fields["prescribed_dose_mg"] == "10"
    assert fields["tablet_count"] == "0.25"
    assert "amount" not in fields

    due = page.locator("#due")
    expect(due.locator('[data-reg731-preview]')).to_contain_text(
        "0.5 tablets = 10 mg taken."
    )
    due.locator('[name="tablet_count"]').fill("0.25")
    expect(due.locator('[data-reg731-preview]')).to_contain_text(
        "0.25 tablets = 5 mg taken. Ordered: 10 mg."
    )
    due.locator('[name="outcome"]').select_option("skipped")
    expect(due.locator('[data-reg731-preview]')).to_contain_text(
        "no tablets recorded as taken"
    )
    assert not errors, errors


@pytest.mark.parametrize("width", (320, 390, 760, 1024))
def test_731_tablet_controls_have_mobile_touch_targets_and_no_overflow(width):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": width, "height": 844})
            page.set_content(HTML.replace("__SCRIPT__", JS.read_text()))
            page.locator("#schedule [name='item_id']").select_option("2")
            page.locator("#schedule [name='tablet_mode']").select_option("tablet")
            for selector in (
                '#schedule [name="tablet_strength_mg"]',
                '#schedule [name="prescribed_dose_mg"]',
                '#schedule [name="tablets_planned"]',
            ):
                assert page.locator(selector).evaluate(
                    "(el) => el.getBoundingClientRect().height >= 44"
                ), (width, selector)
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth"
            ), width
        finally:
            browser.close()
