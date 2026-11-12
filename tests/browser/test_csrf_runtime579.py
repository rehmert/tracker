"""Release 579: strict-CSRF runtime evidence from real browser JS requests.

Only run via tracker-browser-qualify.sh against the disposable localhost
candidate. No installed DEV/PROD route or user database can be targeted.
"""
from __future__ import annotations

import os
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright

HTTP_URL = os.environ.get("TRACKER_TEST_URL", "").rstrip("/")
HTTPS_URL = os.environ.get("TRACKER_TEST_HTTPS_URL", "").rstrip("/")
DATA = Path(os.environ.get("TRACKER_BROWSER_QA_DATA_DIR", "/")).resolve()
HTTP = urlsplit(HTTP_URL)
HTTPS = urlsplit(HTTPS_URL)

if not (
    os.environ.get("TRACKER_TEST_ISOLATED") == "1"
    and os.environ.get("TRACKER_TEST_STRICT_CSRF") == "1"
    and HTTP.scheme == "http" and HTTPS.scheme == "https"
    and HTTP.hostname == HTTPS.hostname == "127.0.0.1"
    and HTTP.port not in (None, 8000)
    and HTTPS.port not in (None, 443, 8000, HTTP.port)
    and DATA.is_dir()
    and DATA.name == "data"
    and DATA.parent.name.startswith("tracker-browser-qa.")
    and DATA.parent.parent == Path("/tmp").resolve()
):
    raise RuntimeError("Release 579 runtime tests require isolated strict localhost")

pytestmark = pytest.mark.browser


def _record_evidence(scheme, flow, path, accepted_status, denied_status):
    """Emit only whitelisted metadata under the disposable browser QA root."""
    if flow not in ("mobile-weight", "mobile-bp", "mobile-water",
                   "notes-preview", "notes-visual-fetch", "native-compound"):
        raise ValueError("Unknown runtime witness flow")
    folder = DATA.parent / "csrf-runtime579"
    folder.mkdir(mode=0o700, exist_ok=True)
    destination = folder / (scheme + "-" + flow + ".json")
    payload = {
        "scheme": scheme, "flow": flow, "method": "POST",
        "path": path, "accepted_status": accepted_status,
        "denied_status": denied_status,
        "signed_browser_request": True,
        "runtime_observed": True, "isolated_candidate": True,
    }
    # Never retain cookie, signed CSRF token, request body, or user data.
    with destination.open("x", encoding="utf-8") as output:
        json.dump(payload, output, sort_keys=True)
        output.write("\n")
    destination.chmod(0o600)


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
    page.on("pageerror", lambda err: errors.append(str(err)))
    yield page, errors
    context.close()


