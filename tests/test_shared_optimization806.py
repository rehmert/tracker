"""Release 806: shared frontend lifecycle regressions on offline Chromium."""
from pathlib import Path
import os
import pytest
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]

def load(page, name):
    page.add_script_tag(content=(ROOT/"app/static"/name).read_text())

@pytest.mark.parametrize("width", [320,390,430,768,1024,1440,1920])
def test_duplicate_submit_guard_and_cancel_retry(width):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None)
        try:
            page = browser.new_page(viewport={"width":width,"height":800})
            page.route("**/*",lambda route: route.abort())
            page.set_content("""<main id="main-content"><form method="post" id="f">
                <label>Value<input name="value" required value="1"></label>
                <button type="submit" name="save" value="yes">Save</button></form>
                <form method="post" id="fallback" data-no-dirty-warning>
                <button type="submit">Save</button></form>
                <form method="post" id="hx" hx-put="/example"><button type="submit">Save</button></form></main>""")
            load(page,"release36_40.js")
            load(page,"js/tracker-ux-3447-3452.js")
            page.evaluate("""() => {
                window.fireSubmit = id => { const f=document.getElementById(id);
                    return f.dispatchEvent(new SubmitEvent('submit',{bubbles:true,cancelable:true,submitter:f.querySelector('button')})); };
                window.cancelSubmit = e => { if(e.target.id==='f') e.preventDefault(); };
                document.addEventListener('submit', window.cancelSubmit);
            }""")
            page.locator("#f input").fill("2")
            assert page.evaluate("fireSubmit('f')") is False
            expect(page.locator("#f .ux-form-status")).to_have_count(0)
            expect(page.locator("#f")).to_have_class("tracker-form-dirty")
            page.evaluate("document.removeEventListener('submit',window.cancelSubmit)")
            assert page.evaluate("fireSubmit('f')") is True
            expect(page.locator("#f .ux-form-status")).to_have_count(1)
            assert page.evaluate("fireSubmit('f')") is False
            expect(page.locator("#f .ux-form-status")).to_have_count(1)
            page.evaluate("window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}))")
            expect(page.locator("#f .ux-form-status")).to_have_count(0)
            assert page.evaluate("fireSubmit('f')") is True
            assert page.evaluate("fireSubmit('fallback')") is True
            assert page.evaluate("fireSubmit('fallback')") is False
            assert page.evaluate("fireSubmit('hx')") is True
            assert page.evaluate("fireSubmit('hx')") is True
            expect(page.locator("#hx .ux-form-status")).to_have_count(0)
        finally:
            browser.close()

def test_inventory_table_gets_one_filter_and_keeps_generic_fallback():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None)
        try:
            page=browser.new_page()
            page.route("**/*",lambda route: route.fulfill(status=200,content_type="text/html",body="<html></html>"))
            page.goto("http://tracker.test/inventory-health")
            rows="".join(f"<tr><td>Row {i}</td></tr>" for i in range(6))
            page.set_content(f'<main id="main-content"><h1>Inventory</h1><div data-enhanced-table><table><thead><tr><th>Finding</th></tr></thead><tbody>{rows}</tbody></table></div><div class="scroll"><table><tbody>{rows}</tbody></table></div></main>')
            page.add_style_tag(content=(ROOT/"app/static/release36_40.css").read_text())
            load(page,"release36_40.js")
            load(page,"core_workflow_97_104.js")
            expect(page.locator(".ux-table-tools")).to_have_count(1)
            expect(page.locator(".core-table-toolbar")).to_have_count(1)
            page.locator(".ux-table-tools input").fill("Row 1")
            expect(page.locator("[data-enhanced-table] tbody tr:visible")).to_have_count(1)
            expect(page.locator(".scroll tbody tr:visible")).to_have_count(6)
            expect(page.locator("[data-enhanced-table] tbody tr:visible")).to_have_text("Row 1")
            page.locator(".ux-table-tools input").fill("")
            expect(page.locator("[data-enhanced-table] tbody tr:visible")).to_have_count(6)
            page.locator(".core-table-toolbar input").fill("Row 2")
            expect(page.locator(".scroll tbody tr:visible")).to_have_count(1)
            expect(page.locator(".scroll tbody tr:visible")).to_have_text("Row 2")
            expect(page.locator("[data-enhanced-table] tbody tr:visible")).to_have_count(6)
        finally:
            browser.close()
