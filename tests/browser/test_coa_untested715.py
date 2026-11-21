"""Release 715: Chromium COA Untested is a true default, never an assumed test.

The fixture requires strict-CSRF localhost disposable browser QA. Both
HTTP and HTTPS are exercised without touching installed DEV/PROD records.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
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
    and DATA.is_dir() and DATA.name == "data" and not DATA.is_symlink()
    and DATA.parent.parent == Path("/tmp").resolve()
    and re.fullmatch(r"tracker-browser-qa[.][A-Za-z0-9_]{8}", DATA.parent.name)
):
    raise RuntimeError("715 browser test refuses non-disposable strict QA")

pytestmark = pytest.mark.browser


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_715_coa_default_untested_and_explicit_result_browser(scheme):
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        try:
            page = context.new_page()
            new = page.goto(base + "/coas/new", wait_until="networkidle")
            assert new is not None and new.status == 200

            form = page.locator('form[action="/coas/new"]')
            assert form.count() == 1
            picker = form.locator('select[name="endotoxin_result_kind"]')
            expect(picker).to_have_value("untested")
            expect(picker.locator('option[value="untested"]')).to_have_text("Untested")
            expect(picker.locator('option[value="lt1"]')).to_contain_text("<1 EU/vial")
            expect(picker.locator('option[value="exact"]')).to_have_text("Exact numeric result")
            vial_choice = form.locator('select[name="vial_id"] option:not([value=""])').first.get_attribute("value")
            assert vial_choice and vial_choice.isdecimal()
            lab = "QA715-" + scheme + "-" + uuid4().hex[:10]
            form.locator('select[name="vial_id"]').select_option(vial_choice)
            form.locator('input[name="lab_name"]').fill(lab)
            token = page.evaluate("window.trackerCsrfToken?.() || ''")
            assert token.startswith("v1.")
            with page.expect_response(
                lambda response: response.request.method == "POST"
                and urlsplit(response.url).path == "/coas/new"
            ) as pending:
                form.get_by_role("button", name="Create COA").click()
            assert pending.value.status == 303
            page.wait_for_url(re.compile(re.escape(base) + r"/coas/[0-9]+(?:[?].*)?$"))
            route = urlsplit(page.url).path
            detail = page.locator('form[action="' + route + '/edit"]')
            assert detail.count() == 1
            kind = detail.locator('select[name="endotoxin_result_kind"]')
            exact = detail.locator('input[name="endotoxin_eu_per_vial"]')
            expect(kind).to_have_value("untested")
            expect(exact).to_have_value("")

            kind.select_option("lt1")
            with page.expect_response(
                lambda r: r.request.method == "POST"
                and urlsplit(r.url).path == route + "/edit"
            ) as pending:
                detail.get_by_role("button", name="Save changes").click()
            assert pending.value.status == 303
            page.reload(wait_until="networkidle")
            expect(page.locator('select[name="endotoxin_result_kind"]')).to_have_value("lt1")

            detail = page.locator('form[action="' + route + '/edit"]')
            kind = detail.locator('select[name="endotoxin_result_kind"]')
            kind.select_option("exact")
            detail.locator('input[name="endotoxin_eu_per_vial"]').fill("4.308")
            with page.expect_response(
                lambda r: r.request.method == "POST"
                and urlsplit(r.url).path == route + "/edit"
            ) as pending:
                detail.get_by_role("button", name="Save changes").click()
            assert pending.value.status == 303
            page.reload(wait_until="networkidle")
            expect(page.locator('select[name="endotoxin_result_kind"]')).to_have_value("exact")
            expect(page.locator('input[name="endotoxin_eu_per_vial"]')).to_have_value("4.308")

            detail = page.locator('form[action="' + route + '/edit"]')
            detail.locator('select[name="endotoxin_result_kind"]').select_option("untested")
            detail.locator('input[name="endotoxin_eu_per_vial"]').fill("")
            with page.expect_response(
                lambda r: r.request.method == "POST"
                and urlsplit(r.url).path == route + "/edit"
            ) as pending:
                detail.get_by_role("button", name="Save changes").click()
            assert pending.value.status == 303
            page.reload(wait_until="networkidle")
            expect(page.locator('select[name="endotoxin_result_kind"]')).to_have_value("untested")
            expect(page.locator('input[name="endotoxin_eu_per_vial"]')).to_have_value("")

            # The separate vial-level COA creation form must use the same default.
            vial_page = page.goto(base + "/vials/" + vial_choice, wait_until="networkidle")
            assert vial_page is not None and vial_page.status == 200
            expect(page.locator(
                f'form[action="/vials/{vial_choice}/coas"] '
                'select[name="endotoxin_result_kind"]'
            )).to_have_value("untested")
            print("TARGETED_715_COA_UNTESTED=PASSED", flush=True)
        finally:
            context.close()
            browser.close()
