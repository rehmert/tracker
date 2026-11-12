"""Release 582: signed dose create/correct/delete under disposable strict CSRF.

All browser mutations use the seeded /tmp candidate database only.
Do not collect against installed DEV or PROD. Source and receipts are QA-only.
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
    and DATA.is_dir() and DATA.name == "data"
    and re.fullmatch(r"tracker-browser-qa\.[A-Za-z0-9_]{8}", DATA.parent.name)
    and DATA.parent.parent == Path("/tmp").resolve()
):
    raise RuntimeError("Release 582 only runs inside isolated strict localhost QA")

pytestmark = pytest.mark.browser
OPERATIONS = (
    ("POST", "/doses", 200),
    ("POST", "/doses/{id}/edit", 303),
    ("DELETE", "/doses/{id}", 200),
)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        instance = p.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.fixture
def tab(browser):
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    yield page, errors
    context.close()


def _open(page, base, path):
    response = page.goto(base + path, wait_until="networkidle")
    assert response is not None and response.status == 200, (path, response.status)
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")
    return token


def _forged(page, base, method, path):
    response = page.request.fetch(base + path, method=method, max_redirects=0)
    assert response.status == 403, (method, path, response.status)
    assert "CSRF token required" in response.text()


def _witness(page, selector, method, path, expected, *, dialog=False):
    if dialog:
        page.once("dialog", lambda alert: alert.accept())
    with page.expect_response(
        lambda response: response.request.method == method
        and urlsplit(response.url).path == path
    ) as pending:
        selector.click()
    response = pending.value
    assert response.status == expected, (method, path, response.status)
    assert response.headers.get("x-tracker-csrf-report") == "valid"
    if method == "DELETE":
        assert response.request.all_headers().get("x-tracker-csrf", "").startswith("v1.")
    return response


def _receipt(scheme):
    folder = DATA.parent / "csrf-runtime582"
    folder.mkdir(mode=0o700, exist_ok=True)
    output = folder / (scheme + "-dose-lifecycle.json")
    data = {
        "scheme": scheme,
        "flow": "dose-lifecycle",
        "operations": [
            {"method": method, "route_pattern": route,
             "signed_status": status, "unsigned_status": 403}
            for method, route, status in OPERATIONS
        ],
        "strict_candidate": True,
        "synthetic_qa_data_only": True,
        "signed_lifecycle_verified": True,
    }
    with output.open("x", encoding="utf-8") as file:
        json.dump(data, file, sort_keys=True)
        file.write("\n")
    output.chmod(0o600)


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_582_dose_create_correct_delete_with_forgery_rejection(tab, scheme):
    page, errors = tab
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    _open(page, base, "/doses")
    form = page.locator('form[hx-post="/doses"]')
    assert form.count() == 1
    before = set(page.locator('a[href^="/doses/"][href$="/edit"]').evaluate_all(
        "(nodes) => nodes.map(n => n.getAttribute('href'))"
    ))
    _forged(page, base, "POST", "/doses")
    form.locator('select[name="vial_id"]').select_option("1")
    form.locator('input[name="amount"]').fill("1")
    form.locator('select[name="unit"]').select_option("mg")
    # The application enhances the datetime-local input with a visible
    # date + 24-hour clock. Use the real UI's current-time control so the
    # enhanced fields and original submitted timestamp remain synchronized.
    form.get_by_role("button", name="Use current time").click()
    expect(form.locator('input[name="taken_at"]')).not_to_have_value("")
    # Fail immediately with the invalid field names rather than waiting
    # 30 seconds for a POST that HTML constraint validation prevented.
    invalid = form.evaluate("""form => [...form.elements]
        .filter(el => el.willValidate && !el.checkValidity())
        .map(el => ({name: el.name || el.getAttribute('aria-label'),
                     message: el.validationMessage}))""")
    assert not invalid, ("dose form has invalid browser fields", invalid)
    assert form.evaluate("form => form.checkValidity()")
    # HTMX form, not a native POST: verify emitted request CSRF header.
    response = _witness(
        page, form.get_by_role("button", name="Add to log"),
        "POST", "/doses", 200
    )
    assert response.request.all_headers().get("x-tracker-csrf", "").startswith("v1.")
    new_link = page.locator('a[href^="/doses/"][href$="/edit"]')
    expect(new_link).to_have_count(len(before) + 1)
    created = set(new_link.evaluate_all(
        "(nodes) => nodes.map(n => n.getAttribute('href'))"
    )) - before
    assert len(created) == 1, created
    edit_path = created.pop()
    assert re.fullmatch(r"/doses/[0-9]+/edit", edit_path)
    delete_path = edit_path.removesuffix("/edit")
    row = page.locator("tr").filter(
        has=page.locator('a[href="' + edit_path + '"]')
    )
    expect(row).to_have_count(1)

    token = _open(page, base, edit_path)
    edit = page.locator('form[method="post"][action="' + edit_path + '"]')
    assert edit.count() == 1
    assert edit.locator('input[name="csrf_token"]').input_value() == token
    _forged(page, base, "POST", edit_path)
    edit.locator('input[name="amount"]').fill("2")
    edit.locator('input[name="notes"]').fill("QA signed correction 582 " + scheme)
    _witness(page, edit.get_by_role("button", name="Save entry"),
             "POST", edit_path, 303)
    _open(page, base, edit_path)
    expect(page.locator('form[action="' + edit_path + '"] input[name="amount"]')).to_have_value(
        re.compile(r"2(?:\.0+)?")
    )
    expect(page.locator('form[action="' + edit_path + '"] input[name="notes"]')).to_have_value(
        "QA signed correction 582 " + scheme
    )
    _forged(page, base, "DELETE", delete_path)
    _open(page, base, "/doses")
    row = page.locator("tr").filter(
        has=page.locator('a[href="' + edit_path + '"]')
    )
    expect(row).to_have_count(1)
    _witness(page, row.locator('button[hx-delete="' + delete_path + '"]'),
             "DELETE", delete_path, 200, dialog=True)
    expect(page.locator('a[href="' + edit_path + '"]')).to_have_count(0)
    assert page.request.get(base + edit_path).status == 404
    assert not errors, errors
    _receipt(scheme)
