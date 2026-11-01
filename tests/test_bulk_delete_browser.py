"""Playwright smoke coverage for the actual bulk-delete button JavaScript."""
import json
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.browser
TEMPLATE = Path(__file__).resolve().parents[1] / "app/templates/vials.html"
URL = "http://tracker-bulk-delete.test/vials"
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
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        posted = []
        alerts = []
        errors = []
        requests = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: requests.append((request.method, request.url)))

        def route_handler(route):
            request = route.request
            if request.method == "POST" and request.url.endswith("/delete-preview"):
                route.fulfill(status=200, content_type="application/json", body=json.dumps({
                    "ok": True,
                    "eligible": [{"id": 123, "name": "Test compound · vial-123"}],
                    "blocked": [],
                    "missing": [],
                    "snapshot": "preview-token-123",
                }))
            elif request.method == "POST" and request.url.endswith("/bulk/delete"):
                posted.append(request.post_data or "")
                location = "/vials?msg=Deleted" if succeeds else "/vials?err=Inventory+busy"
                route.fulfill(status=303, headers={"Location": location})
            else:
                route.fulfill(status=200, content_type="text/html", body=html_fixture())

        page.route("http://tracker-bulk-delete.test/**", route_handler)

        def on_dialog(dialog):
            if dialog.type == "alert":
                alerts.append(dialog.message)
            dialog.accept()

        page.on("dialog", on_dialog)
        page.goto(URL)
        page.evaluate(
            "(key) => sessionStorage.setItem(key, JSON.stringify({'123': {id: '123'}}))",
            KEY,
        )
        page.locator("#bulk-delete-selected").click()
        page.wait_for_timeout(850)
        assert posted, (
            f"Deletion request missing; JS errors={errors}, dialogs={alerts}, "
            f"requests={requests}"
        )

        if succeeds:
            page.wait_for_url("**/vials?msg=Deleted", timeout=10000)
            assert page.evaluate("(key) => sessionStorage.getItem(key)", KEY) is None
        else:
            page.wait_for_timeout(600)
            assert page.evaluate("(key) => sessionStorage.getItem(key)", KEY) is not None
            assert any("Inventory busy" in message for message in alerts)

        assert posted, "Bulk deletion should be submitted after preview confirmation"
        assert 'name="delete_preview_snapshot"' in posted[0]
        assert "preview-token-123" in posted[0]
        page.close()
        browser.close()
