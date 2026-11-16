"""Release 663: read-only session aggregates and validated finish delegation."""
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from jinja2 import Environment

from app.db import SessionLocal
from app.main import app
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654

ROOT = Path(__file__).resolve().parents[1]


def post(client, path, data=None):
    return client.post(path, data=data or {}, follow_redirects=False)


def machine663(client, label, *, kind="selectorized"):
    result = post(client, "/workouts/equipment", {
        "name": label, "kind": kind, "gym": "663 QA Gym",
    })
    assert result.status_code == 303
    with SessionLocal() as db:
        item = db.scalar(select(WorkoutEquipment654).where(
            WorkoutEquipment654.name == label
        ).order_by(WorkoutEquipment654.id.desc()).limit(1))
        assert item
        return item.id


def test_663_finish_and_review_uses_existing_finish_once_with_real_totals():
    key = uuid4().hex[:9]
    with TestClient(app) as client:
        a = machine663(client, "663 Press " + key)
        b = machine663(client, "663 Bodyweight " + key, kind="bodyweight")
        home = client.get("/workouts")
        assert home.status_code == 200
        assert 'formaction="/workouts/finish-review"' in home.text
        assert 'action="/workouts/finish"' in home.text

        assert post(client, "/workouts/quick/start").status_code == 303
        quick = client.get(f"/workouts/quick?machine={a}")
        assert 'formaction="/workouts/finish-review"' in quick.text
        assert 'action="/workouts/quick/finish"' in quick.text

        with SessionLocal() as db:
            active = db.scalar(select(WorkoutSession654).where(
                WorkoutSession654.completed_at.is_(None)
            ).order_by(WorkoutSession654.id.desc()).limit(1))
            assert active
            sid = active.id

        for eid, lb, reps in ((a, "100", "10"), (a, "105", "8"), (b, "0", "12")):
            saved = post(client, "/workouts/quick/sets", {
                "equipment_id": eid, "weight_lb": lb, "reps": reps,
            })
            assert saved.status_code == 303
            assert "logged=1" in saved.headers["location"]

        with SessionLocal() as db:
            before_count = db.scalar(select(func.count(WorkoutSet654.id)).where(
                WorkoutSet654.session_id == sid
            ))
            assert before_count == 3

        ongoing = client.get(f"/workouts/sessions/{sid}/review")
        assert ongoing.status_code == 200
        assert "In progress" in ongoing.text
        assert "1,840.0" in ongoing.text
        assert "Recorded volume (lb × reps)" in ongoing.text
        assert "30" in ongoing.text
        assert "Exercise Breakdown" in ongoing.text
        assert "663 Press " + key in ongoing.text
        assert "663 Bodyweight " + key in ongoing.text
        assert "0.0 lb" in ongoing.text
        assert f"/workouts/sessions/{sid}" in ongoing.text
        assert f"/workouts/equipment/{a}/progress" in ongoing.text
        with SessionLocal() as db:
            assert db.scalar(select(func.count(WorkoutSet654.id)).where(
                WorkoutSet654.session_id == sid
            )) == before_count
            assert db.get(WorkoutSession654, sid).completed_at is None

        finished = post(client, "/workouts/finish-review")
        assert finished.status_code == 303
        assert finished.headers["location"].startswith(
            f"/workouts/sessions/{sid}/review?msg="
        )
        review = client.get(finished.headers["location"])
        assert review.status_code == 200
        assert "Workout Session Review" in review.text
        assert "Completed" in review.text
        assert "1,840.0" in review.text
        assert ">2</strong>" in review.text
        assert ">3</strong>" in review.text
        assert ">30</strong>" in review.text

        with SessionLocal() as db:
            complete_at = db.get(WorkoutSession654, sid).completed_at
            assert complete_at is not None
            assert db.scalar(select(func.count(WorkoutSet654.id)).where(
                WorkoutSet654.session_id == sid
            )) == before_count

        historical = client.get(f"/workouts/sessions/{sid}")
        assert historical.status_code == 200
        assert f'href="/workouts/sessions/{sid}/review"' in historical.text

        # A repeated completion request must not fabricate another workout.
        repeated = post(client, "/workouts/finish-review")
        assert repeated.status_code == 303
        assert repeated.headers["location"].startswith("/workouts?err=")
        with SessionLocal() as db:
            assert db.get(WorkoutSession654, sid).completed_at == complete_at


def test_663_empty_session_invalid_id_and_escaped_equipment():
    key = uuid4().hex[:9]
    unsafe = "663 <script>alert(1)</script> " + key
    with TestClient(app) as client:
        a = machine663(client, unsafe)
        assert post(client, "/workouts/start").status_code == 303
        with SessionLocal() as db:
            active = db.scalar(select(WorkoutSession654).where(
                WorkoutSession654.completed_at.is_(None)
            ).order_by(WorkoutSession654.id.desc()).limit(1))
            assert active
            sid = active.id
        empty = client.get(f"/workouts/sessions/{sid}/review")
        assert empty.status_code == 200
        assert "No sets were recorded during this workout." in empty.text
        assert "In progress" in empty.text
        assert ">0</strong>" in empty.text
        assert client.get("/workouts/sessions/999999999/review").status_code == 404

        assert post(client, "/workouts/sets", {
            "equipment_id": a, "weight_lb": "95.5", "reps": "11",
        }).status_code == 303
        review = client.get(f"/workouts/sessions/{sid}/review")
        assert review.status_code == 200
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in review.text
        assert "<script>alert(1)</script>" not in review.text
        assert "1,050.5" in review.text
        assert post(client, "/workouts/finish").status_code == 303


def test_663_source_only_access_and_unchanged_legacy_endpoints():
    for filename in (
        "workout_review663.html", "workouts654.html",
        "workout_quick659.html", "workout_history654.html",
    ):
        Environment().parse(
            (ROOT / "app/templates" / filename).read_text(encoding="utf-8")
        )
    source = (ROOT / "app/routers/workouts663.py").read_text(encoding="utf-8")
    for token in (
        "get_scoped_db390",
        '@router.get("/workouts/sessions/{session_id}/review")',
        '@router.post("/workouts/finish-review")',
        "active654(db)", "finish654(db=db)",
        "WorkoutSet654.session_id == session_id",
        "func.count(WorkoutSet654.id)",
        "func.sum(WorkoutSet654.reps)",
        "func.sum(entry_volume)",
        "func.max(WorkoutSet654.weight_lb)",
        "db.get(WorkoutSession654, session_id)",
    ):
        assert token in source
    for forbidden in (
        "db.add(", "db.delete(", "db.commit(", "Base.metadata", "DROP TABLE",
        "ALTER TABLE", "httpx", "requests.", "urlopen(",
    ):
        assert forbidden not in source

    main = (ROOT / "app/main.py").read_text()
    assert "app.include_router(workouts663.router)" in main
    quick = (ROOT / "app/templates/workout_quick659.html").read_text()
    assert 'action="/workouts/quick/finish"' in quick
    assert 'formaction="/workouts/finish-review"' in quick
    home = (ROOT / "app/templates/workouts654.html").read_text()
    assert 'action="/workouts/finish"' in home
    assert 'formaction="/workouts/finish-review"' in home
