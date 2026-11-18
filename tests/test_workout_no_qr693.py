"""Release 693: remove obsolete Workout QR controls without losing equipment data."""
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.routers.data_quality674 import quality_summary674
from app.workout_models654 import WorkoutEquipment654

ROOT = Path(__file__).resolve().parents[1]


def test_693_main_workout_ui_is_equipment_first_and_qr_free():
    with TestClient(app) as client:
        created = client.post("/workouts/equipment", data={
            "name": "QA693 UI Fixture " + uuid4().hex[:9],
            "kind": "selectorized", "gym": "Merritt Eldersburg",
        }, follow_redirects=False)
        assert created.status_code == 303
        response = client.get("/workouts")
        assert response.status_code == 200
        html = response.text
        for missing in (
            "Find a machine", "QR text or URL", "Find Machine",
            "Paste a Nautilus QR code", "Map QR codes once",
            "Setup &amp; QR", "QR code value", "QR code URL/text",
            'action="/workouts/qr"', 'name="qr_value"',
            "Scan QR with Camera",
        ):
            assert missing not in html
        for present in (
            "Equipment &amp; Logging", "Add Equipment", "Saved Routines",
            "Machine Setup", "Seat / backrest position", "Save Settings",
            "Gym Mode", "Progress", "Log completed sets only",
        ):
            assert present in html


def test_693_qr_lookup_endpoints_retired_but_gym_name_finder_remains():
    with TestClient(app) as client:
        for path in ("/workouts/qr", "/workouts/qr/scan"):
            assert client.get(path, params={"code": "old-code"}).status_code == 404
        quick = client.get("/workouts/quick")
        assert quick.status_code == 200
        assert "Find Machine" in quick.text
        assert 'id="workout662-search"' in quick.text
        assert 'id="workout659-machine-select"' in quick.text
    source = (ROOT / "app/routers/workouts654.py").read_text(encoding="utf-8")
    assert '@router.get("/workouts/qr")' not in source
    assert "qr_value: str = Form" not in source


def test_693_historical_qr_values_preserved_and_new_submissions_ignore_them():
    name = "QA693 Existing " + uuid4().hex[:9]
    prior_value = "https://example.invalid/historic/" + uuid4().hex
    with TestClient(app) as client:
        with SessionLocal() as db:
            old = WorkoutEquipment654(name=name, gym="Merritt Eldersburg",
                                      kind="selectorized", qr_value=prior_value)
            db.add(old)
            db.commit()
            old_id = old.id

        settings = client.post(
            f"/workouts/equipment/{old_id}/settings",
            data={
                "seat_setting": "5", "setup_notes": "Backrest 2",
                "qr_value": "FORGED-FORM-SHOULD-BE-IGNORED",
            },
            follow_redirects=False,
        )
        assert settings.status_code == 303
        with SessionLocal() as db:
            prior = db.get(WorkoutEquipment654, old_id)
            assert prior.qr_value == prior_value
            assert prior.seat_setting == "5"
            assert prior.setup_notes == "Backrest 2"

        new_name = "QA693 New " + uuid4().hex[:9]
        created = client.post(
            "/workouts/equipment",
            data={"name": new_name, "kind": "free_weight",
                  "gym": "Home", "qr_value": prior_value},
            follow_redirects=False,
        )
        assert created.status_code == 303
        with SessionLocal() as db:
            new = db.scalar(select(WorkoutEquipment654).where(
                WorkoutEquipment654.name == new_name
            ))
            assert new is not None and new.qr_value is None
        assert client.get(f"/workouts?machine={old_id}").status_code == 200


def test_693_quality_checks_dont_require_retired_qr_mapping():
    name = "QA693 No QR " + uuid4().hex[:9]
    with TestClient(app) as client:
        with SessionLocal() as db:
            db.add(WorkoutEquipment654(name=name, gym="Merritt Eldersburg",
                                       kind="selectorized", qr_value=None))
            db.commit()
            report = quality_summary674(db)
            assert not any(
                issue["kind"] == "Workout" and issue["label"] == name
                for issue in report["issues"]
            )
        page = client.get("/data-quality")
        assert page.status_code == 200
        assert "Equipment &amp; QR Mapping" not in page.text
        assert "Workout Equipment" in page.text
        assert "Machine has no QR mapping" not in page.text
    # Historical schema/data retained: no migration or destructive nulling.
    model = (ROOT / "app/workout_models654.py").read_text(encoding="utf-8")
    assert "qr_value:" in model
