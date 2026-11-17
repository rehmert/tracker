"""Release 659 focused HTTP tests: rapid workout reuses validated writes and is scoped."""
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from app.workout_models655 import WorkoutRoutine655, WorkoutRoutineItem655

ROOT = Path(__file__).resolve().parents[1]


def post(client, path, data=None):
    return client.post(path, data=data or {}, follow_redirects=False)


def machine659(client, label):
    name = label + " " + uuid4().hex[:8]
    result = post(client, "/workouts/equipment", {
        "name": name, "kind": "selectorized", "gym": "659 QA Gym",
    })
    assert result.status_code == 303
    with SessionLocal() as db:
        item = db.scalar(select(WorkoutEquipment654).where(
            WorkoutEquipment654.name == name
        ).order_by(WorkoutEquipment654.id.desc()))
        assert item
        return item.id, name


def test_659_quick_mode_free_workout_and_server_validated_sets():
    with TestClient(app) as client:
        first, label = machine659(client, "659 Cable Press")
        second, _ = machine659(client, "659 Row")
        ready = client.get(f"/workouts/quick?machine={first}")
        assert ready.status_code == 200
        assert "Rapid Gym Mode" in ready.text
        assert "Start Free Workout" in ready.text
        assert "Gym Mode" in client.get("/workouts").text

        started = post(client, "/workouts/quick/start")
        assert started.status_code == 303
        assert started.headers["location"].startswith("/workouts/quick?msg=")

        page = client.get(f"/workouts/quick?machine={first}")
        assert page.status_code == 200
        assert label in page.text
        assert 'action="/workouts/quick/sets"' in page.text
        assert 'action="/workouts/quick/repeat"' not in page.text
        assert 'name="weight_lb"' in page.text
        assert 'name="reps"' in page.text
        assert "Rest Timer" in page.text
        assert 'data-session-id="' in page.text
        assert 'action="/workouts/quick/finish"' in page.text

        for data in (
            {"equipment_id": first, "weight_lb": "-5", "reps": "12"},
            {"equipment_id": first, "weight_lb": "NaN", "reps": "12"},
            {"equipment_id": first, "weight_lb": "100", "reps": "0"},
            {"equipment_id": first, "weight_lb": "100", "reps": "12", "effort": "11"},
        ):
            rejected = post(client, "/workouts/quick/sets", data)
            assert rejected.status_code == 303
            assert f"/workouts/quick?machine={first}&err=" in rejected.headers["location"]
            assert "logged=1" not in rejected.headers["location"]

        with SessionLocal() as db:
            assert db.scalar(select(WorkoutSet654.id).where(
                WorkoutSet654.equipment_id == first
            )) is None

        good = post(client, "/workouts/quick/sets", {
            "equipment_id": first, "weight_lb": "95.5",
            "reps": "12", "effort": "7",
        })
        assert good.status_code == 303
        assert f"/workouts/quick?machine={first}&logged=1&msg=" in good.headers["location"]

        with SessionLocal() as db:
            source = db.scalar(select(WorkoutSet654).where(
                WorkoutSet654.equipment_id == first
            ).order_by(WorkoutSet654.id.desc()))
            assert source
            source_id = source.id
            active_session = source.session_id

        after = client.get(f"/workouts/quick?machine={first}&logged=1")
        assert after.status_code == 200
        assert 'data-logged="yes"' in after.text
        assert f'data-last-set-id="{source_id}"' in after.text
        assert 'action="/workouts/quick/repeat"' in after.text
        assert "95.5 lb × 12" in after.text

        repeated = post(client, "/workouts/quick/repeat", {
            "equipment_id": first, "source_set_id": source_id,
            "weight_lb": "500", "reps": "1",
        })
        assert repeated.status_code == 303
        assert "logged=1" in repeated.headers["location"]
        stale = post(client, "/workouts/quick/repeat", {
            "equipment_id": first, "source_set_id": source_id,
        })
        assert stale.status_code == 303
        assert "err=" in stale.headers["location"]
        assert "logged=1" not in stale.headers["location"]

        with SessionLocal() as db:
            rows = list(db.scalars(select(WorkoutSet654).where(
                WorkoutSet654.session_id == active_session,
                WorkoutSet654.equipment_id == first,
            ).order_by(WorkoutSet654.id)))
            assert [(row.weight_lb, row.reps, row.effort) for row in rows] == [
                (95.5, 12, 7), (95.5, 12, 7),
            ]
            assert db.get(WorkoutSession654, active_session).completed_at is None

        # Switching the selected machine must never create or log a set.
        changed = client.get(f"/workouts/quick?machine={second}")
        assert changed.status_code == 200
        assert 'value="' + str(second) + '" selected' in changed.text
        assert 'name="equipment_id" value="' + str(second) + '"' in changed.text
        assert "No sets recorded on this machine" in changed.text
        assert "95.5 lb × 12" not in changed.text

        finished = post(client, "/workouts/quick/finish")
        assert finished.status_code == 303
        assert finished.headers["location"].startswith("/workouts/quick?msg=")
        with SessionLocal() as db:
            assert db.get(WorkoutSession654, active_session).completed_at is not None

        forbidden = post(client, "/workouts/quick/repeat", {
            "equipment_id": first, "source_set_id": source_id,
        })
        assert forbidden.status_code == 303
        assert "err=" in forbidden.headers["location"]


