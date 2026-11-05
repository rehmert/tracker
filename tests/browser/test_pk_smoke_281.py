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

        assert not errors,'; '.join(errors)
        context.close()
        browser.close()
