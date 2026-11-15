"""Read-only PK Playwright smoke tests."""
import os
import pytest

pytest.importorskip('playwright.sync_api')
from playwright.sync_api import sync_playwright

BASE=os.environ.get(
    'TRACKER_TEST_URL',
    'http://127.0.0.1:8000'
).rstrip('/')


def test_pk_workspace_browser_smoke():
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)

        options={'viewport':{'width':1280,'height':900}}

        username=os.environ.get('TRACKER_TEST_USER')
        password=os.environ.get('TRACKER_TEST_PASSWORD')

        if username is not None and password is not None:
            options['http_credentials']={
                'username':username,
                'password':password
            }

        context=browser.new_context(**options)
        page=context.new_page()
        errors=[]

        page.on(
            'pageerror',
            lambda err:errors.append(str(err))
        )

        response=page.goto(
            BASE+'/pk',
            wait_until='domcontentloaded',
            timeout=30000
        )

        assert response is not None
        assert response.status==200

        page.locator(
            '#pkPanelControls'
        ).wait_for(timeout=10000)

        for element in (
            '#pkRevisionLoad',
            '#pkGrid217Run',
            '#pkGraphLayerControls'
        ):
            assert page.locator(element).count()==1

        # Release 628: essential workflow and legend remain available without
        # opening advanced controls; existing graph controls remain functional.
        assert page.locator(".pk628-steps li").count() == 3
        assert page.get_by_role("button", name="Use a protocol").count() == 1
        assert page.get_by_role("button", name="Build a schedule").count() == 1
        assert page.get_by_role("button", name="Compare scenarios").count() == 1
        assert page.get_by_role("button", name="Compare schedules").count() == 1
        assert page.locator(".pk628-graph-guide span").count() == 3
        options_panel = page.locator(".pk628-graph-options")
        assert options_panel.count() == 1
        assert options_panel.evaluate("(element) => element.open") is False
        options_panel.locator("summary").click()
        assert options_panel.evaluate("(element) => element.open") is True
        assert page.locator("#pkGraphLayerControls").is_visible()
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.locator(".pk628-intro").is_visible()
        assert page.locator(".pk-tabs").is_visible()
        assert page.locator("#pkResults #plot").count() == 1
        # Exercise the new graph orientation without running any PK writes.
        page.evaluate("""() => {
          window.trackerPkLastGraph = {
            rows: [
              {at: '2026-11-14T00:00:00', actual: 1, planned: 2},
              {at: '2026-11-15T00:00:00', actual: 1, planned: 2}
            ]
          };
          document.dispatchEvent(new Event('tracker:pk-graph-updated'));
        }""")
        assert "Showing " in page.locator("#pk628GraphHint").inner_text()
        assert "modeled estimates" in page.locator("#pk628GraphHint").inner_text()

        assert not errors,'; '.join(errors)
        context.close()
        browser.close()