@pytest.mark.parametrize("scheme", ("http", "https"))
@pytest.mark.parametrize("kind,endpoint,values", (
    ("weight", "/vitals", {"weight": "217.25"}),
    ("bp", "/vitals", {"systolic": "121", "diastolic": "77"}),
    ("water", "/food/water", {"ounces": "7.5"}),
))
def test_579_real_mobile_js_write_and_forged_replay_denied(
    tab, scheme, kind, endpoint, values,
):
    page, errors = tab
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    page.set_viewport_size({"width": 390, "height": 844})
    loaded = page.goto(base + "/mobile", wait_until="networkidle")
    assert loaded is not None and loaded.status == 200

    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")

    captured = []
    def on_request(req):
        if req.method == "POST" and urlsplit(req.url).path == endpoint:
            captured.append(req)

    page.on("request", on_request)
    page.locator("#tracker-mobile-add528").click()
    page.locator(f'[data-quick528-choice="{kind}"]').click()
    form = page.locator(f'form[data-quick528-form="{kind}"]')
    assert form.count() == 1
    assert form.get_attribute("data-quick528-endpoint") == endpoint
    for field, value in values.items():
        form.locator(f'input[name="{field}"]').fill(value)

    with page.expect_response(
        lambda response: (
            response.request.method == "POST"
            and urlsplit(response.url).path == endpoint
        )
    ) as event:
        form.locator('button[type="submit"]').click()

    response = event.value
    assert response.status == 200, (kind, response.status)
    assert response.headers.get("x-tracker-csrf-report") == "valid"
    expect(page.locator("[data-quick528-success]")).to_be_visible()
    assert len(captured) == 1
    wire = captured[0]
    assert wire.url == base + endpoint
    headers = wire.all_headers()
    assert headers.get("x-tracker-csrf") == token
    assert headers.get("x-tracker-mobile-quick") == "528"
    assert headers.get("accept") == "application/json"
    assert form.locator('input[name="csrf_token"]').input_value() == token

    # Bypass the application's browser fetch/FormData wrapper using
    # Playwright's separate API request. An unsigned replay MUST fail.
    denied = page.request.post(
        base + endpoint, data=values,
        headers={"X-Tracker-Mobile-Quick": "528", "Accept": "application/json"},
        max_redirects=0,
    )
    assert denied.status == 403, (kind, scheme, denied.status)
    assert not errors, errors
    _record_evidence(scheme, "mobile-" + kind, endpoint, response.status,
                     denied.status)


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_579_htmx_preview_records_actual_header_and_route(tab, scheme):
    page, errors = tab
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    response = page.goto(base + "/pages/new", wait_until="networkidle")
    assert response is not None and response.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")
    editor = page.locator("#notes-body")
    assert editor.get_attribute("hx-post") == "/pages/preview"
    page.locator("#notes-source-mode").click()
    expect(editor).to_be_visible()

    sent = []
    page.on("request", lambda request: sent.append(request)
            if request.method == "POST" and
            urlsplit(request.url).path == "/pages/preview" else None)
    with page.expect_response(
        lambda result: result.request.method == "POST" and
        urlsplit(result.url).path == "/pages/preview"
    ) as pending:
        editor.fill("**Release 579 real HTMX witness**")
    approved = pending.value
    assert approved.status == 200
    assert approved.headers.get("x-tracker-csrf-report") == "valid"
    assert sent
    assert all(req.all_headers().get("x-tracker-csrf") == token for req in sent)
    expect(page.locator("#preview")).to_contain_text(
        "Release 579 real HTMX witness"
    )

    denied = page.request.post(
        base + "/pages/preview", data={"body": "forged"},
        max_redirects=0,
    )
    assert denied.status == 403
    assert not errors, errors
    _record_evidence(scheme, "notes-preview", "/pages/preview",
                     approved.status, denied.status)


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_579_native_compound_positive_and_unsigned_negative(tab, scheme):
    page, errors = tab
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    response = page.goto(base + "/compounds", wait_until="networkidle")
    assert response is not None and response.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")
    form = page.locator('form[action="/compounds"][method="post"]')
    assert form.count() == 1
    name = "QA release 579 native " + scheme
    form.locator('input[name="name"]').fill(name)
    with page.expect_response(
        lambda response: response.request.method == "POST"
        and urlsplit(response.url).path == "/compounds"
    ) as pending:
        form.get_by_role("button", name="Add compound").click()
    approved = pending.value
    assert approved.status == 303
    assert approved.headers.get("x-tracker-csrf-report") == "valid"
    expect(page.locator("body")).to_contain_text(name)

    denied = page.request.post(
        base + "/compounds", data={"name": "QA forbidden native 579"},
        max_redirects=0,
    )
    assert denied.status == 403
    assert "QA forbidden native 579" not in page.request.get(
        base + "/compounds"
    ).text()
    assert not errors, errors
    _record_evidence(scheme, "native-compound", "/compounds",
                     approved.status, denied.status)


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_579_real_notes_visual_editor_fetch_callsite(tab, scheme):
    """Exercise the tracked app/static/notes_editor.js POST, not injected JS."""
    page, errors = tab
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    loaded = page.goto(base + "/pages/new", wait_until="networkidle")
    assert loaded is not None and loaded.status == 200
    assert page.locator('script[src*="notes_editor.js"]').count() >= 1
    expect(page.locator("#notes-visual-mode")).to_have_attribute(
        "aria-pressed", "true"
    )
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")
    page.locator("#notes-source-mode").click()
    expect(page.locator("#notes-source-mode")).to_have_attribute(
        "aria-pressed", "true"
    )

    # Attach listeners AFTER the initial load and switch back using the
    # actual app UI. Only notes_editor.js's markdownToVisual() fetch can
    # be responsible for the resulting transition request.
    sent = []
    responses = []
    def is_preview(req):
        return req.method == "POST" and urlsplit(req.url).path == "/pages/preview"

    page.on("request", lambda req: sent.append(req) if is_preview(req) else None)
    page.on("response", lambda resp: responses.append(resp)
            if is_preview(resp.request) else None)
    with page.expect_response(
        lambda resp: is_preview(resp.request)
    ) as pending:
        page.locator("#notes-visual-mode").click()
    assert pending.value.status == 200
    expect(page.locator("#notes-visual-mode")).to_have_attribute(
        "aria-pressed", "true"
    )
    assert sent and responses
    assert any(req.all_headers().get("x-tracker-csrf") == token for req in sent)
    approved = [resp for resp in responses if
                resp.status == 200 and
                resp.headers.get("x-tracker-csrf-report") == "valid"]
    assert approved, [resp.status for resp in responses]
    denied = page.request.post(
        base + "/pages/preview", data={"body": "unsigned 579"},
        max_redirects=0,
    )
    assert denied.status == 403
    assert not errors, errors
    _record_evidence(scheme, "notes-visual-fetch", "/pages/preview",
                     approved[-1].status, denied.status)
