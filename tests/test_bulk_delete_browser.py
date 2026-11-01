"""Browser regression checks for real HTTP redirect behavior on vial deletion.

A temporary localhost HTTP server replaces Playwright's synthetic redirect
fulfillment, which doesn't behave like a browser's real fetch redirect chain.
No Tracker database or running service is used.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.browser
TEMPLATE = Path(__file__).resolve().parents[1] / "app/templates/vials.html"
KEY = "tracker.bulkVials.selection.v1"


def deletion_script():
    source = TEMPLATE.read_text(encoding="utf-8")
    marker = "/* TRACKER_BULK_VIAL_DELETE */"
    start = source.index(marker)
    end = source.index("</script>", start)
    return source[start:end]


def html_fixture():
    return f"""<!doctype html><html><body>
      <form id="bulk-vials"></form>
      <span id="bulk-toolbar-count">1</span>
      <input type="checkbox" class="bulk-vial-check" form="bulk-vials"
             name="vial_ids" value="123" checked>
      <button type="button" id="bulk-delete-selected">Delete selected</button>
      <script>{deletion_script()}</script>
    </body></html>"""


@pytest.mark.parametrize("succeeds", [True, False])
def test_delete_confirmation_and_persisted_selection(succeeds):
    posted = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def send_payload(self, content, content_type):
            payload = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            self.send_payload(html_fixture(), "text/html; charset=utf-8")

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            if self.path == "/vials/bulk/delete-preview":
                self.send_payload(json.dumps({
                    "ok": True,
                    "eligible": [{"id": 123, "name": "Test compound - vial-123"}],
                    "blocked": [],
                    "missing": [],
                    "snapshot": "preview-token-123",
                }), "application/json")
            elif self.path == "/vials/bulk/delete":
                posted.append(body)
                location = (
                    "/vials?msg=Deleted" if succeeds
                    else "/vials?err=Inventory+busy"
                )
                self.send_response(303)
                self.send_header("Location", location)
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                self.send_error(404)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_port}"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                alerts = []
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))

                def on_dialog(dialog):
                    if dialog.type == "alert":
                        alerts.append(dialog.message)
                    dialog.accept()

                page.on("dialog", on_dialog)
                page.goto(base + "/vials")
                page.evaluate(
                    "(key) => sessionStorage.setItem(key, JSON.stringify({'123': {id: '123'}}))",
                    KEY,
                )
                page.locator("#bulk-delete-selected").click()

                if succeeds:
                    page.wait_for_url(base + "/vials?msg=Deleted", timeout=10000)
                    assert page.evaluate(
                        "(key) => sessionStorage.getItem(key)", KEY
                    ) is None
                else:
                    page.wait_for_function(
                        "() => document.querySelector('#bulk-delete-selected')?.disabled === false",
                        timeout=10000,
                    )
                    page.wait_for_timeout(150)
                    assert page.url == base + "/vials"
                    assert page.evaluate(
                        "(key) => sessionStorage.getItem(key)", KEY
                    ) is not None
                    assert any("Inventory busy" in message for message in alerts)

                assert posted, f"Deletion request not submitted; JS errors={errors}"
                assert b'name="delete_preview_snapshot"' in posted[0]
                assert b"preview-token-123" in posted[0]
                assert not errors, errors
            finally:
                browser.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
