"""Release 692: remove the Workout camera QR scanner, not workout tracking.

Runs against the existing pytest-managed disposable application database.
No live data, schema migration, hardware camera, or external QR destination.
"""
import os
from pathlib import Path
from uuid import uuid4

import pytest
from playwright.sync_api import expect, sync_playwright
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from app.db import SessionLocal, engine
from app.main import app
from app.workout_models654 import WorkoutEquipment654, WorkoutSet654

ROOT = Path(__file__).resolve().parents[1]


def test_692_workout_page_has_no_camera_ui_or_scanner_script():
    with TestClient(app) as client:
        page = client.get("/workouts")
        assert page.status_code == 200
        html = page.text
        assert "Find a machine" not in html
        assert 'name="code"' not in html
        assert 'action="/workouts/qr"' not in html
        assert "Setup &amp; QR" not in html
        assert 'name="qr_value"' not in html
        assert "Equipment &amp; Logging" in html
        assert "Add Equipment" in html
        assert "Progress" in html
        assert "Gym Mode" in html
        for forbidden in (
            "Scan QR with Camera", "Stop Camera", "Live camera view",
            "workout-qr-camera656", "data-start656", "data-stop656",
            "data-preview656", "data-status656",
            "tracker-workouts656.js", "unmapped_qr",
        ):
            assert forbidden not in html, forbidden


def test_692_camera_backend_and_script_are_gone_manual_lookup_kept():
    with TestClient(app) as client:
        for value in ("", "TEST-OLD-CAMERA", "https://example.invalid/workout"):
            response = client.get("/workouts/qr/scan", params={"code": value})
            assert response.status_code == 404
        assert client.get("/static/js/tracker-workouts656.js").status_code == 404
        assert client.get("/workouts/qr", params={"code": "unknown-code"},
                          follow_redirects=False).status_code == 404
        assert client.get("/workouts").status_code == 200
    assert not (ROOT / "app/static/js/tracker-workouts656.js").exists()
    assert not (ROOT / "scripts/tracker-workout-camera-test656.cjs").exists()
    source = (ROOT / "app/routers/workouts656.py").read_text()
    assert '@router.get("/workouts/qr/scan")' not in source
    assert '@router.get("/workouts/equipment/{equipment_id}/progress")' in source
    css = (ROOT / "app/static/css/tracker-workouts656.css").read_text()
    assert ".workout656-camera" not in css
    assert ".workout656-preview" not in css
    assert ".workout656-progress" in css


def test_692_manual_machine_selection_settings_sets_and_progress_still_work():
    suffix = uuid4().hex[:12]
    name = "QA692 Manual Nautilus " + suffix
    code = "https://example.invalid/692/" + suffix
    with TestClient(app) as client:
        created = client.post("/workouts/equipment", data={
            "name": name, "kind": "selectorized", "gym": "Merritt Eldersburg",
            "qr_value": code, "manufacturer": "Nautilus",
        }, follow_redirects=False)
        assert created.status_code == 303
        with SessionLocal() as db:
            equipment_id = db.scalar(select(WorkoutEquipment654.id).where(
                WorkoutEquipment654.name == name
            ))
            assert equipment_id is not None
            assert db.get(WorkoutEquipment654, equipment_id).qr_value is None
        page = client.get("/workouts")
        assert name in page.text
        assert f'id="workout-machine-{equipment_id}"' in page.text
        assert 'type="submit">Find Machine</button>' not in page.text
        assert client.get(f"/workouts?machine={equipment_id}").status_code == 200
        assert client.get(f"/workouts/equipment/{equipment_id}/progress").status_code == 200
        assert client.post("/workouts/start", follow_redirects=False).status_code == 303
        logged = client.post("/workouts/sets", data={
            "equipment_id": equipment_id, "weight_lb": "90", "reps": "12",
        }, follow_redirects=False)
        assert logged.status_code == 303
        with SessionLocal() as db:
            logged_sets = list(db.scalars(select(WorkoutSet654).where(
                WorkoutSet654.equipment_id == equipment_id
            )))
            assert len(logged_sets) == 1
            assert logged_sets[0].weight_lb == 90
        assert client.post("/workouts/finish", follow_redirects=False).status_code == 303
        progress = client.get(f"/workouts/equipment/{equipment_id}/progress")
        assert progress.status_code == 200
        assert name in progress.text


def test_692_database_model_and_upload_storage_unchanged():
    # The release removes camera UI/routing only, never any equipment mapping,
    # workout session, set, or performance-history tables.
    assert {
        "workout_equipment654", "workout_sessions654", "workout_sets654"
    } <= set(inspect(engine).get_table_names())
    source = (ROOT / "app/routers/workouts656.py").read_text()
    assert "db.commit(" not in source
    assert "db.add(" not in source
    assert "db.delete(" not in source


@pytest.mark.parametrize("width", [375, 1280])
def test_692_real_browser_workout_navigation_and_manual_equipment_lookup(width):
    with TestClient(app) as client:
        html = client.get("/workouts").text
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": width, "height": 812})
            page.set_content(html)
            expect(page.get_by_role("heading", name="Workouts", exact=True)).to_be_visible()
            expect(page.get_by_role("heading", name="Find a machine")).to_have_count(0)
            expect(page.get_by_role("button", name="Find Machine")).to_have_count(0)
            expect(page.get_by_role("link", name="Gym Mode")).to_be_visible()
            expect(page.get_by_role("link", name="Progress", exact=True)).to_be_visible()
            expect(page.get_by_role("heading", name="Equipment & Logging")).to_be_visible()
            assert page.get_by_role("button", name="Scan QR with Camera").count() == 0
            assert page.locator("video").count() == 0
            assert page.locator('script[src*="tracker-workouts656.js"]').count() == 0
            assert page.locator('[data-start656], [data-stop656], [data-preview656]').count() == 0
            assert page.locator('form[action="/workouts/qr"] input[name="code"]').count() == 0
            assert page.locator('input[name="qr_value"]').count() == 0
        finally:
            browser.close()
