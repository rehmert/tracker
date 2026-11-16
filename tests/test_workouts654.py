"""Release 654 focused tests. No live DB, unrelated suites, or network."""
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.db import engine
from app.main import app

ROOT = Path(__file__).resolve().parents[1]


def _post(client, path, data=None):
    return client.post(path, data=data or {}, follow_redirects=False)


def test_654_catalog_qr_free_weights_and_session_logging():
    with TestClient(app) as client:
        assert {
            "workout_equipment654", "workout_sessions654", "workout_sets654"
        } <= set(inspect(engine).get_table_names())

        page = client.get("/workouts")
        assert page.status_code == 200
        assert "Find a machine" in page.text

        created = _post(client, "/workouts/equipment", {
            "name": "Nautilus Chest Press", "kind": "selectorized",
            "manufacturer": "Nautilus", "seat_setting": "4",
            "qr_value": "https://example.invalid/nautilus/test-654",
        })
        assert created.status_code == 303
        assert created.headers["location"].startswith("/workouts?msg=")

        duplicate = _post(client, "/workouts/equipment", {
            "name": "Duplicate Chest Press", "kind": "selectorized",
            "qr_value": "https://example.invalid/nautilus/test-654",
        })
        assert duplicate.status_code == 303
        assert duplicate.headers["location"].startswith("/workouts?err=")

        home = client.get("/workouts").text
        assert "Nautilus Chest Press" in home
        assert "Setup: 4" in home

        from app.workout_models654 import WorkoutEquipment654
        from app.db import SessionLocal
        with SessionLocal() as db:
            machine = db.query(WorkoutEquipment654).filter(
                WorkoutEquipment654.name == "Nautilus Chest Press"
            ).one()
            machine_id = machine.id

        found = client.get("/workouts/qr", params={
            "code": "https://example.invalid/nautilus/test-654"
        }, follow_redirects=False)
        assert found.status_code == 303
        assert f"machine={machine_id}" in found.headers["location"]
        unknown = client.get(
            "/workouts/qr", params={"code": "not-a-known-machine"},
            follow_redirects=False,
        )
        assert unknown.headers["location"].startswith("/workouts?err=")

        free = _post(client, "/workouts/equipment", {
            "name": "Dumbbell Curl", "kind": "free_weight", "gym": "Home"
        })
        assert free.status_code == 303

        assert _post(client, "/workouts/start").status_code == 303
        invalid = _post(client, "/workouts/sets", {
            "equipment_id": machine_id, "weight_lb": "-5", "reps": "10"
        })
        assert invalid.headers["location"].startswith("/workouts?err=")
        valid = _post(client, "/workouts/sets", {
            "equipment_id": machine_id, "weight_lb": "100", "reps": "12", "effort": "7"
        })
        assert valid.status_code == 303
        logged = client.get("/workouts").text
        assert "100.0 lb" in logged and "12" in logged
        assert "Dumbbell Curl" in logged

        finished = _post(client, "/workouts/finish")
        assert finished.status_code == 303
        late = _post(client, "/workouts/sets", {
            "equipment_id": machine_id, "weight_lb": "100", "reps": "10"
        })
        assert late.headers["location"].startswith("/workouts?err=")


def test_654_template_and_route_contract():
    from jinja2 import Environment

    Environment().parse(
        (ROOT / "app/templates/workouts654.html").read_text(encoding="utf-8")
    )
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    nav = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")
    assert "app.include_router(workouts654.router)" in main
    assert "('/workouts','Workouts')" in nav
    assert "get_scoped_db390" in (
        ROOT / "app/routers/workouts654.py"
    ).read_text(encoding="utf-8")
    assert (ROOT / "app/static/css/tracker-workouts654.css").is_file()
