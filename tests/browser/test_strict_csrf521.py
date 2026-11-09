"""Release 521: real Chromium strict-CSRF acceptance on disposable localhost.

Only collected by tracker-browser-qualify.sh against its isolated candidate.
Never imports or uses credentials, data, or endpoints from the installed app.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright

URL = os.environ.get("TRACKER_TEST_URL", "").rstrip("/")
HTTPS_URL = os.environ.get("TRACKER_TEST_HTTPS_URL", "").rstrip("/")
DATA = Path(os.environ.get("TRACKER_BROWSER_QA_DATA_DIR", "/")).resolve()
HTTP = urlsplit(URL)
HTTPS = urlsplit(HTTPS_URL)

if not (
    os.environ.get("TRACKER_TEST_ISOLATED") == "1"
    and os.environ.get("TRACKER_TEST_STRICT_CSRF") == "1"
    and HTTP.scheme == "http"
    and HTTPS.scheme == "https"
    and HTTP.hostname == HTTPS.hostname == "127.0.0.1"
    and HTTP.port not in (None, 8000)
    and HTTPS.port not in (None, 443, 8000, HTTP.port)
    and DATA.is_dir()
    and DATA.name == "data"
    and DATA.parent.name.startswith("tracker-browser-qa.")
    and DATA.parent.parent == Path("/tmp").resolve()
):
    raise RuntimeError(
        "Strict browser writes require isolated HTTPS localhost candidate"
    )

pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(headless=True)
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


def _navigate(page, path):
    response = page.goto(HTTPS_URL + path, wait_until="networkidle")
    assert response is not None and response.status == 200, (
        path, None if response is None else response.status
    )
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1."), "Real browser did not receive signed token"
    return token


def _post_response(page, path):
    return lambda response: (
        response.request.method in ("POST", "DELETE")
        and urlsplit(response.url).path == path
    )


def _verified(response, *, status):
    assert response.status == status, (
        response.status, response.text()[:150]
    )
    assert response.headers.get("x-tracker-csrf-report") == "valid", (
        response.headers.get("x-tracker-csrf-report")
    )


def test_521_native_urlencoded_compound_create_and_reject_forgery(tab):
    page, errors = tab
    _navigate(page, "/compounds")
    form = page.locator('form[action="/compounds"][method="post"]')
    assert form.count() == 1
    assert form.locator('input[name="csrf_token"]').count() == 1
    name = "QA strict native compound 521"
    form.locator('input[name="name"]').fill(name)
    with page.expect_response(_post_response(page, "/compounds")) as pending:
        form.get_by_role("button", name="Add compound").click()
    _verified(pending.value, status=303)
    expect(page.locator("body")).to_contain_text(name)

    # Browser API requests share the cookie but do NOT run our fetch wrapper.
    # This deliberately omits the submitted CSRF token and must fail closed.
    denied = page.request.post(
        HTTPS_URL + "/compounds",
        data={"name": "QA forged compound 521"},
        max_redirects=0,
    )
    assert denied.status == 403
    _navigate(page, "/compounds")
    assert "QA forged compound 521" not in page.locator("body").inner_text()
    assert not errors, errors


def test_521_native_coa_multipart_upload_and_signed_verification(tab):
    page, errors = tab
    _navigate(page, "/coas/new")
    form = page.locator('form[action="/coas/new"]')
    assert form.count() == 1
    assert form.locator('input[name="csrf_token"]').count() == 1
    choices = form.locator('select[name="vial_id"] option:not([value=""])')
    assert choices.count() >= 1, "Disposable vial fixtures are missing"
    vial = choices.first.get_attribute("value")
    assert vial and vial.isdecimal()
    form.locator('select[name="vial_id"]').select_option(vial)
    form.locator('input[name="lab_name"]').fill("QA strict COA 521")
    form.locator('input[name="tested_on"]').fill("2026-11-08")
    form.locator('input[name="file"]').set_input_files({
        "name": "strict-coa521.pdf",
        "mimeType": "application/pdf",
        "buffer": b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n",
    })
    with page.expect_response(_post_response(page, "/coas/new")) as pending:
        form.get_by_role("button", name="Create COA").click()
    _verified(pending.value, status=303)
    page.wait_for_url(re.compile(re.escape(HTTPS_URL) + r"/coas/[0-9]+(?:\?.*)?$"))
    expect(page.locator("body")).to_contain_text("QA strict COA 521")
    assert page.locator("body").get_by_text("strict-coa521.pdf").count() >= 1
    coa_id = urlsplit(page.url).path.split("/")[-1]
    page.locator('form[action="/coas/' + coa_id + '/verify"] select[name="status"]').select_option(index=0)
    with page.expect_response(
        _post_response(page, f"/coas/{coa_id}/verify")
    ) as verify_response:
        page.locator('form[action="/coas/' + coa_id + '/verify"] button').click()
    _verified(verify_response.value, status=303)

    # Real upload without token must be rejected rather than creating a COA.
    rejected = page.request.post(
        HTTPS_URL + "/coas/new",
        multipart={
            "vial_id": vial,
            "lab_name": "QA forbidden COA 521",
            "file": {
                "name": "forged.pdf",
                "mimeType": "application/pdf",
                "buffer": b"%PDF-1.4\n%%EOF\n",
            },
        },
        max_redirects=0,
    )
    assert rejected.status == 403
    assert "QA forbidden COA 521" not in page.request.get(
        HTTPS_URL + "/coas"
    ).text()
    assert not errors, errors


def test_521_htmx_preview_writes_include_signed_header(tab):
    page, errors = tab
    _navigate(page, "/pages/new")
    editor = page.locator("#notes-body")
    assert editor.get_attribute("hx-post") == "/pages/preview"
    with page.expect_response(_post_response(page, "/pages/preview")) as pending:
        editor.fill("**Strict HTMX preview 521**")
    _verified(pending.value, status=200)
    expect(page.locator("#preview")).to_contain_text(
        "Strict HTMX preview 521"
    )
    assert not errors, errors


def test_521_same_origin_fetch_auto_header_and_missing_header_denial(tab):
    page, errors = tab
    token = _navigate(page, "/compounds")
    requests = []

    def capture(request):
        if request.method == "POST" and urlsplit(request.url).path == "/compounds":
            requests.append(request.all_headers())

    page.on("request", capture)
    name = "QA strict fetch compound 521"
    result = page.evaluate(
        """async name => {
          const fields = new URLSearchParams({
            name, category: 'peptide', primary_unit: 'mg'
          });
          const response = await fetch('/compounds', {
            method: 'POST', body: fields
          });
          return {
            status: response.status,
            redirected: response.redirected
          };
        }""",
        name,
    )
    assert result == {"status": 200, "redirected": True}, result
    assert requests and requests[-1].get("x-tracker-csrf") == token
    _navigate(page, "/compounds")
    expect(page.locator("body")).to_contain_text(name)
    denied = page.request.post(
        HTTPS_URL + "/pk/compounds",
        data="{}",
        headers={"Content-Type": "application/json"},
        max_redirects=0,
    )
    assert denied.status == 403
    assert not errors, errors


def test_521_htmx_delete_vitals_needs_token_and_preserves_other_records(tab):
    page, errors = tab
    _navigate(page, "/vitals")
    form = page.locator('form[action="/vitals"][method="post"]')
    form.locator('input[name="weight"]').fill("180")
    form.locator('input[name="context"]').fill("QA STRICT VITAL 521")
    with page.expect_response(_post_response(page, "/vitals")) as pending:
        form.get_by_role("button", name="Save reading").click()
    _verified(pending.value, status=303)
    row = page.locator("tr").filter(has_text="QA STRICT VITAL 521")
    expect(row).to_have_count(1)
    button = row.locator('button[hx-delete]')
    url = urlsplit(button.get_attribute("hx-delete") or "").path
    assert re.fullmatch(r"/vitals/[0-9]+", url)
    page.on("dialog", lambda dialog: dialog.accept())
    with page.expect_response(_post_response(page, url)) as pending:
        button.click()
    _verified(pending.value, status=200)
    expect(page.locator("tr").filter(has_text="QA STRICT VITAL 521")).to_have_count(0)
    assert not errors, errors
