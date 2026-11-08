"""Release 500: actual create/edit/delete browser paths in isolated candidate only.

This module intentionally refuses to collect outside the disposable
tracker-browser-qualify.sh server. It never targets installed DEV or PROD.
"""
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright


URL = os.environ.get("TRACKER_TEST_URL", "").rstrip("/")
DATA = Path(os.environ.get("TRACKER_BROWSER_QA_DATA_DIR", "/")).resolve()
# pytest's tests/conftest.py intentionally overrides TRACKER_DATA_DIR.
# The isolated candidate server's directory is passed separately by the
# guarded browser runner and must remain a valid disposable localhost path.
PARSED = urlsplit(URL)
ISOLATED = (
    os.environ.get("TRACKER_TEST_ISOLATED") == "1"
    and PARSED.hostname == "127.0.0.1"
    and PARSED.port not in (None, 8000)
    and DATA.name == "data"
    and DATA.parent.name.startswith("tracker-browser-qa.")
    and DATA.parent.parent == Path("/tmp").resolve()
    and DATA.is_dir()
)
if not ISOLATED:
    raise RuntimeError(
        "CRUD tests require the guarded disposable localhost runner; refusing writes"
    )

pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    context = browser.new_context()
    tab = context.new_page()
    errors = []
    tab.on("pageerror", lambda error: errors.append(str(error)))
    yield tab, errors
    context.close()


def test_500_food_create_edit_quick_reuse_and_delete(page):
    tab, errors = page
    name = "Browser QA Food 500"
    day = "2026-11-08"
    response = tab.goto(URL + "/food?day=" + day, wait_until="networkidle")
    assert response is not None and response.status == 200

    tab.locator("#food-add").evaluate("(node) => { node.open = true; }")
    form = tab.locator("#food-entry-form")
    form.locator("#food-name").fill(name)
    form.locator("#food-serving").fill("1 portion")
    form.locator('input[name="servings"]').fill("1.5")
    form.locator('select[name="meal"]').select_option("Breakfast")
    form.locator("#food-nutrient-energy").fill("100")
    form.locator("#food-nutrient-proteins").fill("10")
    form.locator('button[type="submit"]').click()

    expect(tab.locator("#food-recorded .food-log-row").filter(
        has_text=name
    )).to_have_count(1)

    tab.locator("#food-recorded").evaluate("(node) => { node.open = true; }")
    row = tab.locator("#food-recorded .food-log-row").filter(has_text=name)
    row.locator("details.food377-edit").evaluate(
        "(node) => { node.open = true; }"
    )
    edit = row.locator("form.food377-edit-form")
    edit.locator('input[name="servings"]').fill("2")
    edit.locator('select[name="meal"]').select_option("Lunch")
    edit.get_by_role("button", name="Save Changes").click()

    row = tab.locator("#food-recorded .food-log-row").filter(has_text=name)
    expect(row).to_have_count(1)
    expect(row.locator("small").first).to_contain_text("Lunch")

    tab.locator("#food-quick-log").evaluate(
        "(node) => { node.open = true; }"
    )
    search = tab.locator("#food500-quick-search")
    search.fill("no such test food")
    expect(tab.locator("#food500-quick-empty")).to_be_visible()
    search.fill(name)
    tab.locator("#food500-quick-scope").select_option("recent")
    expect(tab.locator('#food500-recent [data-food500-quick-card]:not([hidden])')).to_have_count(1)
    expect(tab.locator("#food500-quick-count")).to_contain_text("1 of")
    recent = tab.locator('#food500-recent [data-food500-quick-card]:not([hidden])')
    quick = recent.locator("form.food375-quick-form")
    quick.locator('input[name="servings"]').fill("1")
    quick.locator('select[name="meal"]').select_option("Dinner")
    quick.get_by_role("button", name="Add").click()

    matching = tab.locator("#food-recorded .food-log-row").filter(has_text=name)
    expect(matching).to_have_count(2)
    tab.on("dialog", lambda dialog: dialog.accept())
    for _ in range(2):
        matching.first.locator('form[action$="/delete"] button').click()
    expect(tab.locator("#food-recorded .food-log-row").filter(
        has_text=name
    )).to_have_count(0)
    assert not errors, errors


def test_500_lab_report_create_edit_history_export_and_delete(page):
    tab, errors = page
    response = tab.goto(URL + "/labs/new", wait_until="networkidle")
    assert response is not None and response.status == 200

    form = tab.locator("form[data-lab-manual-entry]")
    form.locator('input[name="drawn_on"]').fill("2026-11-08")
    form.locator('input[name="lab_name"]').fill("Browser QA Lab 500")
    row = form.locator("#lab-rows tr").first
    row.locator('input[name="analyte"]').fill("QA Analyte 500")
    row.locator('input[name="value"]').fill("10")
    row.locator('input[name="unit"]').fill("ng/mL")
    form.get_by_role("button", name="Save report").click()

    report_path = urlsplit(tab.url).path
    assert re.fullmatch(r"/labs/\d+", report_path), report_path
    expect(tab.locator("h1")).to_contain_text("Lab report")
    expect(tab.locator("body")).to_contain_text("QA Analyte 500")

    tab.locator("details.lab-edit-panel").first.evaluate(
        "(node) => { node.open = true; }"
    )
    edit = tab.locator('form[action="' + report_path + '/edit"]')
    edit.locator('input[name="lab_name"]').fill("Browser QA Lab 500 Edited")
    edit.get_by_role("button", name="Save Report Details").click()
    expect(tab.locator("h1")).to_contain_text("Browser QA Lab 500 Edited")

    history = URL + "/labs/trends/qa%20analyte%20500"
    result = tab.goto(history, wait_until="networkidle")
    assert result is not None and result.status == 200
    expect(tab.locator("#lab500-history-table")).to_have_count(1)
    expect(tab.locator("[data-lab500-history-row]")).to_have_count(1)

    csv = tab.request.get(history + "/export.csv")
    assert csv.status == 200
    assert csv.body().startswith(b"\xef\xbb\xbf")
    assert b"QA Analyte 500" in csv.body()

    tab.goto(URL + report_path, wait_until="networkidle")
    tab.on("dialog", lambda dialog: dialog.accept())
    tab.locator('form[action="' + report_path + '/delete"] button').click()
    expect(tab.locator("body")).not_to_contain_text(
        "Browser QA Lab 500 Edited"
    )
    assert not errors, errors