def test_659_routine_start_machine_navigation_and_progress():
    with TestClient(app) as client:
        first, first_name = machine659(client, "659 Nautilus A")
        second, second_name = machine659(client, "659 Nautilus B")
        name = "659 Ordered " + uuid4().hex[:9]
        assert post(client, "/workouts/routines", {"name": name}).status_code == 303
        with SessionLocal() as db:
            routine = db.scalar(select(WorkoutRoutine655).where(
                WorkoutRoutine655.name == name
            ))
            assert routine
            rid = routine.id
        for eid in (first, second):
            assert post(client, f"/workouts/routines/{rid}/equipment", {
                "equipment_id": eid,
            }).status_code == 303
        entry = client.get("/workouts/quick")
        assert entry.status_code == 200
        assert f'action="/workouts/quick/routines/{rid}/start"' in entry.text

        launch = post(client, f"/workouts/quick/routines/{rid}/start")
        assert launch.status_code == 303
        assert f"/workouts/quick?machine={first}&msg=" in launch.headers["location"]
        page = client.get(f"/workouts/quick?machine={first}")
        assert page.status_code == 200
        assert name in page.text
        assert "0 of 2 exercises logged" in page.text
        assert f'href="/workouts/quick?machine={second}"' in page.text
        assert "Next: " + second_name in page.text
        assert "This session on " + first_name in page.text

        logged = post(client, "/workouts/quick/sets", {
            "equipment_id": first, "weight_lb": "80", "reps": "10",
        })
        assert "logged=1" in logged.headers["location"]
        assert "1 of 2 exercises logged" in client.get("/workouts/quick").text

        second_page = client.get(f"/workouts/quick?machine={second}")
        assert second_page.status_code == 200
        assert f'href="/workouts/quick?machine={first}"' in second_page.text
        assert post(client, "/workouts/quick/sets", {
            "equipment_id": second, "weight_lb": "75", "reps": "8",
        }).status_code == 303
        assert "2 of 2 exercises logged" in client.get(f"/workouts/quick?machine={second}").text

        with SessionLocal() as db:
            selected = db.scalar(select(WorkoutSession654).where(
                WorkoutSession654.completed_at.is_(None)
            ))
            assert selected
            session_id = selected.id
        assert post(client, "/workouts/quick/finish").status_code == 303
        record = client.get(f"/workouts/sessions/{session_id}")
        assert record.status_code == 200
        assert "80.0 lb" in record.text and "75.0 lb" in record.text


def test_659_reuse_existing_protection_and_no_schema():
    from jinja2 import Environment

    source = (ROOT / "app/routers/workouts659.py").read_text()
    assert 'get_scoped_db390' in source
    assert 'add_set654(' in source
    assert 'repeat_last_set655(' in source
    assert 'start_routine655(' in source
    assert 'finish654(' in source
    assert 'active654(db)' in source
    assert 'session_id == active.id' in source
    assert 'from ..workout_models654' in source
    assert 'db.commit()' not in source
    assert 'Base.metadata' not in source
    assert 'httpx' not in source
    assert 'app.include_router(workouts659.router)' in (
        ROOT / "app/main.py"
    ).read_text()
    for template in ("workout_quick659.html", "workouts654.html"):
        Environment().parse((ROOT / "app/templates" / template).read_text())
    page = (ROOT / "app/templates/workout_quick659.html").read_text()
    assert "workout659-rest-display" in page
    assert "workout659-machine-select" in page
    assert 'name="source_set_id"' in page
    assert "Next: " in page
    assert (ROOT / "app/static/js/tracker-workouts659.js").is_file()
    assert (ROOT / "app/static/css/tracker-workouts659.css").is_file()
