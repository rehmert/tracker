"""Release 638: actual Chromium interaction with inline regimen catalog.

Uses the shipped JavaScript, mocked local endpoints, no live app/database.
"""
import json
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

pytestmark = pytest.mark.browser
JS = Path(__file__).resolve().parents[2] / "app/static/js/tracker-regimen-catalog636.js"
URL = "http://tracker.test/regimen"
HTML = """<!doctype html><html><body>
<form method="post" action="/regimen/items" data-reg636-catalog>
  <select name="kind"><option value="supplement">Supplement</option>
    <option value="medication">Medication</option></select>
  <input name="name" maxlength="160" required>
  <button type="button" data-reg637-search>Search catalog</button>
  <small data-reg636-status>Type a name to search public catalogs.</small>
  <div data-reg636-results role="listbox" hidden></div>
  <small data-reg636-source></small>
  <input name="ingredient" maxlength="160">
  <input name="strength" maxlength="80">
  <input name="form" maxlength="60">
  <textarea name="instructions"></textarea>
  <textarea name="notes" maxlength="2000"></textarea>
  <button type="submit">Add catalog item</button>
</form>
<script>__SCRIPT__</script></body></html>"""

MATCH = {
    "results": [{
        "source": "NIH DSLD",
        "source_id": "218662",
        "name": "Nutrient 950",
        "brand": "Pure Encapsulations",
        "ingredient": "", "strength": "", "form": "",
    }],
    "unavailable": [],
}

@pytest.fixture
def tab():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        requested = []
        posts = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.route(URL, lambda route: route.fulfill(
            status=200, content_type="text/html",
            body=HTML.replace("__SCRIPT__", JS.read_text())))
        def lookup(route):
            requested.append(route.request.url)
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(MATCH))
        page.route(re.compile(r".*/regimen/catalog/suggest\?.*"), lookup)
        page.route(re.compile(r".*/regimen/catalog/supplement-label\?.*"),
                   lambda route: route.fulfill(
                       status=200, content_type="application/json",
                       body=json.dumps({
                           "available": True, "ingredients": "Vitamin A 100 mcg",
                           "serving": "2 Capsules", "form": "Capsule"
                       })))
        page.route(re.compile(r".*/regimen/items$"), lambda route: (
            posts.append(route.request.url), route.fulfill(status=200, body="saved")))
        page.goto(URL)
        yield page, errors, requested, posts
        browser.close()


def test_click_search_shows_matching_nih_supplement(tab):
    page, errors, requested, posts = tab
    page.locator('input[name="name"]').fill("nutrient 950")
    page.locator("[data-reg637-search]").click()
    expect(page.locator("[data-reg636-results] button")).to_have_count(1)
    expect(page.locator("[data-reg636-results]")).to_contain_text("Nutrient 950")
    expect(page.locator("[data-reg636-results]")).to_contain_text("Pure Encapsulations")
    assert requested and "q=nutrient+950" in requested[-1]
    assert "kind=supplement" in requested[-1]
    assert not posts
    assert not errors, errors


def test_select_match_prefills_and_preserves_manual_edits(tab):
    page, errors, requested, posts = tab
    page.locator('input[name="name"]').fill("nutrient 950")
    page.locator("[data-reg637-search]").click()
    page.locator("[data-reg636-results] button").click()
    expect(page.locator('input[name="name"]')).to_have_value("Nutrient 950")
    expect(page.locator('input[name="form"]')).to_have_value("Capsule")
    # Release 639 keeps NIH ingredients/source in structured fields, not Notes.
    expect(page.locator('textarea[name="notes"]')).to_have_value("")
    page.locator('input[name="form"]').fill("My custom form")
    expect(page.locator('input[name="form"]')).to_have_value("My custom form")
    assert not posts
    assert not errors, errors


def test_enter_search_does_not_submit_catalog_item(tab):
    page, errors, requested, posts = tab
    page.locator('input[name="name"]').fill("nutrient 950")
    page.locator('input[name="name"]').press("Enter")
    expect(page.locator("[data-reg636-results] button")).to_have_count(1)
    assert requested
    assert posts == []
    assert not errors, errors


def test_provider_http_error_is_visible_and_never_saves(tab):
    page, errors, requested, posts = tab
    page.unroute(re.compile(r".*/regimen/catalog/suggest\\?.*"))
    page.route(re.compile(r".*/regimen/catalog/suggest\\?.*"),
               lambda route: route.fulfill(
                   status=503, content_type="application/json",
                   body=json.dumps({"detail": "Unavailable"})))
    page.locator('input[name="name"]').fill("nutrient 950")
    page.locator("[data-reg637-search]").click()
    expect(page.locator("[data-reg636-status]")).to_contain_text("HTTP 503")
    expect(page.locator("[data-reg636-results] button")).to_have_count(0)
    assert not posts
    assert not errors, errors
