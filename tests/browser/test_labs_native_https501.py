"""Release 501: native Chromium Labs form submission through local HTTPS proxy.

Real HTML multipart create (including an attachment), edit, and delete are
exercised without fabricating requests or modifying security settings.
All writes target the disposable backend created by tracker-browser-qualify.sh.
"""
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright

HTTP_URL = os.environ.get("TRACKER_TEST_URL", "")
HTTPS_URL = os.environ.get("TRACKER_TEST_HTTPS_URL", "").rstrip("/")
DATA = Path(os.environ.get("TRACKER_BROWSER_QA_DATA_DIR", "/")).resolve()
HTTP_PARTS = urlsplit(HTTP_URL)
HTTPS_PARTS = urlsplit(HTTPS_URL)

if not (
    os.environ.get("TRACKER_TEST_ISOLATED") == "1"
    and HTTP_PARTS.scheme == "http"
    and HTTP_PARTS.hostname == "127.0.0.1"
    and HTTP_PARTS.port not in (None, 8000)
    and HTTPS_PARTS.scheme == "https"
    and HTTPS_PARTS.hostname == "127.0.0.1"
    and HTTPS_PARTS.port not in (None, 443, HTTP_PARTS.port)
    and DATA.is_dir()
    and DATA.name == "data"
    and DATA.parent.name.startswith("tracker-browser-qa.")
    and DATA.parent.parent == Path("/tmp").resolve()
):
    raise RuntimeError(
        "Refusing native Labs writes without disposable HTTP and HTTPS QA URLs"
    )

pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(ignore_https_errors=True)
    tab = context.new_page()
    errors = []
    origins = []
    tab.on("pageerror", lambda error: errors.append(str(error)))

    def record_lab_post(request):
        if request.method == "POST" and (
            urlsplit(request.url).path.startswith("/labs")
            or urlsplit(request.url).path.startswith("/lab-results")
        ):
            headers = request.headers
            origins.append({
                "origin": headers.get("origin", "<absent>"),
                "fetch_site": headers.get("sec-fetch-site", "<absent>"),
                "content_type": headers.get("content-type", "<absent>")
                    .split(";", 1)[0],
            })

    tab.on("request", record_lab_post)
    yield tab, errors, origins
    context.close()


def submit_native(tab, control, *, expected_path, origin_events=None):
    with tab.expect_navigation(wait_until="domcontentloaded") as nav:
        control.click()
    response = nav.value
    assert response is not None
    actual_path = urlsplit(tab.url).path
    assert re.fullmatch(expected_path, actual_path), (
        "Native browser form failed: "
        f"HTTP {response.status}, path={actual_path}, "
        f"body={tab.locator('body').inner_text()[:180]}, "
        f"origin_metadata={(origin_events or [])[-1:]}"
    )
    assert response.status == 200
    return actual_path


def test_501_native_https_multipart_create_edit_delete_with_file(page):
    tab, errors, origins = page
    response = tab.goto(HTTPS_URL + "/labs/new", wait_until="networkidle")
    assert response is not None and response.status == 200
    assert tab.evaluate("location.protocol") == "https:"

    form = tab.locator("form[data-lab-manual-entry]")
    assert form.get_attribute("enctype") == "multipart/form-data"
    assert form.locator('input[name="csrf_token"]').count() == 1
    form.locator('input[name="drawn_on"]').fill("2026-11-08")
    form.locator('input[name="lab_name"]').fill("Native HTTPS QA Lab 501")
    row = form.locator("#lab-rows tr").first
    row.locator('input[name="analyte"]').fill("Native QA Analyte 501")
    row.locator('input[name="value"]').fill("16")
    row.locator('input[name="unit"]').fill("ng/mL")
    form.locator('input[name="file"]').set_input_files({
        "name": "native-qa-report.pdf",
        "mimeType": "application/pdf",
        "buffer": b"%PDF-1.4\n%%EOF\n",
    })
    report_path = submit_native(
        tab, form.get_by_role("button", name=re.compile("save report", re.I)),
        expected_path=r"/labs/[1-9][0-9]*", origin_events=origins,
    )
    expect(tab.locator("body")).to_contain_text(
        re.compile("Native HTTPS QA Lab 501", re.I)
    )
    expect(tab.locator("body")).to_contain_text("native-qa-report.pdf")

    # This is a real form submission, not the signed API-request helper.
    assert origins and origins[0]["content_type"] == "multipart/form-data"
    assert origins[0]["fetch_site"] == "same-origin"

    tab.locator("details.lab-edit-panel").first.evaluate(
        "(node) => { node.open = true; }"
    )
    edit = tab.locator('form[action="' + report_path + '/edit"]')
    edit.locator('input[name="lab_name"]').fill("Native HTTPS QA Lab 501 Edited")
    submit_native(
        tab, edit.get_by_role("button", name=re.compile("save report details", re.I)),
        expected_path=re.escape(report_path), origin_events=origins,
    )
    expect(tab.locator("h1")).to_contain_text(
        re.compile("Native HTTPS QA Lab 501 Edited", re.I)
    )

    # Browser-native deletion removes both report and attached file.
    tab.on("dialog", lambda dialog: dialog.accept())
    submit_native(
        tab,
        tab.locator('form[action="' + report_path + '/delete"] button'),
        expected_path=r"/labs", origin_events=origins,
    )
    assert tab.request.get(HTTPS_URL + report_path).status == 404
    assert not errors, errors


def test_501_https_rejects_cross_site_signed_lab_writes(page):
    tab, errors, _ = page
    response = tab.goto(HTTPS_URL + "/labs/new", wait_until="networkidle")
    assert response is not None and response.status == 200
    token = tab.evaluate("window.trackerCsrfToken?.() || ''")
    assert token

    response = tab.request.post(
        HTTPS_URL + "/labs",
        data={"drawn_on": "2026-11-08"},
        headers={
            "Origin": "https://attacker.invalid",
            "Sec-Fetch-Site": "cross-site",
            "X-Tracker-CSRF": token,
        },
        max_redirects=0,
    )
    assert response.status == 403
    assert "Cross-origin write request denied" in response.text()
    assert not errors, errors
