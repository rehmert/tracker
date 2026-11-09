"""Release 522: real HTTPS Vitals workflows through a Host-rewriting QA proxy.

The disposable TLS proxy rewrites Host for Vitals mutations only, while
retaining the browser's public Origin and Sec-Fetch-Site. This reproduces
the rejected production request that prior same-host browser tests missed.
Never collect against an installed DEV/PROD service or real user database.
"""

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
    raise RuntimeError("Refusing Vitals writes without disposable HTTPS proxy QA")

pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        chromium = playwright.chromium.launch(headless=True)
        yield chromium
        chromium.close()


@pytest.fixture
def tab(browser):
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    errors = []
    metadata = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    def capture(request):
        path = urlsplit(request.url).path
        if request.method in ("POST", "DELETE") and (
            path == "/vitals" or re.fullmatch(
                r"/vitals/[1-9][0-9]{0,9}(?:/edit)?", path
            )
        ):
            headers = request.all_headers()
            metadata.append({
                "origin": headers.get("origin", "<absent>"),
                "fetch-site": headers.get("sec-fetch-site", "<absent>"),
                "csrf-header": "x-tracker-csrf" in headers,
                "path": path,
                "method": request.method,
            })

    page.on("request", capture)
    yield page, errors, metadata
    context.close()


def _go(page, path="/vitals"):
    result = page.goto(HTTPS_URL + path, wait_until="networkidle")
    assert result is not None and result.status == 200
    assert page.evaluate("window.trackerCsrfToken?.() || ''").startswith("v1.")


def _verify(response, expected):
    assert response.status == expected, (
        response.status, response.text()[:170]
    )
    assert response.headers.get("x-tracker-csrf-report") == "valid"


def test_522_real_native_https_vitals_create_edit_and_htmx_delete(tab):
    page, errors, metadata = tab
    _go(page)
    form = page.locator('form[action="/vitals"][method="post"]')
    assert form.count() == 1
    assert form.locator('input[name="csrf_token"]').count() == 1

    label = "QA Host Rewrite Vitals 522"
    form.locator('input[name="measured_at"]').fill("2026-11-08T20:30")
    form.locator('input[name="weight"]').fill("180")
    form.locator('input[name="context"]').fill(label)
    with page.expect_response(
        lambda resp: resp.request.method == "POST"
        and urlsplit(resp.url).path == "/vitals"
    ) as create:
        form.get_by_role("button", name="Save reading").click()
    _verify(create.value, 303)
    assert metadata and metadata[-1]["origin"] == HTTPS_URL, metadata
    assert metadata[-1]["fetch-site"] == "same-origin", metadata

    _go(page, "/vitals?days=3650")
    row = page.locator("tr").filter(has_text=label)
    expect(row).to_have_count(1)
    edit_link = row.locator('a[href*="/edit"]').get_attribute("href")
    assert edit_link and re.match(r"^/vitals/[1-9][0-9]*/edit", edit_link)
    _go(page, edit_link)
    edit = page.locator('form[data-tracker-vitals-entry="edit"]')
    edit.locator('input[name="context"]').fill("QA Host Rewrite Edited 522")
    with page.expect_response(
        lambda resp: resp.request.method == "POST"
        and urlsplit(resp.url).path.endswith("/edit")
    ) as update:
        edit.get_by_role("button", name="Save Changes").click()
    _verify(update.value, 303)

    _go(page, "/vitals?days=3650")
    edited_row = page.locator("tr").filter(has_text="QA Host Rewrite Edited 522")
    expect(edited_row).to_have_count(1)
    delete_button = edited_row.locator('button[hx-delete]')
    target = delete_button.get_attribute("hx-delete")
    assert target and re.fullmatch(r"/vitals/[1-9][0-9]*", target)
    page.on("dialog", lambda dialog: dialog.accept())
    with page.expect_response(
        lambda resp: resp.request.method == "DELETE"
        and urlsplit(resp.url).path == target
    ) as remove:
        delete_button.click()
    _verify(remove.value, 200)
    expect(page.locator("tr").filter(
        has_text="QA Host Rewrite Edited 522"
    )).to_have_count(0)
    assert len(metadata) >= 3
    assert all(item["fetch-site"] == "same-origin" for item in metadata)
    assert not errors, errors


def test_522_host_rewrite_does_not_allow_unsigned_or_cross_site_post(tab):
    page, errors, metadata = tab
    _go(page)
    token = page.evaluate("window.trackerCsrfToken()")
    headers = {"Origin": HTTPS_URL, "Sec-Fetch-Site": "same-origin"}

    unsigned = page.request.post(
        HTTPS_URL + "/vitals",
        data={
            "measured_at": "2026-11-08T20:30",
            "weight": "180",
            "context": "QA forbidden unsigned 522",
        },
        headers=headers, max_redirects=0,
    )
    assert unsigned.status == 403
    assert "Cross-origin write request denied" in unsigned.text()

    cross_site = page.request.post(
        HTTPS_URL + "/vitals",
        data={
            "measured_at": "2026-11-08T20:30",
            "weight": "180",
            "context": "QA forbidden cross site 522",
        },
        headers={
            "Origin": "https://attacker.invalid",
            "Sec-Fetch-Site": "cross-site",
            "X-Tracker-CSRF": token,
        },
        max_redirects=0,
    )
    assert cross_site.status == 403

    _go(page, "/vitals?days=3650")
    content = page.locator("body").inner_text()
    assert "QA forbidden unsigned 522" not in content
    assert "QA forbidden cross site 522" not in content
    assert not errors, errors
