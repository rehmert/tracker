"""Release 657 scoped workout correction, deletion and routine navigation tests."""
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from app.workout_models655 import WorkoutRoutine655, WorkoutRoutineItem655

ROOT = Path(__file__).resolve().parents[1]


def post(client, path, data=None):
    return client.post(path, data=data or {}, follow_redirects=False)


def find_machine(name):
    with SessionLocal() as db:
        return db.scalar(
            select(WorkoutEquipment654.id)
            .where(WorkoutEquipment654.name == name)
            .order_by(WorkoutEquipment654.id.desc())
            .limit(1)
        )


def test_657_correction_delete_and_completed_workout_protection():
    with TestClient(app) as client:
        response = post(client, "/workouts/equipment", {
            "name": "Nautilus Safety Press 657", "kind": "selectorized",
        })
        assert response.status_code == 303
        equipment_id = find_machine("Nautilus Safety Press 657")
        assert equipment_id
        assert post(client, "/workouts/start").status_code == 303
        assert post(client, "/workouts/sets", {
            "equipment_id": equipment_id, "weight_lb": "100",
            "reps": "11", "effort": "6",
        }).status_code == 303
        with SessionLocal() as db:
            prior = db.scalar(
                select(WorkoutSet654)
                .where(WorkoutSet654.equipment_id == equipment_id)
                .order_by(WorkoutSet654.id.desc()).limit(1)
            )
            assert prior
            set_id = prior.id
            original_time = prior.performed_at
            active_id = prior.session_id

        page = client.get("/workouts").text
        assert 'action="/workouts/sets/' + str(set_id) + '/edit"' in page
        assert 'action="/workouts/sets/' + str(set_id) + '/delete"' in page
        assert 'value="yes" required' in page
        assert "Save Correction" in page
        assert "Edit or remove this set" in page

        invalid = post(client, f"/workouts/sets/{set_id}/edit", {
            "weight_lb": "-2", "reps": "15", "effort": "7",
        })
        assert invalid.status_code == 303
        assert "err=" in invalid.headers["location"]
        invalid = post(client, f"/workouts/sets/{set_id}/edit", {
            "weight_lb": "100", "reps": "12", "effort": "11",
        })
        assert invalid.status_code == 303
        assert "err=" in invalid.headers["location"]
        not_confirmed = post(client, f"/workouts/sets/{set_id}/delete")
        assert not_confirmed.status_code == 303
        assert "err=" in not_confirmed.headers["location"]

        with SessionLocal() as db:
            original = db.get(WorkoutSet654, set_id)
            assert original
            assert (original.weight_lb, original.reps, original.effort) == (100, 11, 6)

        edited = post(client, f"/workouts/sets/{set_id}/edit", {
            "weight_lb": "95.5", "reps": "12", "effort": "",
        })
        assert edited.status_code == 303
        assert edited.headers["location"].startswith(
            f"/workouts?machine={equipment_id}&msg="
        )
        with SessionLocal() as db:
            changed = db.get(WorkoutSet654, set_id)
            assert changed
            assert (changed.weight_lb, changed.reps, changed.effort) == (95.5, 12, None)
            assert changed.performed_at == original_time
            assert changed.session_id == active_id
            assert changed.equipment_id == equipment_id

        removed = post(client, f"/workouts/sets/{set_id}/delete", {
            "confirm_delete": "yes",
        })
        assert removed.status_code == 303
        assert "msg=" in removed.headers["location"]
        with SessionLocal() as db:
            assert db.get(WorkoutSet654, set_id) is None
        assert post(client, "/workouts/finish").status_code == 303

        assert post(client, "/workouts/sets/12345678/edit", {
            "weight_lb": "50", "reps": "10",
        }).headers["location"].startswith("/workouts?err=")

        assert post(client, "/workouts/start").status_code == 303
        assert post(client, "/workouts/sets", {
            "equipment_id": equipment_id, "weight_lb": "85",
            "reps": "8",
        }).status_code == 303
        with SessionLocal() as db:
            latest_id = db.scalar(
                select(WorkoutSet654.id)
                .where(WorkoutSet654.equipment_id == equipment_id)
                .order_by(WorkoutSet654.id.desc()).limit(1)
            )
        assert post(client, "/workouts/finish").status_code == 303
        # Completed sets must never be changed, even while a newer
        # unrelated workout is active.
        assert post(client, "/workouts/start").status_code == 303
        completed_edit = post(client, f"/workouts/sets/{latest_id}/edit", {
            "weight_lb": "50", "reps": "10",
        })
        assert completed_edit.status_code == 404
        completed_delete = post(client, f"/workouts/sets/{latest_id}/delete", {
            "confirm_delete": "yes",
        })
        assert completed_delete.status_code == 404
        with SessionLocal() as db:
            record = db.get(WorkoutSet654, latest_id)
            assert record and (record.weight_lb, record.reps) == (85, 8)
        assert post(client, "/workouts/finish").status_code == 303


