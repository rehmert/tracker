"""Release 576: isolated strict-CSRF Chromium acceptance for risky writes.

These tests are collected ONLY by tracker-browser-qualify.sh against the
disposable localhost app/database. They must never address installed Tracker.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import pytest
from playwright.sync_api import sync_playwright, expect

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
    raise RuntimeError("Release 576 browser writes require isolated strict localhost QA")

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


def _visit(page, base, path):
    response = page.goto(base + path, wait_until="networkidle")
    assert response is not None and response.status == 200, (path, response)
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1."), "Signed browser CSRF cookie unavailable"
    return token


def _fixture_vial(page, base, marker):
    _visit(page, base, "/coas/new")
    options = page.locator('select[name="vial_id"] option').filter(has_text=marker)
    assert options.count() == 1, ("Missing isolated preparation fixture", marker)
    value = options.first.get_attribute("value")
    assert value and value.isdecimal()
    return value


def _posted(path):
    return lambda response: (
        response.request.method == "POST"
        and urlsplit(response.url).path == path
    )


def _assert_valid(response, status):
    assert response.status == status, (response.status, response.text()[:160])
    assert response.headers.get("x-tracker-csrf-report") == "valid"


@pytest.mark.parametrize("scheme,marker", (
    ("http", "QA preparation HTTP 576"),
    ("https", "QA preparation HTTPS 576"),
))
def test_576_real_preparation_correction_signed_and_forged(tab, scheme, marker):
    page, errors = tab
    base = URL if scheme == "http" else HTTPS_URL
    vid = _fixture_vial(page, base, marker)
    token = _visit(page, base, "/vials/" + vid)

    # This fixture is reserved for the correction case, not other browser tests.
    recon_path = "/vials/" + vid + "/reconstitute"
    recon = page.locator('form[action="' + recon_path + '"]')
    assert recon.count() == 1
    assert recon.locator('input[name="csrf_token"]').input_value() == token
    recon.locator('input[name="volume_ml"]').fill("1.25")
    with page.expect_response(_posted(recon_path)) as pending:
        recon.get_by_role("button", name="Record", exact=True).click()
    _assert_valid(pending.value, 303)

    _visit(page, base, "/vials/" + vid)
    links = page.locator('a[href^="/vials/' + vid + '/preparations/"][href$="/edit"]')
    assert links.count() == 1, "The real preparation event was not created"
    action = links.first.get_attribute("href")
    assert action and re.fullmatch(
        r"/vials/" + re.escape(vid) + r"/preparations/[0-9]+/edit", action
    )

    signed = _visit(page, base, action)
    assert signed == token
    # Base navigation also contains a logout POST form; target only the
    # correction form rather than assuming one POST on the entire page.
    form = page.locator('form[method="post"].grid').filter(has_text="Save correction")
    assert form.count() == 1
    assert form.get_attribute("action") is None  # implicit current-page action
    assert form.locator('input[name="csrf_token"]').input_value() == signed

    denied = page.request.post(
        base + action,
        data={"notes": "QA FORGED CORRECTION 576"},
        max_redirects=0,
    )
    assert denied.status == 403

    update = "QA signed preparation correction 576 " + scheme
    form.locator('input[name="notes"]').fill(update)
    with page.expect_response(_posted(action)) as pending:
        form.get_by_role("button", name="Save correction").click()
    _assert_valid(pending.value, 303)
    expect(page.locator("body")).to_contain_text(update)
    assert "QA FORGED CORRECTION 576" not in page.locator("body").inner_text()
    assert not errors, errors


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_576_bulk_preview_fetch_and_origin_fail_closed(tab, scheme):
    page, errors = tab
    base = URL if scheme == "http" else HTTPS_URL
    vid = _fixture_vial(page, base, "QA Alpha 511")
    token = _visit(page, base, "/vials")
    captures = []

    def capture(request):
        if (
            request.method == "POST"
            and urlsplit(request.url).path.startswith("/vials/bulk/")
        ):
            captures.append(request.all_headers())

    page.on("request", capture)

    for path in (
        "/vials/bulk/validate-selection",
        "/vials/bulk/delete-preview",
    ):
        result = page.evaluate("""async ({path, id}) => {
          const form = new FormData();
          form.append('vial_ids', id);
          const response = await fetch(path, {
            method: 'POST', body: form, credentials: 'same-origin'
          });
          const payload = await response.json();
          return {
            status: response.status,
            csrf: response.headers.get('x-tracker-csrf-report'),
            ok: payload.ok
          };
        }""", {"path": path, "id": vid})
        assert result == {"status": 200, "csrf": "valid", "ok": True}, result

        unsigned = page.request.post(
            base + path, multipart={"vial_ids": vid}, max_redirects=0
        )
        assert unsigned.status == 403, (path, unsigned.status)

        forged = page.request.post(
            base + path,
            multipart={"vial_ids": vid},
            headers={"X-Tracker-CSRF": "v1.forged"},
            max_redirects=0,
        )
        assert forged.status == 403, (path, forged.status)

        cross_site = page.request.post(
            base + path,
            multipart={"vial_ids": vid},
            headers={
                "Origin": "https://cross-site.invalid",
                "Sec-Fetch-Site": "cross-site",
                "X-Tracker-CSRF": token,
            },
            max_redirects=0,
        )
        assert cross_site.status == 403, (path, cross_site.status)

    assert len(captures) == 2
    assert all(headers.get("x-tracker-csrf") == token for headers in captures)
    _visit(page, base, "/vials/" + vid)  # previews must not delete the vial
    assert not errors, errors


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_576_large_form_body_requires_signed_header(tab, scheme):
    page, errors = tab
    base = URL if scheme == "http" else HTTPS_URL
    vid = _fixture_vial(page, base, "QA Alpha 511")
    token = _visit(page, base, "/vials")
    path = "/vials/bulk/validate-selection"
    body = urlencode({"vial_ids": vid, "padding": "x" * (70 * 1024)})
    assert len(body.encode("utf-8")) > 64 * 1024

    # A body larger than middleware's inspection limit must fail without
    # a signed header, but a valid header must still work without mutation.
    missing = page.request.post(
        base + path,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        max_redirects=0,
    )
    assert missing.status == 403

    valid = page.request.post(
        base + path,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Tracker-CSRF": token,
        },
        max_redirects=0,
    )
    assert valid.status == 200, (valid.status, valid.text()[:120])
    assert valid.headers.get("x-tracker-csrf-report") == "valid"
    assert valid.json()["ok"] is True
    assert not errors, errors
