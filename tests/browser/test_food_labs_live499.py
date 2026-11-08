"""Read-only browser smoke against a disposable Tracker candidate server.

The release runner supplies an isolated local URL and a disposable data dir.
No production endpoints or external food-service requests are used.
"""
import json
import os
import re
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright


URL = os.environ.get("TRACKER_TEST_URL", "").rstrip("/")
parsed = urlsplit(URL)
if parsed.hostname != "127.0.0.1" or not parsed.port or parsed.port == 8000:
    pytest.skip("Requires explicit isolated localhost candidate URL", allow_module_level=True)

pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.fixture
def tab(browser):
    context = browser.new_context()
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    yield page, errors
    context.close()


def test_499_live_food_search_and_review_controls(tab):
    page, errors = tab
    page.route(
        re.compile(r".*/food/search-name\?.*"),
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({
                "products": [{
                    "barcode": "1234567890123",
                    "name": "Example Yogurt",
                    "brand": "Test Brand",
                    "nutrition_available": False,
                    "macro_100g": {},
                }]
            }),
        ),
    )

    response = page.goto(URL + "/food", wait_until="networkidle")
    assert response is not None and response.status == 200

    food_add = page.locator("#food-add")
    food_add.evaluate("(node) => { node.open = true; }")
    expect(page.locator("#food499-review-status")).to_contain_text(
        "core values reported"
    )

    page.locator("#food-name-search").evaluate(
        "(node) => { node.open = true; }"
    )
    page.locator("#food380-query").fill("yogurt")
    page.locator("#food380-search-button").click()
    expect(page.locator(".food380-result")).to_have_count(1)
    expect(page.locator(".food380-result")).to_contain_text("Example Yogurt")

    page.locator("#food380-clear-button").click()
    expect(page.locator(".food380-result")).to_have_count(0)
    expect(page.locator("#food380-query")).to_have_value("")
    assert not errors, errors


def test_499_live_labs_report_sort_controls(tab):
    page, errors = tab
    response = page.goto(URL + "/labs", wait_until="networkidle")
    assert response is not None and response.status == 200
    expect(page.locator("#labs-reports-table")).to_have_count(1)

    sort = page.locator("#labs-reports-sort")
    expect(sort).to_have_value("date-desc")
    sort.select_option("date-asc")
    expect(sort).to_have_value("date-asc")
    page.locator("#labs-reports-clear").click()
    expect(sort).to_have_value("date-desc")
    assert not errors, errors
