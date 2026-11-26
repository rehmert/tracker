"""Exercise real scoped routes, native disclosures, geometry and atomic meal reuse."""
from datetime import date
from pathlib import Path
import os

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright, expect
from sqlalchemy import text

from app.main import app
from app.routers import food_bundle376
from tests.test_food_bundle376 import setup, add
from tests.test_calendar_action_buttons787 import rendered

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app/static"


def test_792_prior_meal_copy_preserves_portions_and_rejects_stale_or_duplicate(setup):
    client, engine = setup
    assert add(client, day="2026-11-05", meal="Breakfast").status_code == 303
    assert add(client, day="2026-11-05", meal="Breakfast").status_code == 303
    preview = food_bundle376.prior_meals792("2026-11-06", engine)
    assert len(preview) == 1 and len(preview[0]["rows"]) == 2
    fields = dict(day="2026-11-06", meal="Breakfast", snapshot=preview[0]["snapshot"])
    route = "/food/meal/copy-prior792"
    assert client.post(route, data=dict(fields, snapshot="stale"), follow_redirects=False).status_code == 409
    saved = client.post(route, data=fields, follow_redirects=False)
    assert saved.status_code == 303
    assert saved.headers["location"] == "/food?day=2026-11-06#food-recorded"
    assert client.post(route, data=fields, follow_redirects=False).status_code == 409
    assert food_bundle376.prior_meals792("2026-11-06", engine) == []
    with engine.connect() as db:
        source = db.execute(text("SELECT product_id, servings FROM tracker_food_entries WHERE eaten_on='2026-11-05' ORDER BY id")).all()
        copied = db.execute(text("SELECT product_id, servings FROM tracker_food_entries WHERE eaten_on='2026-11-06' ORDER BY id")).all()
        assert copied == source and len(copied) == 2


def test_792_domain_routes_and_scoped_assets():
    with TestClient(app) as client:
        for path in ("/vials?status=in_use", "/vials?status=sealed", "/purchases", "/blends",
                     "/protocols", "/inventory-health"):
            r = client.get(path)
            assert r.status_code == 200, path
            assert 'aria-label="Inventory &amp; planning workspace"' in r.text
            for url in ('/vials?status=in_use', '/vials?status=sealed', '/purchases', '/blends', '/protocols'):
                assert f'href="{url}"' in r.text, (path, url)
        for path in ("/progress?days=180", "/vitals?days=180", "/health-insights?days=180",
                     "/health-timeline?days=180", "/labs?days=180", "/reports/trends?days=180"):
            r = client.get(path)
            assert r.status_code == 200, path
            assert 'aria-label="Health workspace"' in r.text
            for url in ('/progress?days=180', '/vitals?days=180', '/health-timeline?days=180', '/health-insights?days=180'):
                assert f'href="{url}"' in r.text, (path, url)
        today = client.get("/mobile")
        assert today.status_code == 200
        assert 'tracker-workspaces792.js' not in today.text
        assert 'tracker-dashboard-customize-enhancements.js' not in today.text
        assert 'workflow_hub.css?v=105112' not in today.text
        dashboard = client.get("/")
        assert 'tracker-dashboard-customize-enhancements.js' in dashboard.text
        hub = client.get("/workflow-hub")
        assert 'workflow_hub.css?v=105112' in hub.text


@pytest.mark.parametrize("width", [320, 390, 1280])
def test_792_rendered_workspace_grids_and_native_form_disclosures(width):
    with TestClient(app) as client:
        pages = [(url, *rendered(client, url)) for url in ("/food", "/purchases", "/blends", "/protocols", "/progress?days=180")]
    js = (STATIC / "js/tracker-workspaces792.js").read_text()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None)
        try:
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.route("**/*", lambda route: route.abort())
            for url, markup, css in pages:
                page.set_content(markup)
                page.add_style_tag(content=css)
                page.evaluate("document.documentElement.dataset.density = 'compact'")
                page.add_script_tag(content=js)
                nav = page.locator("nav.tracker-workspace-tabs792").first
                expect(nav).to_be_visible()
                stats = nav.evaluate("""el => {
                    const b=el.getBoundingClientRect();
                    const a=[...el.querySelectorAll(':scope > a')].map(x=>x.getBoundingClientRect());
                    return {display:getComputedStyle(el).display, first:a.filter(x=>Math.abs(x.y-a[0].y)<2).length,
                        fits:a.every(x=>x.width>0 && x.right<=b.right+1), min:Math.min(...a.map(x=>x.height))};
                }""")
                assert stats["display"] == "grid" and stats["first"] >= 2 and stats["fits"], (url,width,stats)
                assert stats["min"] >= (44 if width <= 760 else 36), (url,width,stats)
                if url == "/food":
                    expect(page.locator("#food-recorded")).to_have_attribute("open", "")
                    expect(page.locator("#food-entry-form")).to_be_hidden()
                    nav.locator('a[href="#food-quick-log"]').click()
                    expect(page.locator("#food-add-workspace792")).to_have_attribute("open", "")
                    page.locator('nav[aria-label="Choose food entry method"] a[href="#food-add"]').click()
                    expect(page.locator("#food-entry-form")).to_be_visible()
                    expect(page.locator("#food-entry-form button[type=submit]")).to_be_visible()
                elif url == "/purchases":
                    expect(page.locator("#purchase-history-table")).to_be_visible()
                    expect(page.locator('form[action="/purchases"]')).to_be_hidden()
                    page.locator('nav[aria-label="Purchase actions"] a[href="#new-purchase"]').click()
                    expect(page.locator('form[action="/purchases"]')).to_be_visible()
                elif url == "/blends":
                    expect(page.locator("#recorded-blends792")).to_be_visible()
                    expect(page.locator("#blend-form")).to_be_hidden()
                    page.locator('nav[aria-label="Blend actions"] a[href="#create-blend792"]').click()
                    expect(page.locator("#blend-form")).to_be_visible()
                    expect(page.locator("#record-blend")).to_be_disabled()
                elif url == "/protocols":
                    expect(page.locator('form[action="/protocols"]')).to_be_hidden()
                    page.locator('nav[aria-label="Protocol workflow"] a[href="#new-protocol"]').click()
                    expect(page.locator('form[action="/protocols"]')).to_be_visible()
        finally:
            browser.close()
