"""Release 639: real browser import, edit, and persistence payload tests."""
import json
import re
from pathlib import Path
from urllib.parse import parse_qs

import pytest
from playwright.sync_api import expect, sync_playwright

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[2]
AUTOCOMPLETE = (ROOT / "app/static/js/tracker-regimen-catalog636.js").read_text()
FACTS = (ROOT / "app/static/js/tracker-regimen-facts639.js").read_text()
URL = "http://tracker.test/regimen"

MATCH = {"results": [{
    "source": "NIH DSLD", "source_id": "218662",
    "name": "Nutrient 950", "brand": "Pure Encapsulations",
    "ingredient": "", "strength": "", "form": ""
}], "unavailable": []}
LABEL = {
    "available": True, "source_id": "218662",
    "form": "Capsule", "serving_quantity": "2",
    "serving_unit": "Capsule(s)", "servings_per_container": "60",
    "upc_sku": "1234567890", "other_ingredients": "Plant cellulose",
    "ingredient_rows_truncated": False,
    "ingredient_rows": [
        {"name": "Vitamin C", "amount": "100", "unit": "mg",
         "basis": "2 Capsule(s)", "daily_value": "Adults: 111%"},
        {"name": "Magnesium", "amount": "25", "unit": "mg",
         "basis": "2 Capsule(s)", "daily_value": "Adults: 6%"},
        {"name": "Zinc", "amount": "0.25", "unit": "mg",
         "basis": "2 Capsule(s)", "daily_value": ""},
    ],
}
SHELL = """<!doctype html><html><body>
<form method="post" action="/regimen/items" data-reg636-catalog>
<select name="kind"><option value="supplement">Supplement</option></select>
<input name="name" required maxlength="160">
<button type="button" data-reg637-search>Search catalog</button>
<small data-reg636-status></small><div data-reg636-results hidden></div>
<small data-reg636-source></small>
<input name="ingredient" maxlength="160"><input name="strength" maxlength="80">
<input name="form" maxlength="60">
<textarea name="instructions"></textarea><textarea name="notes" maxlength="2000"></textarea>
<div data-reg639-facts>
<input data-reg639-brand maxlength="160">
<input data-reg639-serving-quantity maxlength="40">
<input data-reg639-serving-unit maxlength="80">
<input data-reg639-servings-container maxlength="80">
<input data-reg639-upc maxlength="80">
<textarea data-reg639-other-ingredients maxlength="4000"></textarea>
<p data-reg639-provenance></p><p data-reg639-status></p>
<table><tbody data-reg639-ingredients></tbody></table>
<button type="button" data-reg639-add-ingredient>Add ingredient</button>
<textarea name="label_facts_json" hidden>__SAVED__</textarea>
</div>
<button type="submit">Add catalog item</button>
</form>
<script>__AUTO__</script><script>__FACTS__</script>
</body></html>"""


@pytest.fixture
def browser_tab():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        posts = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route(URL, lambda route: route.fulfill(
            status=200, content_type="text/html",
            body=SHELL.replace("__SAVED__", "")
                      .replace("__AUTO__", AUTOCOMPLETE)
                      .replace("__FACTS__", FACTS)))
        page.route(re.compile(r".*/regimen/catalog/suggest\?.*"),
                   lambda route: route.fulfill(
                       status=200, content_type="application/json",
                       body=json.dumps(MATCH)))
        page.route(re.compile(r".*/regimen/catalog/supplement-label\?.*"),
                   lambda route: route.fulfill(
                       status=200, content_type="application/json",
                       body=json.dumps(LABEL)))
        def capture(route):
            posts.append(parse_qs(route.request.post_data or ""))
            route.fulfill(status=200, body="saved")
        page.route(re.compile(r".*/regimen/items$"), capture)
        page.goto(URL)
        yield page, errors, posts
        browser.close()


def pick(page):
    page.locator('input[name="name"]').fill("nutrient 950")
    page.locator("[data-reg637-search]").click()
    page.locator("[data-reg636-results] button").click()
    expect(page.locator("[data-reg639-ingredients] tr")).to_have_count(3)


def test_exact_label_populates_structured_serving_ingredients_and_brand(browser_tab):
    page, errors, posts = browser_tab
    pick(page)
    expect(page.locator("[data-reg639-brand]")).to_have_value("Pure Encapsulations")
    expect(page.locator("[data-reg639-serving-quantity]")).to_have_value("2")
    expect(page.locator("[data-reg639-serving-unit]")).to_have_value("Capsule(s)")
    expect(page.locator("[data-reg639-other-ingredients]")).to_have_value("Plant cellulose")
    expect(page.locator("[data-reg639-ingredients]")).to_contain_text("Remove")
    expect(page.locator('[data-reg639-ingredients] [data-key="name"]').nth(2)).to_have_value("Zinc")
    expect(page.locator('[data-reg639-ingredients] [data-key="daily_value"]').first).to_have_value("Adults: 111%")
    expect(page.locator('textarea[name="notes"]')).to_have_value("")
    assert not posts
    assert not errors, errors


def test_selected_label_saves_complete_structured_payload_not_notes(browser_tab):
    page, errors, posts = browser_tab
    pick(page)
    page.locator('[data-reg639-ingredients] [data-key="amount"]').first.fill("105")
    page.locator('button[type="submit"]').click()
    assert len(posts) == 1, posts
    row = posts[0]
    assert row["name"] == ["Nutrient 950"]
    facts = json.loads(row["label_facts_json"][0])
    assert facts["brand"] == "Pure Encapsulations"
    assert facts["source_id"] == "218662"
    assert facts["serving_quantity"] == "2"
    assert facts["other_ingredients"] == "Plant cellulose"
    assert len(facts["ingredients"]) == 3
    assert facts["ingredients"][0]["amount"] == "105"
    assert facts["ingredients"][0]["daily_value"] == "Adults: 111%"
    assert row.get("notes", [""]) == [""]
    assert not errors, errors


def test_no_catalog_selection_does_not_fake_ingredient_facts(browser_tab):
    page, errors, posts = browser_tab
    page.locator('input[name="name"]').fill("Custom supplement")
    page.locator('button[type="submit"]').click()
    assert len(posts) == 1
    assert posts[0].get("label_facts_json", [""])[0] == ""
    assert not errors, errors


def test_delayed_label_data_does_not_overwrite_manual_changes(browser_tab):
    page, errors, posts = browser_tab
    # Replace the label route with a deliberately delayed response.
    page.unroute(re.compile(r".*/regimen/catalog/supplement-label\?.*"))
    import time
    def delayed(route):
        time.sleep(0.25)
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(LABEL))
    page.route(re.compile(r".*/regimen/catalog/supplement-label\?.*"), delayed)
    page.locator('input[name="name"]').fill("nutrient 950")
    page.locator("[data-reg637-search]").click()
    page.locator("[data-reg636-results] button").click()
    page.locator("[data-reg639-brand]").fill("My verified manufacturer")
    expect(page.locator("[data-reg639-brand]")).to_have_value("My verified manufacturer")
    expect(page.locator("[data-reg639-status]")).to_contain_text("Existing edits preserved")
    assert not posts
    assert not errors, errors
