"""Offline Chromium UX checks for Food database search and selection.

HTTP calls to Open Food Facts are mocked at the browser boundary. This
test never makes external requests and never writes to a Tracker database.
"""
import json
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright


pytestmark = pytest.mark.browser
SCRIPT = Path(__file__).resolve().parents[2] / "app/static/js/tracker-food380.js"
REVIEW_SCRIPT = SCRIPT.parent / "tracker-food499.js"
URL = "http://tracker.test/food"

HTML = """<!doctype html><html><body>
<form id="food380-search-form">
  <input id="food380-query"><input type="checkbox" id="food381-nutrition-only">
  <button id="food380-search-button" type="submit">Search Foods</button>
  <button id="food380-clear-button" type="button">Clear Search</button>
</form>
<p id="food380-status"></p><div id="food380-results"></div>
<form id="food-entry-form">
  <input id="food-barcode"><input id="food-name"><input id="food-serving">
  <input id="food-source"><input name="servings" value="2">
  <input id="food-nutrient-energy">
  <input id="food-nutrient-proteins">
</form>
<p id="food-scan-status"></p>
<div id="food499-review">
  <p id="food499-review-status"></p>
  <div id="food499-macro-preview"></div>
</div>
<script>__REVIEW_SCRIPT__</script>
<script>__SEARCH_SCRIPT__</script>
</body></html>"""


@pytest.fixture
def tab():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.route(
            URL,
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body=HTML.replace("__REVIEW_SCRIPT__", REVIEW_SCRIPT.read_text()).replace(
                    "__SEARCH_SCRIPT__", SCRIPT.read_text()
                ),
            ),
        )
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(URL)
        yield page, errors
        browser.close()


def search_route(page, products):
    page.route(
        re.compile(r".*/food/search-name\?.*"),
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"products": products}),
        ),
    )


def test_nutrition_filter_explains_unknown_results_and_clear(tab):
    page, errors = tab
    search_route(page, [{
        "barcode": "1234567890123",
        "name": "Yogurt without macros",
        "nutrition_available": False,
        "macro_100g": {},
    }])
    page.locator("#food380-query").fill("yogurt")
    page.locator("#food380-search-button").click()
    expect(page.locator(".food380-result")).to_have_count(1)

    page.locator("#food381-nutrition-only").check()
    expect(page.locator(".food380-result")).to_have_count(0)
    expect(page.locator("#food380-status")).to_contain_text(
        "None of the 1 results include reported macros"
    )

    page.locator("#food380-clear-button").click()
    expect(page.locator("#food380-query")).to_have_value("")
    expect(page.locator("#food381-nutrition-only")).not_to_be_checked()
    expect(page.locator("#food380-status")).to_contain_text("Search cleared")
    expect(page.locator(".food380-result")).to_have_count(0)
    assert not errors, errors


def test_name_search_loads_barcode_details_for_review(tab):
    page, errors = tab
    search_route(page, [{
        "barcode": "1234567890123",
        "name": "Plain Yogurt",
        "brand": "Example Brand",
        "serving": "170 g",
        "nutrition_available": True,
        "macro_100g": {"energy": 100, "proteins": 12},
    }])
    page.route(
        re.compile(r".*/food/barcode/1234567890123$"),
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({
                "barcode": "1234567890123",
                "name": "Plain Yogurt",
                "serving_description": "170 g",
                "source": "Open Food Facts; verify against packaging",
                "nutrients": {"energy": 170, "proteins": 20.4},
            }),
        ),
    )
    page.locator("#food380-query").fill("plain yogurt")
    page.locator("#food380-search-button").click()
    expect(page.locator(".food380-result")).to_have_count(1)
    page.get_by_role("button", name="Use Food").click()
    expect(page.locator("#food-name")).to_have_value("Plain Yogurt")
    expect(page.locator("#food-serving")).to_have_value("170 g")
    expect(page.locator("#food-nutrient-energy")).to_have_value("170")
    expect(page.locator("#food-nutrient-proteins")).to_have_value("20.4")
    expect(page.locator("#food380-status")).to_contain_text(
        "Review the serving basis"
    )
    assert not errors, errors


def test_search_rate_limit_shows_retry_delay(tab):
    page, errors = tab
    page.route(
        re.compile(r".*/food/search-name\?.*"),
        lambda route: route.fulfill(
            status=429,
            content_type="application/json",
            headers={"Retry-After": "45"},
            body=json.dumps({"detail": "Busy"}),
        ),
    )
    page.locator("#food380-query").fill("protein bar")
    page.locator("#food380-search-button").click()
    expect(page.locator("#food380-status")).to_contain_text(
        "Retry after 45 seconds"
    )
    expect(page.locator("#food380-search-button")).to_be_enabled()
    assert not errors, errors


def test_499_macro_review_distinguishes_unknown_from_zero(tab):
    page, errors = tab
    expect(page.locator("#food499-review-status")).to_contain_text(
        "0 of 4 core values reported"
    )
    page.locator("#food-serving").fill("170 g")
    page.locator("#food-nutrient-energy").fill("0")
    page.locator("#food-nutrient-proteins").fill("20")
    expect(page.locator("#food499-review-status")).to_contain_text(
        "2 of 4 core values reported"
    )
    expect(page.locator("#food499-review-status")).to_contain_text(
        "Unknown: C, F"
    )
    expect(page.locator("#food499-macro-preview")).to_contain_text("Cal 0")
    expect(page.locator("#food499-macro-preview")).to_contain_text("P 40")
    assert not errors, errors
