"""Release 581: isolated inventory/dose CSRF execution evidence.

Runs only in the existing private localhost strict-CSRF Chromium gate.
All writes use synthetic QA records. Never runs against installed DEV/PROD.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import sync_playwright, expect

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
    and DATA.parent.name.startswith("tracker-browser-qa.")
    and DATA.parent.parent == Path("/tmp").resolve()
):
    raise RuntimeError("Release 581 browser security checks require isolated strict localhost")

pytestmark = pytest.mark.browser
NEGATIVE = {
    "vial-delete": ("POST", "/vials/1/delete"),
    "vial-reconstitute": ("POST", "/vials/1/reconstitute"),
    "vial-filter": ("POST", "/vials/1/filter"),
    "dose-create": ("POST", "/doses"),
    "dose-delete": ("DELETE", "/doses/1"),
    "dose-preview": ("POST", "/doses/preview"),
}
POSITIVE = {
    "vial-native-update": ("POST", "/vials/{id}", 303),
    "dose-htmx-preview": ("POST", "/doses/preview", 200),
}


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        chromium = p.chromium.launch(headless=True)
        yield chromium
        chromium.close()


@pytest.fixture
def tab(browser):
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    yield page, errors
    context.close()


def _base(scheme):
    return HTTP_URL if scheme == "http" else HTTPS_URL


def _open(page, base, path):
    loaded = page.goto(base + path, wait_until="networkidle")
    assert loaded is not None and loaded.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")
    return token


def _unsigned(page, base, method, path):
    outcome = page.request.fetch(
        base + path, method=method, max_redirects=0,
    )
    assert outcome.status == 403, (method, path, outcome.status)
    assert "CSRF token required" in outcome.text()


def _save(scheme, name, method, route, status, kind):
    assert name in (POSITIVE if kind == "positive" else NEGATIVE)
    folder = DATA.parent / "csrf-runtime581"
    folder.mkdir(mode=0o700, exist_ok=True)
    target = folder / (scheme + "-" + name + ".json")
    payload = {
        "scheme": scheme, "flow": name, "kind": kind,
        "method": method, "route_pattern": route,
        "signed_status": status if kind == "positive" else None,
        "unsigned_status": 403,
        "strict_candidate": True,
        "synthetic_qa_data_only": True,
    }
    with target.open("x", encoding="utf-8") as file:
        json.dump(payload, file, sort_keys=True)
        file.write("\n")
    target.chmod(0o600)


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_581_signed_native_vial_details_update_and_unsigned_rejection(tab, scheme):
    page, errors = tab
    base = _base(scheme)
    # Existing QA runner creates two synthetic vials with stable IDs 1 and 2.
    token = _open(page, base, "/vials/1")
    form = page.locator('form[method="post"][action="/vials/1"]')
    assert form.count() == 1
    assert form.locator('input[name="csrf_token"]').input_value() == token
    assert float(form.locator('input[name="content_value"]').input_value()) == 100.0
    _unsigned(page, base, "POST", "/vials/1")
    # Set a harmless QA-only note; leave amount, inventory, status unchanged.
    note = "Release 581 signed native vial " + scheme
    form.locator('input[name="notes"]').fill(note)
    with page.expect_response(lambda response: (
        response.request.method == "POST"
        and urlsplit(response.url).path == "/vials/1"
    )) as pending:
        form.get_by_role("button", name="Save changes").click()
    response = pending.value
    assert response.status == 303
    assert response.headers.get("x-tracker-csrf-report") == "valid"
    expect(page.locator('form[action="/vials/1"] input[name="notes"]')).to_have_value(note)
    assert not errors, errors
    _save(scheme, "vial-native-update", "POST", "/vials/{id}", 303, "positive")


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_581_actual_dose_preview_htmx_signed_and_forged_denied(tab, scheme):
    page, errors = tab
    base = _base(scheme)
    token = _open(page, base, "/doses")
    form = page.locator('form[hx-post="/doses"]')
    assert form.count() == 1
    # This form is HTMX-only (hx-post), not method=post. The CSRF
    # integration signs its unsafe HTMX requests in the request header;
    # a hidden native-form token is neither required nor guaranteed.
    assert form.get_attribute("hx-post") == "/doses"
    preview = form.locator('[hx-post="/doses/preview"]')
    assert preview.count() == 1
    amount = preview.locator('input[name="amount"]')
    assert amount.count() == 1
    emitted = []
    page.on("request", lambda request: emitted.append(request)
            if request.method == "POST" and
            urlsplit(request.url).path == "/doses/preview" else None)
    with page.expect_response(lambda response: (
        response.request.method == "POST"
        and urlsplit(response.url).path == "/doses/preview"
    )) as pending:
        amount.fill("2")
    response = pending.value
    assert response.status == 200
    assert response.headers.get("x-tracker-csrf-report") == "valid"
    assert emitted and emitted[-1].all_headers().get("x-tracker-csrf") == token
    _unsigned(page, base, "POST", "/doses/preview")
    assert not errors, errors
    _save(scheme, "dose-htmx-preview", "POST", "/doses/preview", 200, "positive")


@pytest.mark.parametrize("scheme", ("http", "https"))
@pytest.mark.parametrize("name", tuple(NEGATIVE))
def test_581_sensitive_inventory_and_dose_routes_fail_closed_unsigned(
    tab, scheme, name,
):
    page, errors = tab
    base = _base(scheme)
    _open(page, base, "/vials/1")
    method, path = NEGATIVE[name]
    _unsigned(page, base, method, path)
    assert page.request.get(base + "/vials/1").status == 200
    assert not errors, errors
    # These routes have negative-only coverage: do not overclaim that
    # signed mutation compatibility has been demonstrated.
    shape = re.sub(r"(?<=/)[0-9]+(?=/|$)", "{id}", path)
    _save(scheme, name, method, shape, None, "negative")
