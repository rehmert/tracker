"""Release 627: representative gap-workstream forgery probes in real Chromium.

Strict localhost candidate only. These are negative probes, NOT signed
successful business workflows and NOT global CSRF deployment authorization.
"""
from __future__ import annotations
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import sync_playwright

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
    and DATA.is_dir() and DATA.name == "data"
    and DATA.parent.name.startswith("tracker-browser-qa.")
    and DATA.parent.parent == Path("/tmp").resolve()
):
    raise RuntimeError("627 gap probes require disposable strict HTTP/HTTPS QA")

pytestmark = pytest.mark.browser

# One representative from every ordinary unqualified route workstream.
# Individual routes remain unqualified until a positive signed lifecycle
# and a matching forged denial have been demonstrated.
WORKSTREAM_PROBES = (
    ("POST", "/protocols"),
    ("POST", "/blends/preview"),
    ("POST", "/purchases/999999/bac-water"),
    ("POST", "/labs/import-csv"),
    ("POST", "/pages/preview"),
    ("POST", "/coas/999999/verify"),
    ("POST", "/backups/restore-check"),
    ("POST", "/vials/999999/coas"),
    ("POST", "/calendar/exclude"),
    ("POST", "/lab-results/999999/edit"),
    ("DELETE", "/vitals/999999"),
    ("POST", "/food/photo"),
    ("POST", "/reconciliation/999999"),
    ("POST", "/reconstitution-calculator/preview"),
    ("POST", "/sources/999999/delete"),
)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.mark.parametrize("scheme", ("http", "https"))
@pytest.mark.parametrize("method,path", WORKSTREAM_PROBES)
def test_627_unqualified_workstream_forgery_denied(browser, scheme, method, path):
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    context = browser.new_context(ignore_https_errors=True)
    try:
        page = context.new_page()
        landing = page.goto(base + "/labs", wait_until="networkidle")
        assert landing and landing.status == 200
        token = page.evaluate("window.trackerCsrfToken?.() || ''")
        assert token.startswith("v1.")
        # Playwright request API bypasses the installed JS fetch wrapper while
        # preserving cookies in this isolated Chromium browser context.
        for headers, expected_report in (
            ({"Content-Type": "application/x-www-form-urlencoded"}, "missing"),
            ({
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Tracker-CSRF": "forged"
            }, "invalid"),
        ):
            response = page.request.fetch(
                base + path,
                method=method,
                headers=headers,
                data="placeholder=unused",
                max_redirects=0,
            )
            assert response.status == 403, (scheme, method, path, response.status)
            assert response.headers.get("x-tracker-csrf-report") == expected_report, (
                scheme, method, path, response.headers,
            )
    finally:
        context.close()
