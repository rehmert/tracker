"""Release 653: Manage COA test types row actions remain horizontal and compact.

This tests the rendered Tracker template with the real stylesheet in Chromium,
without a live server, full regression suite, or changes to the installed DB.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[1]


def _table_page():
    with TestClient(app) as client:
        response = client.get("/coa-test-types")
        assert response.status_code == 200
        html = response.text
    assert '/static/css/tracker-coa-type-actions653.css?v=653' in html
    begin = '<div class="scroll"><table class="coa-type-table653">'
    end = '</table></div>'
    assert html.count(begin) == 1
    start = html.index(begin)
    stop = html.index(end, start) + len(end)
    content = html[start:stop]
    assert 'coa-type-action-row653' in content
    styles = "\n".join([
        (ROOT / "app/static/app.css").read_text(encoding="utf-8"),
        (ROOT / "app/static/css/tracker-mobile-density600.css").read_text(
            encoding="utf-8"
        ),
        (ROOT / "app/static/css/tracker-coa-type-actions653.css").read_text(
            encoding="utf-8"
        ),
    ])
    return (
        '<!doctype html><html><head><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        f'<style>{styles}</style></head>'
        f'<body><main id="main-content">{content}</main></body></html>'
    )


def test_653_manage_action_markup_and_css_contract():
    html = _table_page()
    assert 'class="coa-type-action-row653"' in html
    assert 'class="coa-type-toggle-form653"' in html
    assert 'form="coa-type-edit-' in html
    assert 'action="/coa-test-types/' in html
    css = (ROOT / "app/static/css/tracker-coa-type-actions653.css").read_text(
        encoding="utf-8"
    )
    assert "flex-wrap: nowrap" in css
    assert "flex-direction: row" in css
    assert ".coa-type-toggle-form653" in css
    assert "margin: 0" in css


def test_653_manage_actions_are_side_by_side_at_desktop_tablet_and_phone():
    from playwright.sync_api import sync_playwright

    html = _table_page()
    with sync_playwright() as browser_api:
        browser = browser_api.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 850})
            page.set_content(html, wait_until="domcontentloaded")
            rows = page.locator(".coa-type-table653 tbody tr")
            assert rows.count() >= 24, "Expected the built-in test catalog"
            first = rows.first
            actions = first.locator(".coa-type-action-row653")
            save = actions.locator('button[form^="coa-type-edit-"]')
            toggle = actions.locator('form.coa-type-toggle-form653 button')
            assert save.count() == toggle.count() == 1
            form_id = save.get_attribute("form")
            assert first.locator(f'form[id="{form_id}"]').count() == 1
            assert first.locator(
                f'input[name="label"][form="{form_id}"]'
            ).count() == 1
            assert first.locator(
                f'input[name="group_name"][form="{form_id}"]'
            ).count() == 1
            assert first.locator(
                'form.coa-type-toggle-form653[action$="/toggle"]'
            ).count() == 1

            for width in (1280, 760, 390, 320):
                page.set_viewport_size({"width": width, "height": 850})
                for toggle_label in ("Deactivate", "Reactivate"):
                    toggle.evaluate("(button, value) => button.textContent = value", toggle_label)
                    left = save.bounding_box()
                    right = toggle.bounding_box()
                    cell = first.locator("td.coa-type-action-cell653").bounding_box()
                    assert left and right and cell
                    assert abs(left["y"] - right["y"]) < 3, (width, toggle_label)
                    assert right["x"] >= left["x"] + left["width"] - 2
                    assert right["x"] + right["width"] <= cell["x"] + cell["width"] + 2
                    assert cell["height"] <= 80, (width, toggle_label, cell)
                if width <= 390:
                    scroll = page.locator(".coa-type-table653").locator("xpath=..")
                    assert scroll.evaluate(
                        "(el) => el.scrollWidth > el.clientWidth"
                    ), "Narrow tables should scroll horizontally, never stack actions"
            page.close()
        finally:
            browser.close()
