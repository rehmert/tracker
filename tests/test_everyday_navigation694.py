"""Release 694: focused real-template and Chromium everyday navigation regression."""
from pathlib import Path
import re
import os

from fastapi.testclient import TestClient
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import expect, sync_playwright

from app.main import app

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app/templates"
FOCUS_JS = (ROOT / "app/static/tracker_focus.js").read_text(encoding="utf-8")
FOCUS_CSS = (ROOT / "app/static/tracker_focus.css").read_text(encoding="utf-8")

PRIMARY = [
    ("/mobile", "Today"),
    ("/doses#quick-dose-entry", "Log Dose"),
    ("/food#food-quick-log", "Log Food"),
    ("/mobile#mobile-quick-vitals", "Log Vitals"),
    ("/workouts/quick", "Workout"),
    ("/vials", "Inventory"),
    ("/quick-entry", "More Actions"),
]


def _rendered_shortcuts():
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    template = env.from_string(
        '{% from "_daily_actions694.html" import daily_actions694 %}'
        '<nav>{{ daily_actions694() }}</nav>'
    )
    return template.render()


def test_694_shared_daily_action_destinations_and_safe_secondary_links():
    with TestClient(app) as client:
        overview = client.get("/")
        today = client.get("/mobile")
        assert overview.status_code == today.status_code == 200
    for source in (overview.text, today.text):
        assert 'href="/static/css/tracker-daily-shortcuts694.css?v=694"' in source
        for href, label in PRIMARY:
            assert f'href="{href}"' in source
            assert f"<strong>{label}</strong>" in source
        assert "tracker-daily-extra694" in source
    for href in ("/food#food-water", "/regimen#reg635-today"):
        assert f'href="{href}"' in today.text
    for href in (
        "/calendar", "/dose-workspace", "/replenishment-review",
        "/labs", "/health-insights", "/food#food-water",
    ):
        assert f'href="{href}"' in overview.text
    assert overview.text.count('class="tracker-daily-flow559-links"') == 1
    assert today.text.count('class="tracker-daily-actions"') == 1

    from html.parser import HTMLParser

    class Extract(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []
            self.href = None
            self.label = ""
        def handle_starttag(self, tag, attrs):
            if tag == "a":
                self.href = dict(attrs).get("href")
                self.label = ""
        def handle_data(self, data):
            if self.href is not None:
                self.label += data
        def handle_endtag(self, tag):
            if tag == "a" and self.href is not None:
                self.links.append((self.href, self.label.strip()))
                self.href = None

    parser = Extract()
    parser.feed(_rendered_shortcuts())
    assert parser.links == PRIMARY


def _fixture():
    with TestClient(app) as client:
        rendered = client.get("/").text
    start = rendered.index('<nav class="rail" id="app-sidebar"')
    end = rendered.index("</nav>", start) + len("</nav>")
    nav = rendered[start:end]
    assert nav.count('class="nav-section"') == 7
    return (
        '<!doctype html><html><head><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<style>*{box-sizing:border-box}body{margin:0}'
        '#app-sidebar{width:min(280px,100vw);padding:8px}'
        '.nav-links{list-style:none;margin:0;padding:0}'
        '.nav-links li{margin:2px 0}'
        '</style></head><body>' + nav +
        '<label>Show everyday pages only'
        '<input type="checkbox" id="tracker-focus-toggle"></label>'
        '</body></html>'
    )


def test_694_sidebar_render_contract_and_full_navigation_retained():
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    assert 'id="tracker-focus-sidebar-toggle"' in base
    assert 'aria-controls="nav-sortable"' in base
    assert '/static/tracker_focus.js?v=694' in base
    assert '/static/tracker_focus.css?v=694' in base
    assert "Show everyday pages only" in base
    assert "active.has(href)" in FOCUS_JS
    assert "localStorage.getItem(KEY)" in FOCUS_JS
    assert "saved !== null" in FOCUS_JS
    assert "localStorage.setItem(KEY" in FOCUS_JS
    assert "document.getElementById('tracker-focus-sidebar-toggle')" in FOCUS_JS
    assert "fetch(" not in FOCUS_JS
    assert "remove(" not in FOCUS_JS
    assert "innerHTML" not in FOCUS_JS


def test_694_everyday_default_all_pages_toggle_and_persisted_choice():
    fixture = _fixture()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            for width in (320, 390, 768, 1280):
                context = browser.new_context(
                    viewport={"width": width, "height": 850},
                )
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda err: errors.append(str(err)))
                page.route("https://tracker-694.test/", lambda route: route.fulfill(
                    status=200, content_type="text/html", body=fixture
                ))
                page.goto("https://tracker-694.test/")
                page.add_style_tag(content=FOCUS_CSS)
                page.add_script_tag(content=FOCUS_JS)
                button = page.locator("#tracker-focus-sidebar-toggle")
                checkbox = page.locator("#tracker-focus-toggle")
                work = page.locator('[data-nav-key="/workouts"]')
                today = page.locator('[data-nav-key="/mobile"]')
                advanced = page.locator('[data-nav-key="/sqlite-viewer"]')
                expect(button).to_have_text("Show all pages")
                expect(button).to_have_attribute("aria-expanded", "false")
                expect(checkbox).to_be_checked()
                assert not work.evaluate(
                    "e => e.classList.contains('tracker-focus-hidden')"
                )
                assert not today.evaluate(
                    "e => e.classList.contains('tracker-focus-hidden')"
                )
                assert advanced.evaluate(
                    "e => e.classList.contains('tracker-focus-hidden')"
                )
                assert page.locator("#nav-sortable [data-nav-key]").count() == 54
                assert button.bounding_box()["height"] >= 44
                assert page.evaluate(
                    "() => document.documentElement.scrollWidth <= innerWidth + 1"
                ), width

                button.click()
                expect(button).to_have_text("Show everyday pages")
                expect(button).to_have_attribute("aria-expanded", "true")
                expect(checkbox).not_to_be_checked()
                assert not advanced.evaluate(
                    "e => e.classList.contains('tracker-focus-hidden')"
                )
                assert page.evaluate(
                    "() => localStorage.getItem('tracker.navigation.focus.v1')"
                ) == "false"
                # An existing user's explicit All Pages preference must persist.
                page.reload()
                page.add_style_tag(content=FOCUS_CSS)
                page.add_script_tag(content=FOCUS_JS)
                expect(page.locator("#tracker-focus-sidebar-toggle")).to_have_text(
                    "Show everyday pages"
                )
                checkbox = page.locator("#tracker-focus-toggle")
                checkbox.check()
                expect(button).to_have_text("Show all pages")
                assert page.evaluate(
                    "() => localStorage.getItem('tracker.navigation.focus.v1')"
                ) == "true"
                assert not errors, (width, errors)
                context.close()
        finally:
            browser.close()
