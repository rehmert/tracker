"""Release 753: COA row density and simplified vial listing, no write changes."""
from pathlib import Path
from jinja2 import Environment
from fastapi.testclient import TestClient
from app.main import app

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "app/templates"
CSS = ROOT / "app/static/css/tracker-coa-list-density753.css"


def test_753_coa_actions_remain_single_row_and_preserve_three_destinations():
    text = (TPL / "coas.html").read_text()
    Environment().parse(text)
    assert "tracker-coa-list-density753.css?v=753" in text
    row = text.split('<tr data-flow696-coa-row>', 1)[1].split('</tr>', 1)[0]
    actions = row.split('data-label="Actions"', 1)[1].split("</td>", 1)[0]
    assert actions.count("<nav ") == 1
    assert actions.count("<a ") == 3
    for path in ("/coas/{{ c.id }}", "/coas/{{ c.id }}#test-documents",
                 "/coas/{{ c.id }}#coa-links741"):
        assert f'href="{path}"' in actions
    assert "tracker-macd741-action" not in actions
    assert "Documents for COA #{{ c.id }}" in actions
    assert "Linked vials for COA #{{ c.id }}" in actions


def test_753_vial_row_is_single_detail_link_and_edit_still_exists():
    listing = (TPL / "vials.html").read_text()
    detail = (TPL / "vial_detail.html").read_text()
    Environment().parse(listing)
    Environment().parse(detail)
    assert '<a href="/vials/{{ v.id }}">#{{ v.id }}' in listing
    assert 'href="/vials/{{ v.id }}#vial-details741"' not in listing
    assert '<a class="tracker-macd741-action" href="#vial-details741">Edit vial</a>' in detail
    assert 'id="vial-details741"' in detail
    assert 'id="tracker-vials-sortable"' in listing
    assert "bulk-vial-check" in listing


def test_753_css_is_compact_focus_visible_and_mobile_touch_friendly():
    css = CSS.read_text()
    assert css.count("{") == css.count("}")
    assert "display: inline-flex" in css
    assert "flex-wrap: nowrap" in css
    assert "white-space: nowrap" in css
    assert "min-height: 34px" in css
    assert "min-height: 44px" in css
    assert ":focus-visible" in css


def test_753_real_list_pages_still_get_200():
    with TestClient(app, follow_redirects=False) as client:
        for url, marker in (
            ("/coas", 'id="tracker-flow696-coa-table"'),
            ("/vials", 'id="tracker-vials-sortable"'),
        ):
            result = client.get(url)
            assert result.status_code == 200, (url, result.status_code)
            assert marker in result.text


def test_753_chromium_links_stay_one_line_on_mobile_and_desktop():
    from playwright.sync_api import sync_playwright

    css = CSS.read_text()
    html = """<html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head>
    <body><table id="tracker-flow696-coa-table"><tbody><tr>
    <td data-label="Actions"><nav class="tracker-coa753-actions">
    <a href="/coas/1">Edit</a><a href="/coas/1#test-documents">Docs</a>
    <a href="/coas/1#coa-links741">Vials</a></nav></td>
    </tr></tbody></table></body></html>"""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            for width in (320, 390, 768):
                page = browser.new_page(viewport={"width": width, "height": 700})
                page.set_content(html)
                page.add_style_tag(content=css)
                links = page.locator("nav.tracker-coa753-actions a")
                assert links.count() == 3
                bounds = [a.bounding_box() for a in links.all()]
                assert all(box is not None for box in bounds)
                assert max(b["y"] for b in bounds) - min(b["y"] for b in bounds) < 1
                assert max(b["x"] + b["width"] for b in bounds) <= width
                assert all(b["height"] >= (44 if width <= 600 else 34) for b in bounds)
                for link in links.all():
                    link.focus()
                    assert link.evaluate("(el) => document.activeElement === el")
                page.close()
        finally:
            browser.close()
