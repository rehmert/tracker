"""Release 583: native signed vial preparations and stock rollback in Chromium.

Strict only, private isolated localhost candidate. Browser mutates synthetic
vials #1 and #2 and independently verified synthetic supply records only.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright

HTTP_URL = os.environ.get("TRACKER_TEST_URL", "").rstrip("/")
HTTPS_URL = os.environ.get("TRACKER_TEST_HTTPS_URL", "").rstrip("/")
DATA = Path(os.environ.get("TRACKER_BROWSER_QA_DATA_DIR", "/")).resolve()
HTTP, HTTPS = urlsplit(HTTP_URL), urlsplit(HTTPS_URL)
if not (
    os.environ.get("TRACKER_TEST_ISOLATED") == "1"
    and os.environ.get("TRACKER_TEST_STRICT_CSRF") == "1"
    and HTTP.scheme == "http" and HTTPS.scheme == "https"
    and HTTP.hostname == HTTPS.hostname == "127.0.0.1"
    and HTTP.port not in (None, 8000)
    and HTTPS.port not in (None, 443, 8000, HTTP.port)
    and DATA.name == "data" and DATA.is_dir()
    and re.fullmatch(r"tracker-browser-qa\.[A-Za-z0-9_]{8}", DATA.parent.name)
    and DATA.parent.parent == Path("/tmp").resolve()
):
    raise RuntimeError("Release 583 browser tests require disposable strict localhost")

pytestmark = pytest.mark.browser
OPERATIONS = (
    ("POST", "/vials/{id}/reconstitute", 303),
    ("POST", "/vials/{id}/filter", 303),
    ("POST", "/vials/{id}/preparations/{event}/edit", 303),
    ("POST", "/vials/{id}/preparations/{event}/delete", 303),
)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture
def tab(browser):
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    yield page, errors
    context.close()


def _visit(page, base, path):
    response = page.goto(base + path, wait_until="networkidle")
    assert response is not None and response.status == 200, (path, response.status)
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")
    return token


def _rejected(page, base, path):
    response = page.request.post(base + path, max_redirects=0)
    assert response.status == 403, (path, response.status)
    assert "CSRF token required" in response.text()


def _submit(page, button, path, *, dialog=False):
    if dialog:
        page.once("dialog", lambda alert: alert.accept())
    with page.expect_response(
        lambda response: response.request.method == "POST"
        and urlsplit(response.url).path == path
    ) as observed:
        button.click()
    response = observed.value
    assert response.status == 303, (path, response.status)
    assert response.headers.get("x-tracker-csrf-report") == "valid"


def _private_receipt(scheme):
    folder = DATA.parent / "csrf-runtime583"
    folder.mkdir(mode=0o700, exist_ok=True)
    target = folder / f"{scheme}-preparation-lifecycle.json"
    data = {
        "scheme": scheme, "flow": "preparation-lifecycle",
        "operations": [
            {"method": method, "route_pattern": route,
             "signed_status": status, "unsigned_status": 403}
            for method, route, status in OPERATIONS
        ],
        "strict_candidate": True, "synthetic_qa_data_only": True,
        "signed_lifecycle_verified": True,
        "inventory_verified_separately": True,
    }
    with target.open("x", encoding="utf-8") as output:
        json.dump(data, output, sort_keys=True)
        output.write("\n")
    target.chmod(0o600)


@pytest.mark.parametrize("scheme,vid", (("http", 1), ("https", 2)))
def test_583_reconstitution_filter_correction_delete_with_stock(tab, scheme, vid):
    page, errors = tab
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    manifest = DATA.parent / "csrf-fixture583.json"
    assert manifest.is_file() and not manifest.is_symlink()
    ids = json.loads(manifest.read_text(encoding="utf-8"))
    assert set(ids) == {"water", "needle", "swab"}
    detail = f"/vials/{vid}"

    token = _visit(page, base, detail)
    reconst_path = detail + "/reconstitute"
    reconst = page.locator(f'form[action="{reconst_path}"][method="post"]')
    assert reconst.count() == 1
    assert reconst.locator('input[name="csrf_token"]').input_value() == token
    _rejected(page, base, reconst_path)
    reconst.locator('input[name="volume_ml"]').fill("2")
    reconst.locator('select[name="supply_id"]').select_option(str(ids["water"]))
    reconst.locator('input[name="supply_id_used"][value="' + str(ids["needle"]) + '"]').check()
    _submit(page, reconst.get_by_role("button", name="Record", exact=True),
            reconst_path)
    # Successful reconstitution hides its one-time form.
    expect(page.locator(f'form[action="{reconst_path}"]')).to_have_count(0)

    filter_path = detail + "/filter"
    token = _visit(page, base, detail)
    filtering = page.locator(f'form[action="{filter_path}"][method="post"]')
    assert filtering.count() == 1
    assert filtering.locator('input[name="csrf_token"]').input_value() == token
    _rejected(page, base, filter_path)
    note = "QA 583 filtering " + scheme
    filtering.locator('input[name="notes"]').fill(note)
    filtering.locator('input[name="supply_id_used"][value="' + str(ids["swab"]) + '"]').check()
    _submit(page, filtering.get_by_role("button", name="Record filtering supplies"),
            filter_path)
    # Identify the new event by its exact note, not a brittle event ID.
    history = page.locator("li").filter(has_text=note)
    expect(history).to_have_count(1)
    edit_href = history.locator('a[href$="/edit"]').get_attribute("href")
    assert edit_href and re.fullmatch(
        rf"/vials/{vid}/preparations/[0-9]+/edit", edit_href
    )
    delete_path = edit_href.removesuffix("/edit") + "/delete"

    token = _visit(page, base, edit_href)
    correction = page.locator("form[method='post']")
    assert correction.count() == 1
    assert correction.locator('input[name="csrf_token"]').input_value() == token
    _rejected(page, base, edit_href)
    changed = "QA 583 corrected " + scheme
    correction.locator('input[name="notes"]').fill(changed)
    correction.locator('input[name="supply_id_used"][value="' + str(ids["swab"]) + '"]').uncheck()
    correction.locator('input[name="supply_id_used"][value="' + str(ids["needle"]) + '"]').check()
    correction.locator('input[name="supply_qty_' + str(ids["needle"]) + '"]').fill("2")
    _submit(page, correction.get_by_role("button", name="Save correction"), edit_href)
    _visit(page, base, edit_href)
    expect(page.locator('input[name="notes"]')).to_have_value(changed)
    assert page.locator('input[name="supply_id_used"][value="' + str(ids["needle"]) + '"]').is_checked()
    assert not page.locator('input[name="supply_id_used"][value="' + str(ids["swab"]) + '"]').is_checked()

    _rejected(page, base, delete_path)
    _visit(page, base, detail)
    history = page.locator("li").filter(has_text=changed)
    expect(history).to_have_count(1)
    delete_form = history.locator(f'form[action="{delete_path}"]')
    assert delete_form.count() == 1
    assert delete_form.locator('input[name="csrf_token"]').count() == 1
    _submit(page, delete_form.get_by_role("button", name="Delete"),
            delete_path, dialog=True)
    expect(page.locator("li").filter(has_text=changed)).to_have_count(0)
    assert page.request.get(base + edit_href).status == 404
    assert not errors, errors
    _private_receipt(scheme)
