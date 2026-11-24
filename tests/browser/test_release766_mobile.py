"""Release 766 offline touch browser layout: compact inventory and report cards."""
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.browser
@pytest.mark.parametrize("width", [360, 430])
def test_766_compact_cards_and_report_are_touch_usable(width):
    vial_css = (ROOT/"app/static/css/tracker-vial-mobile-cards766.css").read_text()
    trend_css = (ROOT/"app/static/css/tracker-trends766.css").read_text()
    html = f"""<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">
    <style>*{{box-sizing:border-box}} body{{margin:0;padding:8px}}
    {vial_css}\n{trend_css}</style>
    <section class="vial766-mobile-cards" id="vial766-mobile-cards">
      <details class="vial766-card">
        <summary><span><strong>BPC-157</strong><small>#1 · in use</small></span>
        <span class="vial766-amount">36,349.664 mg</span></summary>
        <div class="vial766-card-body"><p>COA Missing</p><a href="/vials/1">Open Vial #1</a></div>
      </details>
      <button id="vial766-full-toggle">Show Full Table</button>
    </section>
    <div id="vial766-full-table">Example full table</div>
    <section class="trends766-page">
    <div class="trends766-scroll"><table class="trends766-table">
    <thead><tr><th>Week</th><th>Weight</th><th>Steps</th></tr></thead>
    <tbody><tr><th>2026-11-23</th><td data-label="Weight">265.2 <small>3d</small></td>
    <td data-label="Steps">7520 <small>5d</small></td></tr></tbody>
    </table></div></section>"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width":width,"height":830},
                                device_scale_factor=2, is_mobile=True, has_touch=True)
        page.set_content(html)
        assert page.locator(".vial766-mobile-cards").is_visible()
        assert page.locator(".vial766-card summary").is_visible()
        page.locator(".vial766-card summary").click()
        assert page.get_by_text("COA Missing").is_visible()
        assert page.locator(".trends766-table tbody tr").count() == 1
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+2"), width
        browser.close()
