"""Real 807 application assets with isolated, offline browser routing."""
from pathlib import Path
import json
import pytest
from playwright.sync_api import sync_playwright
from app.anatomical_sites807 import SITES, site_geometry

ROOT=Path(__file__).resolve().parents[2]
STATIC=ROOT/"app/static"

@pytest.mark.browser
@pytest.mark.parametrize("width",[320,390,430,768,1024,1440,1920])
def test_picker807_real_assets_and_selection(width):
    from html import escape
    options="".join('<option value="'+s.code+'" data-site807="'+escape(json.dumps(
        {"region":s.region,"views":s.views,"geometry":site_geometry(s.code)}),quote=True)+'">'+escape(s.label)+'</option>' for s in SITES)
    html='<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/css/tracker-anatomy807.css"><script defer src="/static/js/tracker-anatomy807.js"></script></head><body><form><label>Location<select name="site"><option value="">Not recorded</option>'+options+'</select></label></form></body></html>'
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={"width":width,"height":850},has_touch=width<=430)
        errors=[]
        page.on("pageerror",lambda error:errors.append(str(error)))
        def route(r):
            from urllib.parse import urlsplit
            path=urlsplit(r.request.url).path
            if path=="/": r.fulfill(status=200,content_type="text/html",body=html)
            elif path.startswith("/static/"):
                file=STATIC/path.removeprefix("/static/")
                assert file.resolve().is_relative_to(STATIC.resolve())
                r.fulfill(status=200,content_type={".css":"text/css",".js":"text/javascript",".svg":"image/svg+xml"}[file.suffix],body=file.read_bytes())
            elif path=="/wellness807/site-summary":
                r.fulfill(status=200,content_type="application/json",body='{"sites":{},"configured":false}')
            else: r.abort()
        page.route("**/*",route)
        page.goto("https://tracker.test/")
        page.locator(".site807-picker summary").first.click()
        zone=page.locator('[data-code="abdomen_left"]')
        zone.focus(); zone.press("Enter")
        assert page.locator('select[name="site"]').input_value()=="abdomen_left"
        assert zone.get_attribute("aria-pressed")=="true"
        page.get_by_role("button",name="Left",exact=True).click()
        assert page.locator('[data-code="abdomen_left"]').get_attribute("aria-pressed")=="true"
        page.get_by_role("button",name="Selected region reference").click()
        assert page.locator(".site807-reference").evaluate("(el)=>el.open")
        page.get_by_role("button",name="Rear",exact=True).click()
        page.locator('[data-code="glute_left_upper_outer"]').click()
        assert page.locator('select[name="site"]').input_value()=="glute_left_upper_outer"
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
        assert not errors
        browser.close()
