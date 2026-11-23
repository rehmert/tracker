"""Release 762 Chromium phone smoke using an isolated synthetic application DB.

The browser sees an offline document snapshot: no live Tracker HTTP listener,
no user data and no external requests. Tests real responsive CSS and controls.
"""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from playwright.sync_api import sync_playwright

from app.db import Base, get_db
from app.main import app
from app.food_read_engine406 import get_food_read_engine406

ROOT = Path(__file__).resolve().parents[2]
CSS = (ROOT/"app/static/css/tracker-progress762.css").read_text()

@pytest.mark.browser
@pytest.mark.parametrize("width", [360, 390, 430])
def test_762_mobile_progress_toggles_no_overflow(width):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    def scoped():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = scoped
    app.dependency_overrides[get_food_read_engine406] = lambda: engine
    try:
        with TestClient(app) as client:
            source = client.get("/progress").text
            assert "Progress Dashboard" in source
        # Flatten the actual stylesheet into a single offline page.
        source = source.replace('</head>', '<style>' + CSS + '</style></head>')
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": width, "height": 844}, has_touch=True,
                is_mobile=True, device_scale_factor=2)
            page = context.new_page()
            page.route("**/*", lambda route: route.fulfill(
                status=200, content_type="text/html", body=source)
                if route.request.resource_type == "document" else route.abort())
            page.goto("https://tracker.test/progress")
            assert page.get_by_role("heading", name="Progress Dashboard").is_visible()
            section = page.locator('#measure')
            section.locator('summary').click()
            assert section.locator('input[name="waist_navel"]').is_visible()
            assert section.locator('input[name="measured_on"]').is_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2"), width
            section.locator('summary').click()
            assert not section.locator('input[name="waist_navel"]').is_visible()
            browser.close()
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_food_read_engine406, None)
        engine.dispose()
