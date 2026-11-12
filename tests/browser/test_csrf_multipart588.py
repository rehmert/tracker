"""Combined 587–588: native multipart COA upload under strict HTTP and HTTPS.

Genuine Chromium form submission, separate from signed JavaScript fetch. All
uploaded data belongs to the disposable candidate server on 127.0.0.1.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

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
    and DATA.parent.parent == Path("/tmp").resolve()
    and re.fullmatch(r"tracker-browser-qa[.][A-Za-z0-9_]{8}", DATA.parent.name)
):
    raise RuntimeError("588 multipart QA requires disposable strict localhost")

pytestmark = pytest.mark.browser
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_588_real_native_coa_multipart_upload_and_forgery_denial(browser, scheme):
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    try:
        landing = page.goto(base + "/coas/new", wait_until="networkidle")
        assert landing is not None and landing.status == 200
        token = page.evaluate("window.trackerCsrfToken?.() || ''")
        assert token.startswith("v1.")
        form = page.locator('form[action="/coas/new"][method="post"]')
        assert form.count() == 1
        assert form.get_attribute("enctype") == "multipart/form-data"
        assert form.locator('input[name="csrf_token"]').input_value() == token
        choices = form.locator('select[name="vial_id"] option:not([value=""])')
        assert choices.count() >= 1
        vial = choices.first.get_attribute("value")
        assert vial and vial.isdecimal()
        name = "QA multipart 588 " + scheme + " " + uuid4().hex[:8]
        form.locator('select[name="vial_id"]').select_option(vial)
        form.locator('input[name="lab_name"]').fill(name)
        form.locator('input[name="tested_on"]').fill("2026-11-12")
        form.locator('input[name="file"]').set_input_files({
            "name": "qa-588.pdf", "mimeType": "application/pdf", "buffer": PDF,
        })
        # A tokenless multipart request with identical expected fields and a
        # viable PDF must fail before the endpoint can write an upload.
        bad_name = name + " unsigned"
        denied = page.request.post(base + "/coas/new", multipart={
            "vial_id": vial,
            "lab_name": bad_name,
            "tested_on": "2026-11-12",
            "file": {"name": "qa-588-unsigned.pdf",
                     "mimeType": "application/pdf", "buffer": PDF},
        }, max_redirects=0)
        assert denied.status == 403
        assert "CSRF token required" in denied.text()
        assert bad_name not in page.request.get(base + "/coas").text()
        with page.expect_response(lambda response: (
            response.request.method == "POST"
            and urlsplit(response.url).path == "/coas/new"
        )) as pending:
            form.get_by_role("button", name="Create COA").click()
        submitted = pending.value
        assert submitted.status == 303
        assert submitted.headers.get("x-tracker-csrf-report") == "valid"
        assert submitted.request.all_headers().get("content-type", "").startswith(
            "multipart/form-data"
        )
        page.wait_for_url(re.compile(re.escape(base) + r"/coas/[0-9]+(?:\?.*)?$"))
        expect(page.locator("body")).to_contain_text(name)
        assert not errors, errors
    finally:
        context.close()
