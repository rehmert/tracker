"""Release 730: medication lookups populate native add/edit form POST fields."""
import json
import re
from pathlib import Path
from urllib.parse import parse_qs

import pytest
from playwright.sync_api import expect, sync_playwright

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / "app/static/js/tracker-regimen-catalog636.js"
URL = "http://tracker.test/regimen"

HTML = """<!doctype html><html><body>
<form method="post" action="/regimen/items" data-reg636-catalog>
  <select name="kind"><option value="medication" selected>Medication</option></select>
  <input name="name" maxlength="160" required>
  <button type="button" data-reg637-search>Search catalog</button>
  <small data-reg636-status></small>
  <div data-reg636-results role="listbox" hidden></div>
  <small data-reg636-source></small>
  <input name="ingredient" maxlength="160">
  <input name="strength" maxlength="80">
  <input name="form" maxlength="60">
  <button type="submit">Add catalog item</button>
</form>
<form method="post" action="/regimen/items/42/edit" data-reg636-catalog>
  <select name="kind"><option value="medication" selected>Medication</option></select>
  <input name="name" value="Old Medication" maxlength="160" required>
  <button type="button" data-reg637-search>Search catalog</button>
  <small data-reg636-status></small>
  <div data-reg636-results role="listbox" hidden></div>
  <small data-reg636-source></small>
  <input name="ingredient" value="Old ingredient" maxlength="160">
  <input name="strength" value="999 mg" maxlength="80">
  <input name="form" value="OLD FORM" maxlength="60">
  <button type="submit">Save item</button>
</form><script>__SCRIPT__</script></body></html>"""

MATCH = {
    "results": [
        {"source": "openFDA", "source_id": "12345-678",
         "name": "Sample 10 mg Tablet", "brand": "Sample",
         "ingredient": "SAMPLE INGREDIENT", "strength": "10 mg", "form": "TABLET"},
        {"source": "RxNorm", "source_id": "3456",
         "name": "Sample concept", "brand": "",
         "ingredient": "", "strength": "", "form": ""},
    ],
    "unavailable": [],
}


@pytest.fixture
def browser_tab():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        posts = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route(URL, lambda route: route.fulfill(
            status=200, content_type="text/html",
            body=HTML.replace("__SCRIPT__", JS.read_text(encoding="utf-8")),
        ))
        page.route(
            re.compile(r".*/regimen/catalog/suggest\?.*"),
            lambda route: route.fulfill(
                status=200, content_type="application/json",
                body=json.dumps(MATCH),
            ),
        )

        def capture_post(route):
            posts.append({
                "url": route.request.url,
                "form": parse_qs(route.request.post_data or ""),
            })
            route.fulfill(status=200, content_type="text/html", body="Saved")

        page.route(re.compile(r".*/regimen/items(?:/[0-9]+/edit)?$"), capture_post)
        page.goto(URL)
        yield page, posts, errors
        browser.close()


@pytest.mark.parametrize("index", (0, 1))
def test_730_medication_selection_prefills_fields_that_are_posted(browser_tab, index):
    page, posts, errors = browser_tab
    form = page.locator("form[data-reg636-catalog]").nth(index)
    form.locator('[name="name"]').fill("sample")
    form.locator("[data-reg637-search]").click()
    buttons = form.locator("[data-reg636-results] button")
    expect(buttons).to_have_count(2)
    buttons.first.click()
    for name, expected in [
        ("name", "Sample 10 mg Tablet"),
        ("ingredient", "SAMPLE INGREDIENT"),
        ("strength", "10 mg"),
        ("form", "TABLET"),
    ]:
        expect(form.locator('[name="' + name + '"]')).to_have_value(expected)
    expect(form.locator("[data-reg636-status]")).to_contain_text(
        "Product details filled"
    )
    assert not posts, "Search or selection must not submit"
    # The same fields must be included in the browser's real form POST body.
    with page.expect_request(re.compile(r".*/regimen/items(?:/[0-9]+/edit)?$")):
        form.locator('button[type="submit"]').click()
    expect(page.locator("body")).to_contain_text("Saved")
    assert len(posts) == 1
    assert posts[0]["form"] == {
        "kind": ["medication"],
        "name": ["Sample 10 mg Tablet"],
        "ingredient": ["SAMPLE INGREDIENT"],
        "strength": ["10 mg"],
        "form": ["TABLET"],
    }
    assert posts[0]["url"].endswith(
        "/regimen/items" if index == 0 else "/regimen/items/42/edit"
    )
    assert not errors, errors


def test_730_new_name_only_selection_clears_old_medication_details(browser_tab):
    page, posts, errors = browser_tab
    form = page.locator("form[data-reg636-catalog]").nth(1)
    form.locator('[name="name"]').fill("sample")
    form.locator("[data-reg637-search]").click()
    buttons = form.locator("[data-reg636-results] button")
    expect(buttons).to_have_count(2)
    buttons.first.click()
    expect(form.locator('[name="strength"]')).to_have_value("10 mg")

    # An RxNorm-only match may have no structured fields. It must not keep
    # another drug's ingredient, strength or form from the prior selection.
    form.locator("[data-reg637-search]").click()
    expect(buttons).to_have_count(2)
    buttons.nth(1).click()
    expect(form.locator('[name="name"]')).to_have_value("Sample concept")
    for key in ("ingredient", "strength", "form"):
        expect(form.locator('[name="' + key + '"]')).to_have_value("")
    expect(form.locator("[data-reg636-status]")).to_contain_text(
        "no structured ingredient"
    )
    assert not posts
    assert not errors, errors
