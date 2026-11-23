"""Release 763 real Chromium coverage for unit selector round-trip semantics."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.food_read_engine406 import get_food_read_engine406
from app.main import app

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.browser
@pytest.mark.parametrize("width", [360, 430])
def test_763_progress_units_convert_values_and_labels(width):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
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
        css = (ROOT/"app/static/css/tracker-progress762.css").read_text()
        js = (ROOT/"app/static/js/tracker-progress763.js").read_text()
        source = source.replace("</head>", "<style>" + css + "</style><script>" +
                                js + "</script></head>")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": width, "height": 844},
                                          has_touch=True, is_mobile=True)
            page = context.new_page()
            page.route("**/*", lambda route: route.fulfill(
                status=200, content_type="text/html", body=source)
                if route.request.resource_type == "document" else route.abort())
            page.goto("https://tracker.test/progress")
            measure = page.locator("#measure")
            measure.locator("summary").click()
            waist = measure.locator('input[name="waist_navel"]')
            waist.fill("40")
            measure.locator('select[name="unit"]').select_option("cm")
            assert float(waist.input_value()) == pytest.approx(101.6)
            assert "(cm)" in measure.locator("[data-tape-unit-label]").first.inner_text()
            measure.locator('select[name="unit"]').select_option("in")
            assert float(waist.input_value()) == pytest.approx(40, abs=.0001)

            composition = page.locator("#composition")
            composition.locator("summary").click()
            lean = composition.locator('input[name="fat_free_mass_kg"]')
            lean.fill("170")
            composition.locator('select[name="mass_unit"]').select_option("kg")
            assert float(lean.input_value()) == pytest.approx(77.1107, abs=.0001)
            assert "(kg)" in composition.locator("[data-mass-unit-label]").first.inner_text()
            composition.locator('select[name="mass_unit"]').select_option("lb")
            assert float(lean.input_value()) == pytest.approx(170, abs=.0002)

            settings = page.locator("#progress-settings")
            settings.locator("summary").click()
            height = settings.locator('input[name="height"]')
            height.fill("71")
            settings.locator('select[name="height_unit"]').select_option("cm")
            assert float(height.input_value()) == pytest.approx(180.34)
            goal = settings.locator('input[name="goal_weight"]')
            goal.fill("215")
            settings.locator('select[name="weight_unit"]').select_option("kg")
            assert float(goal.input_value()) == pytest.approx(97.522, abs=.001)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
            browser.close()
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_food_read_engine406, None)
        engine.dispose()
