"""Release 627: real signed native create flows on disposable HTTP and HTTPS.

Positive persistence and tokenless denial for protocols, pages, and labs.
Never connects to installed Tracker. Existing strict browser gate provides
a fresh localhost database and both HTTP and TLS proxy endpoints.
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
    and DATA.name == "data"
    and DATA.is_dir()
    and DATA.parent.parent == Path("/tmp").resolve()
    and re.fullmatch(r"tracker-browser-qa[.][A-Za-z0-9_]{8}", DATA.parent.name)
):
    raise RuntimeError("627 signed lifecycle QA requires disposable localhost")

pytestmark = pytest.mark.browser

WORKFLOWS = (
    ("protocols", "/protocols", "/protocols"),
    ("pages", "/pages/new", "/pages"),
    ("labs", "/labs/new", "/labs"),
)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        chromium = playwright.chromium.launch(headless=True)
        yield chromium
        chromium.close()


@pytest.mark.parametrize("scheme", ("http", "https"))
@pytest.mark.parametrize("kind,landing_path,write_path", WORKFLOWS)
def test_627_signed_native_create_persists_and_forgery_denied(
    browser, scheme, kind, landing_path, write_path,
):
    base = URL if scheme == "http" else HTTPS_URL
    context = browser.new_context(ignore_https_errors=True)
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        landing = page.goto(base + landing_path, wait_until="networkidle")
        assert landing is not None and landing.status == 200
        token = page.evaluate("window.trackerCsrfToken?.() || ''")
        assert token.startswith("v1.")
        form = page.locator(f'form[action="{write_path}"][method="post" i]')
        assert form.count() == 1, (kind, scheme)
        signed = form.locator('input[name="csrf_token"]')
        assert signed.count() == 1
        assert signed.input_value() == token

        name = "QA 627 " + kind + " " + scheme + " " + uuid4().hex[:12]
        if kind == "protocols":
            form.locator('input[name="name"]').fill(name)
            forged_fields = {"name": name + " unsigned"}
            verify_path = "/protocols"
            button_name = "Create"
        elif kind == "pages":
            form.locator('input[name="title"]').fill(name)
            # Body can be empty: creation must still persist the title.
            forged_fields = {"title": name + " unsigned", "body": ""}
            verify_path = "/pages"
            button_name = "Save page"
        else:
            form.locator('input[name="drawn_on"]').fill("2026-11-12")
            form.locator('input[name="lab_name"]').fill(name)
            form.locator('input[name="analyte"]').first.fill("QA627 Marker")
            form.locator('input[name="value"]').first.fill("23.5")
            form.locator('input[name="unit"]').first.fill("ng/mL")
            forged_fields = {"drawn_on": "2026-11-12",
                             "lab_name": name + " unsigned"}
            verify_path = "/labs"
            button_name = "Save report"

        # Real browser context retains the cookie while request API bypasses
        # native form token injection. This is an intentional forged replay.
        if kind == "labs":
            denied = page.request.post(
                base + write_path,
                multipart=forged_fields,
                max_redirects=0,
            )
        else:
            denied = page.request.post(
                base + write_path,
                data=forged_fields,
                max_redirects=0,
            )
        assert denied.status == 403, (kind, scheme, denied.status)

        with page.expect_response(lambda response: (
            response.request.method == "POST"
            and urlsplit(response.url).path == write_path
        )) as pending:
            form.get_by_role("button", name=button_name).click()
        accepted = pending.value
        assert accepted.status == 303, (kind, scheme, accepted.status)
        assert accepted.headers.get("x-tracker-csrf-report") == "valid"
        page.wait_for_url(re.compile(re.escape(base + write_path) + r"/[0-9]+(?:[?].*)?$"))
        expect(page.locator("body")).to_contain_text(name)
        created_path = urlsplit(page.url).path
        assert re.fullmatch(re.escape(write_path) + r"/[0-9]+", created_path)

        page.goto(base + verify_path, wait_until="networkidle")
        expect(page.locator("body")).to_contain_text(name)
        assert name + " unsigned" not in page.locator("body").inner_text()

        # Extend the real signed native creation with browser-context API
        # updates, then delete only the synthetic record created above.
        # The API calls are independently signed but not native-form clicks.
        if kind == "protocols":
            next_path, fields, marker = created_path + "/active", {}, "protocol"
        elif kind == "pages":
            next_path = created_path
            fields = {"title": name + " revised", "body": "QA627 revised text"}
            marker = name + " revised"
        else:
            next_path = created_path + "/results"
            fields = {"analyte": "QA627 Extra", "value": "9.1", "unit": "mg/dL"}
            marker = "QA627 Extra"

        unsigned_update = page.request.post(
            base + next_path, data=fields, max_redirects=0,
        )
        assert unsigned_update.status == 403, (kind, scheme, "update forgery")

        signed_update = page.request.post(
            base + next_path, data=fields,
            headers={"X-Tracker-CSRF": token}, max_redirects=0,
        )
        assert signed_update.status == 303, (
            kind, scheme, "signed update", signed_update.status,
        )
        assert signed_update.headers.get("x-tracker-csrf-report") == "valid"

        persisted = page.request.get(base + created_path)
        assert persisted.status == 200
        if kind != "protocols":
            assert marker in persisted.text()
        else:
            # Protocol active status is a state change, not a label edit.
            assert "Active" in persisted.text()

        delete_path = created_path + "/delete"
        denied_delete = page.request.post(
            base + delete_path, data={}, max_redirects=0,
        )
        assert denied_delete.status == 403, (kind, scheme, "delete forgery")
        signed_delete = page.request.post(
            base + delete_path, data={},
            headers={"X-Tracker-CSRF": token}, max_redirects=0,
        )
        assert signed_delete.status == 303, (
            kind, scheme, "signed delete", signed_delete.status,
        )
        assert signed_delete.headers.get("x-tracker-csrf-report") == "valid"
        assert page.request.get(base + created_path).status == 404
        assert not errors, (kind, scheme, errors)
    finally:
        context.close()
