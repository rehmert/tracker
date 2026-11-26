"""Rendered density/geometry regression for daily shortcut grids and Calendar."""
import os

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright, expect

from app.main import app
from tests.test_calendar_action_buttons787 import rendered


@pytest.mark.parametrize("width,density", [
    (320, "compact"), (390, "balanced"), (430, "compact"),
    (1280, "balanced"), (1920, "compact"),
])
def test_791_daily_actions_use_available_width_and_calendar_note_expands(width, density):
    with TestClient(app) as client:
        pages = [(url, *rendered(client, url)) for url in ("/", "/mobile", "/calendar")]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None)
        try:
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.route("**/*", lambda route: route.abort())
            for url, markup, css in pages:
                page.set_content(markup)
                page.add_style_tag(content=css)
                page.evaluate("(density) => document.documentElement.dataset.density = density", density)
                if url != "/calendar":
                    quick = page.locator("nav.tracker-quick-actions790")
                    expect(quick.locator(":scope > a")).to_have_count(6)
                    review = page.locator("nav.tracker-review-actions791")
                    review.evaluate("el => el.closest('details').open = true")
                    for grid in (quick, review):
                        metrics = grid.evaluate("""el => {
                            const bounds = el.getBoundingClientRect();
                            const children = [...el.querySelectorAll(':scope > a')].map(a => {
                                const r = a.getBoundingClientRect();
                                return {x:r.x, y:r.y, w:r.width, h:r.height, right:r.right};
                            });
                            return {
                                display:getComputedStyle(el).display,
                                rows:new Set(children.map(r => Math.round(r.y))).size,
                                first:children.filter(r => Math.abs(r.y-children[0].y)<2).length,
                                within:children.every(r => r.x>=bounds.x-1 && r.right<=bounds.right+1 && r.w>0),
                                minHeight:Math.min(...children.map(r => r.h)),
                            };
                        }""")
                        assert metrics["display"] == "grid", (url, width, metrics)
                        assert metrics["first"] >= (2 if width <= 760 else 4), (url, width, metrics)
                        assert metrics["rows"] <= (3 if width <= 760 else 2), (url, width, metrics)
                        assert metrics["within"], (url, width, metrics)
                        assert metrics["minHeight"] >= (44 if width <= 760 else 36)
                else:
                    note = page.locator("#calendar-explanation791")
                    preview = note.locator(".calendar-explanation791-preview")
                    more = note.get_by_text("More…", exact=True)
                    less = note.get_by_text("Less", exact=True)
                    expect(more).to_be_visible()
                    expect(note.locator(":scope > p")).to_be_hidden()
                    metrics = preview.evaluate("""el => ({
                        height:el.clientHeight, line:parseFloat(getComputedStyle(el).lineHeight),
                        whiteSpace:getComputedStyle(el).whiteSpace,
                        ellipsis:getComputedStyle(el).textOverflow
                    })""")
                    assert metrics["height"] <= metrics["line"] + 1, (width, metrics)
                    assert metrics["whiteSpace"] == "nowrap" and metrics["ellipsis"] == "ellipsis"
                    more.click()
                    expect(less).to_be_visible()
                    expect(note.locator(":scope > p")).to_be_visible()
                    assert preview.evaluate("el => getComputedStyle(el).whiteSpace") == "normal"
                    assert "Calendar events never create dose logs" in preview.inner_text()
                    assert "Previewing does not record an administration" in note.locator(":scope > p").inner_text()
                    less.click()
                    expect(more).to_be_visible()
                    expect(note.locator(":scope > p")).to_be_hidden()
        finally:
            browser.close()
