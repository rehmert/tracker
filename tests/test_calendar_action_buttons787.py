"""Release 787: real rendered calendar actions have consistent button styling."""
import os
import re

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from app.main import app
from tests.test_calendar_quick_dose786 import seed


def rendered(client, url):
    response = client.get(url)
    assert response.status_code == 200
    source = response.text
    urls = re.findall(r'<link\b[^>]*?href="([^"]+)"[^>]*>', source, re.I)
    styles = []
    for uri in urls:
        if uri.startswith("/") and uri.split("?")[0].endswith(".css"):
            result = client.get(uri)
            assert result.status_code == 200, uri
            styles.append(result.text)
    source = re.sub(r'<script\b[^>]*>.*?</script>', '', source, flags=re.I | re.S)
    source = re.sub(r'<link\b[^>]*>', '', source, flags=re.I)
    return source, "\n".join(styles)


@pytest.mark.parametrize("width", [390, 1280])
def test_787_calendar_and_quick_dose_actions_are_real_styled_controls(width):
    day, items, _, _ = seed()
    path = f"/calendar/log-dose?protocol_item_id={items[0]}&scheduled_on={day}"
    with TestClient(app) as client:
        pages = [rendered(client, f"/calendar?month={day:%Y-%m}"), rendered(client, path)]
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None)
        try:
            page = browser.new_page(viewport={"width":width, "height":900})
            page.route("**/*", lambda route: route.abort())
            for markup, css in pages:
                page.set_content(markup)
                page.add_style_tag(content=css)
                scope = page.locator(".calendar-actions787")
                assert scope.count() == 1
                # GET destinations retain real links; POST actions retain buttons.
                assert scope.locator("a:not(.tracker-ui-action)").count() == 0
                assert scope.locator("button:not(.tracker-ui-action)").count() == 0
                if scope.locator("form[hx-post='/doses']").count():
                    selectors = ["button[type=submit]", "a:has-text('Cancel')"]
                    assert scope.locator("form[hx-post='/doses'] button[type=submit]").count() == 1
                else:
                    assert scope.locator(f'a[href="{path}"]').count() >= 1
                    assert scope.locator("a:has-text('Choose vial first'):visible").count() == 0
                    scope.locator("details.tracker-more790").evaluate_all("nodes => nodes.forEach(n => n.open = true)")
                    selectors = ["a:has-text('Log this dose')", "a:has-text('Choose vial first')",
                                 "a:has-text('Edit schedule')", "button:has-text('Hide projection')"]
                for selector in selectors:
                    control = scope.locator(selector + ":visible").first
                    assert control.count() == 1, selector
                    style = control.evaluate("""el => {
                        const s=getComputedStyle(el);
                        return {border:s.borderTopStyle,radius:parseFloat(s.borderTopLeftRadius),
                                height:el.getBoundingClientRect().height,decoration:s.textDecorationLine};
                    }""")
                    assert style["border"] == "solid" and style["radius"] > 0, (selector,style)
                    assert style["height"] >= (44 if width <= 760 else 36), (selector,style)
                    assert style["decoration"] == "none", (selector,style)
        finally:
            browser.close()
