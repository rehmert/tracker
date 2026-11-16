"""Release 658: historical workout entry is atomic, scoped and never touches active sessions."""
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal
from app.main import app
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from app.workout_models655 import WorkoutRoutine655, WorkoutSessionRoutine655

ROOT = Path(__file__).resolve().parents[1]


def post(client, path, data=None):
    return client.post(path, data=data or {}, follow_redirects=False)


def equipment658(client):
    unique = "History " + uuid4().hex[:8]
    r = post(client, "/workouts/equipment", {
        "name": unique, "gym": "Backfill QA", "kind": "selectorized",
    })
    assert r.status_code == 303
    with SessionLocal() as db:
        eid = db.scalar(select(WorkoutEquipment654.id).where(
            WorkoutEquipment654.name == unique
        ))
    assert eid
    return eid, unique


def day658():
    return (datetime.now() - timedelta(days=3)).date().isoformat()


def entry658(eid, *, day=None, end="10:30", start="09:00", weight="100",
             reps="12", effort="7", set_time="09:45"):
    return {
        "day": day if day is not None else day658(),
        "start_time": start, "end_time": end,
        "equipment_id": [str(eid), ""],
        "weight_lb": [weight, ""],
        "reps": [reps, ""],
        "effort": [effort, ""],
        "set_time": [set_time, ""],
    }


def sessions658():
    with SessionLocal() as db:
        return db.scalar(select(func.count(WorkoutSession654.id)))


def test_658_create_historical_routine_sets_and_preserve_active_session():
    with TestClient(app) as client:
        eid, machine = equipment658(client)
        second, _ = equipment658(client)
        routine_name = "Backfill " + uuid4().hex
        assert post(client, "/workouts/routines", {"name": routine_name}).status_code == 303
        with SessionLocal() as db:
            routine_id = db.scalar(select(WorkoutRoutine655.id).where(
                WorkoutRoutine655.name == routine_name
            ))
        assert routine_id
        assert post(client, "/workouts/start").status_code == 303
        with SessionLocal() as db:
            active_id = db.scalar(select(WorkoutSession654.id).where(
                WorkoutSession654.completed_at.is_(None)
            ))
        assert active_id

        form = client.get("/workouts/backfill")
        assert form.status_code == 200
        assert "Log Previous Workout" in form.text
        assert 'name="start_time"' in form.text
        assert 'name="set_time"' in form.text
        assert 'name="routine_id"' in form.text

        data = {
            "day": day658(), "start_time": "09:00", "end_time": "10:30",
            "routine_id": str(routine_id),
            "equipment_id": [str(eid), str(second), ""],
            "weight_lb": ["100", "75.5", ""],
            "reps": ["12", "8", ""],
            "effort": ["7", "", ""],
            "set_time": ["09:45", "", ""],
        }
        response = post(client, "/workouts/backfill", data)
        assert response.status_code == 303, response.text[:400]
        assert response.headers["location"].startswith("/workouts/sessions/")
        historical_id = int(response.headers["location"].split("?")[0].split("/")[-1])

        with SessionLocal() as db:
            saved = db.get(WorkoutSession654, historical_id)
            assert saved
            assert saved.started_at == datetime.fromisoformat(day658() + "T09:00")
            assert saved.completed_at == datetime.fromisoformat(day658() + "T10:30")
            assert db.get(WorkoutSessionRoutine655, historical_id).routine_id == routine_id
            recorded = list(db.scalars(select(WorkoutSet654).where(
                WorkoutSet654.session_id == historical_id
            ).order_by(WorkoutSet654.id)))
            assert len(recorded) == 2
            assert [(x.equipment_id, x.weight_lb, x.reps, x.effort) for x in recorded] == [
                (eid, 100.0, 12, 7), (second, 75.5, 8, None),
            ]
            assert recorded[0].performed_at == datetime.fromisoformat(day658() + "T09:45")
            # Unknown exact set time is not silently assigned to the current time.
            assert recorded[1].performed_at == saved.started_at
            active = db.get(WorkoutSession654, active_id)
            assert active and active.completed_at is None

        history = client.get(f"/workouts/sessions/{historical_id}")
        assert history.status_code == 200
        assert machine in history.text and "100.0 lb" in history.text
        assert "75.5 lb" in history.text
        assert client.get(f"/workouts/equipment/{eid}/progress").status_code == 200
        page = client.get("/workouts")
        assert page.status_code == 200 and "Workout in progress" in page.text
        assert "Log a Previous Workout" in page.text
        assert post(client, "/workouts/finish").status_code == 303


