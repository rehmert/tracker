"""Release 627: genuine signed COA upload, edit, verify, delete in Chromium.

All writes and PDF bytes are synthetic within the isolated browser QA server.
"""
from __future__ import annotations
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from playwright.sync_api import expect, sync_playwright

URL = os.environ.get("TRACKER_TEST_URL", "").rstrip("/")
HTTPS_URL = os.environ.get("TRACKER_TEST_HTTPS_URL", "").rstrip("/")
DATA = Path(os.environ.get("TRACKER_BROWSER_QA_DATA_DIR", "/")).resolve()
HTTP, HTTPS = urlsplit(URL), urlsplit(HTTPS_URL)
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
    raise RuntimeError("627 COA lifecycle requires isolated strict QA")

pytestmark = pytest.mark.browser
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        chromium = playwright.chromium.launch(headless=True)
        yield chromium
        chromium.close()


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_627_signed_coa_multipart_edit_verify_delete_and_forgery(browser, scheme):
    base = URL if scheme == "http" else HTTPS_URL
    context = browser.new_context(ignore_https_errors=True)
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        landing = page.goto(base + "/coas/new", wait_until="networkidle")
        assert landing is not None and landing.status == 200
        token = page.evaluate("window.trackerCsrfToken?.() || ''")
        assert token.startswith("v1.")
        form = page.locator('form[action="/coas/new"][method="post"]')
        assert form.count() == 1
        assert form.locator('input[name="csrf_token"]').input_value() == token
        option = form.locator('select[name="vial_id"] option:not([value=""])').first
        vial = option.get_attribute("value")
        assert vial and vial.isdecimal()
        lab = "QA627 COA " + scheme + " " + uuid4().hex[:10]
        form.locator('select[name="vial_id"]').select_option(vial)
        form.locator('input[name="lab_name"]').fill(lab)
        form.locator('input[name="tested_on"]').fill("2026-11-14")
        form.locator('input[name="file"]').set_input_files({
            "name": "qa627-coa.pdf",
            "mimeType": "application/pdf",
            "buffer": PDF,
        })
        rejected = page.request.post(
            base + "/coas/new",
            multipart={"vial_id": vial, "lab_name": lab + " unsigned"},
            max_redirects=0,
        )
        assert rejected.status == 403
        with page.expect_response(lambda r: (
            r.request.method == "POST" and urlsplit(r.url).path == "/coas/new"
        )) as pending:
            form.get_by_role("button", name="Create COA").click()
        accepted = pending.value
        assert accepted.status == 303
        assert accepted.headers.get("x-tracker-csrf-report") == "valid"
        page.wait_for_url(re.compile(re.escape(base) + r"/coas/[0-9]+(?:[?].*)?$"))
        route = urlsplit(page.url).path
        # The laboratory name is rendered in an input, not body text.
        expect(page.locator('input[name="lab_name"]')).to_have_value(lab)
        # Release 650: one filename review link in the unified table; no
        # special "view existing/original" link remains in the editor.
        document = page.locator("#test-documents").get_by_role(
            "link", name="qa627-coa.pdf", exact=True,
        )
        expect(document).to_be_visible()
        assert document.get_attribute("href") == route + "/original-file"
        assert page.get_by_role("link", name="qa627-coa.pdf", exact=True).count() == 1
        # Consolidated test categories are selected in a native, touch-friendly
        # expandable checkbox group rather than the removed single combobox.
        expect(page.locator("#test-documents details.coa-test-multi651").first
               .locator("summary")).to_be_visible()
        assert page.locator("#test-documents input[data-coa-multi-choice]").count() >= 20
        expect(page.get_by_role(
            "radio", name="Make qa627-coa.pdf the default COA document"
        )).to_be_checked()

        # Release 651: a consolidated report selects multiple test categories
        # through the real browser, saves with signed AJAX and persists on reload.
        picker = page.locator("#test-documents details.coa-test-multi651").first
        picker.locator("summary").click()
        picker.locator('input[value="Purity"]').check()
        picker.locator('input[value="Identity"]').check()
        with page.expect_response(lambda response: (
            response.request.method == "POST"
            and urlsplit(response.url).path == route + "/attachments/test-types"
        )) as pending_tests:
            page.get_by_role("button", name="Save all test types").click()
        saved_tests = pending_tests.value
        assert saved_tests.status == 200
        assert saved_tests.json()["updated"] == 1
        assert saved_tests.headers.get("x-tracker-csrf-report") == "valid"
        page.reload(wait_until="networkidle")
        persisted = page.locator("#test-documents details.coa-test-multi651").first
        expect(persisted.locator('input[value="Purity"]')).to_be_checked()
        expect(persisted.locator('input[value="Identity"]')).to_be_checked()
        expect(page.locator("#test-documents").get_by_role(
            "link", name="qa627-coa.pdf", exact=True,
        )).to_be_visible()

        def signed(path, data):
            bad = page.request.post(base + path, form=data, max_redirects=0)
            assert bad.status == 403, (scheme, path, "forged")
            good = page.request.post(
                base + path, form=data, max_redirects=0,
                headers={"X-Tracker-CSRF": token},
            )
            assert good.status == 303, (scheme, path, good.status)
            assert good.headers.get("x-tracker-csrf-report") == "valid"

        revised = lab + " updated"
        signed(route + "/edit", {"lab_name": revised, "tested_on": "2026-11-14"})
        detail = page.request.get(base + route)
        assert detail.status == 200 and revised in detail.text()

        # A genuine existing COA verification POST with valid status choice.
        page.goto(base + route, wait_until="networkidle")
        select = page.locator(f'form[action="{route}/verify"] select[name="status"]')
        assert select.count() == 1
        assert select.locator('option[value="verified"]').count() == 1
        signed(route + "/verify", {
            "status": "verified", "verification_notes": "QA627 verified",
        })
        verified = page.request.get(base + route)
        assert verified.status == 200
        assert "QA627 verified" in verified.text()

        signed(route + "/delete", {})
        assert page.request.get(base + route).status == 404
        assert not errors, errors
    finally:
        context.close()