def test_657_routine_next_machine_and_logged_exercise_count():
    with TestClient(app) as client:
        for name in ("657 Cable Row", "657 Leg Extension"):
            assert post(client, "/workouts/equipment", {
                "name": name, "kind": "selectorized",
            }).status_code == 303
        first = find_machine("657 Cable Row")
        second = find_machine("657 Leg Extension")
        assert first and second
        assert post(client, "/workouts/routines", {
            "name": "657 Gym Circuit",
        }).status_code == 303
        with SessionLocal() as db:
            routine_id = db.scalar(
                select(WorkoutRoutine655.id)
                .where(WorkoutRoutine655.name == "657 Gym Circuit")
                .order_by(WorkoutRoutine655.id.desc()).limit(1)
            )
        assert routine_id
        for equipment_id in (first, second):
            assert post(client, f"/workouts/routines/{routine_id}/equipment", {
                "equipment_id": equipment_id,
            }).status_code == 303

        started = post(client, f"/workouts/routines/{routine_id}/start")
        assert started.status_code == 303
        assert f"machine={first}" in started.headers["location"]
        page = client.get(f"/workouts?machine={first}")
        assert page.status_code == 200
        assert "0 of 2" in page.text
        assert f'href="/workouts?machine={second}#workout-machine-{second}"' in page.text
        assert f'id="workout-machine-{first}"' in page.text
        assert f'id="workout-machine-{second}"' in page.text
        assert page.text.index("657 Cable Row") < page.text.index("657 Leg Extension")

        assert post(client, "/workouts/sets", {
            "equipment_id": first, "weight_lb": "70", "reps": "10",
        }).status_code == 303
        page = client.get("/workouts")
        assert "1 of 2" in page.text
        assert "1 set recorded today" in page.text
        assert post(client, "/workouts/sets", {
            "equipment_id": first, "weight_lb": "75", "reps": "10",
        }).status_code == 303
        page = client.get("/workouts")
        assert "1 of 2" in page.text
        assert "2 sets recorded today" in page.text
        assert post(client, "/workouts/sets", {
            "equipment_id": second, "weight_lb": "75", "reps": "10",
        }).status_code == 303
        assert "2 of 2" in client.get("/workouts").text
        assert post(client, "/workouts/finish").status_code == 303


def test_657_new_ui_is_server_validated_and_scoped():
    from jinja2 import Environment

    template = (ROOT / "app/templates/workouts654.html").read_text()
    Environment().parse(template)
    assert "workout657-set-actions" in template
    assert "workout657-delete-form" in template
    assert 'name="confirm_delete" value="yes" required' in template
    route = (ROOT / "app/routers/workouts657.py").read_text()
    assert "get_scoped_db390" in route
    assert 'entry.session_id != current.id' in route
    assert 'if confirm_delete != "yes":' in route
    assert "math.isfinite(weight_lb)" in route
    assert "entry.performed_at" not in route
    main = (ROOT / "app/main.py").read_text()
    assert "app.include_router(workouts657.router)" in main
    assert (ROOT / "app/static/css/tracker-workouts657.css").is_file()