def test_658_reject_invalid_rows_and_keep_all_user_entries():
    with TestClient(app) as client:
        eid, _ = equipment658(client)
        original_count = sessions658()
        cases = [
            ({}, "Record at least one"),
            ({"weight_lb": ["-1", "" ]}, "weight must be between"),
            ({"weight_lb": ["NaN", "" ]}, "weight must be between"),
            ({"weight_lb": ["inf", "" ]}, "weight must be between"),
            ({"reps": ["0", ""]}, "repetitions must be 1 to 200"),
            ({"reps": ["3.5", ""]}, "repetitions must be a whole number"),
            ({"effort": ["11", ""]}, "effort must be 1 to 10"),
            ({"set_time": ["11:00", ""]}, "set time must be within"),
            ({"equipment_id": ["9999999", ""]}, "choose an existing machine"),
            ({"end_time": "08:00"}, "End time must be after"),
        ]
        for overrides, expected in cases[:-1]:
            data = entry658(eid)
            if not overrides:
                data.update(equipment_id=["", ""], weight_lb=["", ""], reps=["", ""],
                            effort=["", ""], set_time=["", ""])
            else:
                data.update(overrides)
            failed = post(client, "/workouts/backfill", data)
            assert failed.status_code == 200, failed.status_code
            assert "Not saved" in failed.text and expected in failed.text, expected
            assert 'name="start_time" value="09:00"' in failed.text
            assert sessions658() == original_count
        # Invalid layout must reject all rows rather than shifting columns.
        mismatched = entry658(eid)
        mismatched["reps"] = ["12"]
        response = post(client, "/workouts/backfill", mismatched)
        assert "Incomplete set rows" in response.text
        assert sessions658() == original_count


def test_658_duplicate_future_limit_and_history_ordering():
    with TestClient(app) as client:
        eid, _ = equipment658(client)
        data = entry658(
            eid, day=(datetime.now() - timedelta(days=5)).date().isoformat(),
            set_time="",
        )
        first = post(client, "/workouts/backfill", data)
        assert first.status_code == 303
        count = sessions658()
        repeated = post(client, "/workouts/backfill", data)
        assert repeated.status_code == 200
        assert "already exists" in repeated.text
        assert sessions658() == count

        invalid_future = entry658(
            eid, day=(datetime.now() + timedelta(days=1)).date().isoformat()
        )
        rejected = post(client, "/workouts/backfill", invalid_future)
        assert rejected.status_code == 200 and "past or today" in rejected.text
        assert sessions658() == count

        invalid_long = entry658(eid, start="00:01", end="23:30")
        rejected = post(client, "/workouts/backfill", invalid_long)
        assert rejected.status_code == 200 and "12 hours" in rejected.text
        assert sessions658() == count

        many = entry658(eid)
        for key in ("equipment_id", "weight_lb", "reps", "effort", "set_time"):
            many[key] = many[key] + [""] * 39
        rejected = post(client, "/workouts/backfill", many)
        assert rejected.status_code == 200 and "Maximum 40 sets" in rejected.text
        assert sessions658() == count


def test_658_source_and_template_are_schema_free():
    from jinja2 import Environment

    source = (ROOT / "app/routers/workouts658.py").read_text()
    assert "get_scoped_db390" in source
    assert "db.add(session)" in source
    assert "db.flush()" in source
    assert "db.commit()" in source
    assert "WorkoutSessionRoutine655" in source
    assert "datetime.now()" in source
    assert "math.isfinite(pounds)" in source
    assert "MAX_HISTORICAL_SETS658 = 40" in source
    assert "ALTER TABLE" not in source
    assert "Base.metadata" not in source
    assert "app.include_router(workouts658.router)" in (
        ROOT / "app/main.py"
    ).read_text()
    assert "Log a Previous Workout" in (
        ROOT / "app/templates/workouts654.html"
    ).read_text()
    Environment().parse(
        (ROOT / "app/templates/workout_backfill658.html").read_text()
    )
    assert (ROOT / "app/static/js/tracker-workouts658.js").is_file()
    assert (ROOT / "app/static/css/tracker-workouts658.css").is_file()
