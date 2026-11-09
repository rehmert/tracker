"""Release 523: actual PROD browser login against isolated HTTPS candidate.

This module is intentionally outside tests/browser because the existing
Release 511 standard/strict browser inventory has separate phase ownership.
It is collected only by the explicit third PROD-mode candidate gate.
A normal backend test run skips it; no live installed service is touched.
"""
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest

if os.getenv("TRACKER_TEST_PROD_PARITY", "0") != "1":
    pytest.skip("PROD browser test requires isolated candidate", allow_module_level=True)

from playwright.sync_api import expect, sync_playwright

HTTP_URL = os.environ.get("TRACKER_TEST_URL", "").rstrip("/")
HTTPS_URL = os.environ.get("TRACKER_TEST_HTTPS_URL", "").rstrip("/")
DATA = Path(os.environ.get("TRACKER_BROWSER_QA_DATA_DIR", "/")).resolve()
HTTP = urlsplit(HTTP_URL)
HTTPS = urlsplit(HTTPS_URL)
if not (
    os.getenv("TRACKER_TEST_ISOLATED") == "1"
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
    raise RuntimeError("Refusing PROD browser tests without disposable candidate")

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
    tab.on("pageerror", lambda error: errors.append(str(error)))
    yield tab, errors
    context.close()


def _goto(tab, path):
    response = tab.goto(HTTPS_URL + path, wait_until="networkidle")
    assert response is not None and response.status == 200, (
        path, None if response is None else response.status
    )


def _login(tab, username, password):
    _goto(tab, "/login")
    assert tab.locator('input[name="csrf_token"]').count() == 1
    tab.locator('input[name="username"]').fill(username)
    tab.locator('input[name="password"]').fill(password)
    with tab.expect_response(
        lambda response:
        response.request.method == "POST"
        and urlsplit(response.url).path == "/login"
    ) as response:
        tab.get_by_role("button", name="Sign In").click()
    assert response.value.status == 303, (
        response.value.status, response.value.text()[:180]
    )


def test_523_prod_admin_signin_security_and_logout(page):
    tab, errors = page
    # An anonymous GET must redirect to browser login, not demand Basic Auth.
    response = tab.goto(HTTPS_URL + "/", wait_until="domcontentloaded")
    assert response is not None
    assert urlsplit(tab.url).path == "/login"
    assert "www-authenticate" not in response.headers
    expect(tab.locator("h1")).to_contain_text("Tracker PROD")
    _login(tab, "qa-admin523", "qa-pass-admin523")

    tab.wait_for_url(HTTPS_URL + "/")
    expect(tab.locator("body")).to_contain_text("Tracker")
    _goto(tab, "/account/security")
    expect(tab.get_by_role("heading", name="Account Security")).to_be_visible()
    _goto(tab, "/account/users")
    expect(tab.locator("body")).to_contain_text("qa-member523")

    # Return to the main app shell: the standalone User Management page
    # correctly has no logout form of its own.
    _goto(tab, "/")
    # Logout must revoke the signed administrator session, not just a UI flag.
    tab.locator('form[action="/logout"] input[name="csrf_token"]').wait_for()
    with tab.expect_response(
        lambda r: r.request.method == "POST"
        and urlsplit(r.url).path == "/logout"
    ) as out:
        tab.locator('form[action="/logout"] button').click()
    assert out.value.status == 303
    tab.wait_for_url(HTTPS_URL + "/login")
    denied = tab.request.get(HTTPS_URL + "/account/users", max_redirects=0)
    assert denied.status == 303
    assert not errors, errors


def test_523_prod_secondary_login_private_and_admin_denial(page):
    tab, errors = page
    _login(tab, "qa-member523", "qa-pass-member523")
    tab.wait_for_url(HTTPS_URL + "/secondary/overview")
    expect(tab.locator("body")).to_contain_text("Private workspace")

    denied = tab.request.get(HTTPS_URL + "/account/users", max_redirects=0)
    assert denied.status == 303
    assert denied.headers["location"].startswith("/login")
    _goto(tab, "/secondary/security")
    expect(tab.locator("body")).to_contain_text("Active Sessions")

    # Logout must revoke only the secondary session, without exposing
    # administrator routes or permitting reuse of the old cookie.
    _goto(tab, "/secondary/overview")
    form = tab.locator('form[action="/secondary/logout"]')
    assert form.locator('input[name="csrf_token"]').count() == 1
    with tab.expect_response(
        lambda r: r.request.method == "POST"
        and urlsplit(r.url).path == "/secondary/logout"
    ) as logout:
        form.get_by_role("button", name="Sign Out").click()
    assert logout.value.status == 303
    tab.wait_for_url(HTTPS_URL + "/secondary/login")
    denied = tab.request.get(
        HTTPS_URL + "/secondary/overview", max_redirects=0
    )
    assert denied.status == 303
    assert denied.headers["location"] == "/secondary/login"
    assert not errors, errors
