"""Release 665: exact-machine historical comparison and read-only routine planning."""
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from jinja2 import Environment
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal
from app.main import app
from app.routers.workouts665 import routine_plan_data665
from app.workout_models654 import (
    WorkoutEquipment654, WorkoutSession654, WorkoutSet654,
)
from app.workout_models655 import (
    WorkoutRoutine655, WorkoutRoutineItem655,
)

ROOT = Path(__file__).resolve().parents[1]


def test_665_two_completed_sessions_exact_equipment_chronological_even_if_backdated(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "plan665.sqlite"))
    try:
        Base.metadata.create_all(engine, tables=[
            WorkoutEquipment654.__table__,
            WorkoutSession654.__table__, WorkoutSet654.__table__,
            WorkoutRoutine655.__table__, WorkoutRoutineItem655.__table__,
        ])
        with Session(engine) as db:
            routine = WorkoutRoutine655(name="665 Upper")
            another = WorkoutRoutine655(name="665 Lower")
            press = WorkoutEquipment654(name="Press", gym="Home", kind="selectorized")
            row = WorkoutEquipment654(name="Row", gym="Home", kind="selectorized")
            outsider = WorkoutEquipment654(name="Outsider", gym="Other", kind="free_weight")
            db.add_all([routine, another, press, row, outsider])
            db.flush()
            db.add_all([
                WorkoutRoutineItem655(routine_id=routine.id, equipment_id=press.id, position=2),
                WorkoutRoutineItem655(routine_id=routine.id, equipment_id=row.id, position=0),
                WorkoutRoutineItem655(routine_id=another.id, equipment_id=outsider.id, position=0),
            ])

            def workout(day, machine, sets, complete=True):
                started = datetime(2026, 5, day, 9)
                session = WorkoutSession654(
                    started_at=started,
                    completed_at=started + timedelta(hours=1) if complete else None,
                )
                db.add(session)
                db.flush()
                for load, reps in sets:
                    db.add(WorkoutSet654(
                        session_id=session.id, equipment_id=machine.id,
                        weight_lb=load, reps=reps, performed_at=started,
                    ))
                return session

            # Insert in a different order from actual workout dates.
            prior = workout(6, press, [(80, 10), (75, 12)])
            latest = workout(18, press, [(100, 8), (90, 10)])
            earliest = workout(2, press, [(70, 10)])
            active = workout(20, press, [(999, 200)], complete=False)
            empty = workout(19, press, [])
            future = WorkoutSession654(
                started_at=datetime.now() + timedelta(days=30),
                completed_at=datetime.now() + timedelta(days=30, hours=1),
            )
            db.add(future)
            db.flush()
            db.add(WorkoutSet654(
                session_id=future.id, equipment_id=press.id,
                weight_lb=1900, reps=200,
                performed_at=future.started_at,
            ))
            other = workout(20, outsider, [(900, 10)])
            db.commit()
            before = db.scalar(select(func.count(WorkoutSet654.id)))

            data = routine_plan_data665(db, routine.id)
            assert data["routine"].id == routine.id
            assert len(data["rows"]) == 2
            assert data["history_count"] == 1
            assert [x["equipment"].id for x in data["rows"]] == [row.id, press.id]
            assert data["rows"][0]["latest"] is None
            chosen = data["rows"][1]
            assert chosen["latest"].session_id == latest.id
            assert chosen["previous"].session_id == prior.id
            assert chosen["latest"].sets == 2
            assert chosen["latest"].reps == 18
            assert chosen["latest"].heaviest_lb == 100
            assert chosen["latest"].volume == 1700
            assert chosen["previous"].volume == 1700
            assert chosen["load_change"] == 20
            assert chosen["volume_change"] == 0
            excluded = {earliest.id, active.id, empty.id, future.id, other.id}
            assert chosen["latest"].session_id not in excluded
            assert chosen["previous"].session_id not in excluded
            assert db.scalar(select(func.count(WorkoutSet654.id))) == before
            assert routine_plan_data665(db, another.id)["rows"][0]["latest"].session_id == other.id
    finally:
        engine.dispose()


def test_665_get_routine_planning_read_only_and_escapes_user_data():
    nonce = uuid4().hex
    with TestClient(app) as client:
        with SessionLocal() as db:
            routine = WorkoutRoutine655(name="665 Routine " + nonce)
            machine = WorkoutEquipment654(
                name="665 <svg onload=alert(1)> " + nonce,
                gym="665 Trial", kind="selectorized",
            )
            db.add_all([routine, machine])
            db.flush()
            item = WorkoutRoutineItem655(
                routine_id=routine.id, equipment_id=machine.id, position=0,
            )
            db.add(item)
            db.flush()
            sid = WorkoutSession654(
                started_at=datetime(2026, 6, 13, 9),
                completed_at=datetime(2026, 6, 13, 10),
            )
            db.add(sid)
            db.flush()
            db.add(WorkoutSet654(
                session_id=sid.id, equipment_id=machine.id,
                weight_lb=95.5, reps=10,
                performed_at=datetime(2026, 6, 13, 9),
            ))
            db.commit()
            rid, item_id, session_id = routine.id, item.id, sid.id
            before = (
                db.scalar(select(func.count(WorkoutSession654.id))),
                db.scalar(select(func.count(WorkoutSet654.id))),
            )

        plan = client.get(f"/workouts/routines/{rid}/plan")
        assert plan.status_code == 200
        assert "Workout Program Planner" in plan.text
        assert f'data-routine-id665="{rid}"' in plan.text
        assert f'data-item-id665="{item_id}"' in plan.text
        assert "95.5 lb" in plan.text
        assert "Only one completed session" in plan.text
        assert f'href="/workouts/sessions/{session_id}/review"' in plan.text
        assert "Targets are optional" in plan.text
        assert "only in this browser on this device" in plan.text
        assert "&lt;svg onload=alert(1)&gt;" in plan.text
        assert "<svg onload=alert(1)>" not in plan.text
        assert "tracker-workout-plan665.js?v=665" in plan.text
        assert 'data-field665="weight"' in plan.text
        assert 'data-field665="sets"' in plan.text
        assert 'data-field665="reps"' in plan.text
        assert f'href="/workouts/routines/{rid}/plan"' in client.get(
            f"/workouts/routines/{rid}"
        ).text
        assert f'href="/workouts/routines/{rid}/plan"' in client.get(
            "/workouts/routines"
        ).text
        assert client.get("/workouts/routines/999999999/plan").status_code == 404

        for _ in range(2):
            assert client.get(f"/workouts/routines/{rid}/plan").status_code == 200
        with SessionLocal() as db:
            after = (
                db.scalar(select(func.count(WorkoutSession654.id))),
                db.scalar(select(func.count(WorkoutSet654.id))),
            )
        assert after == before


def test_665_empty_routine_and_existing_quick_endpoints_preserved():
    with TestClient(app) as client:
        with SessionLocal() as db:
            routine = WorkoutRoutine655(name="665 Empty " + uuid4().hex)
            db.add(routine)
            db.commit()
            rid = routine.id
        empty = client.get(f"/workouts/routines/{rid}/plan")
        assert empty.status_code == 200
        assert "There are no exercises" in empty.text
        assert 'data-routine-id665=' in empty.text

        quick = client.get("/workouts/quick")
        assert quick.status_code == 200
        assert 'action="/workouts/quick/start"' in quick.text or (
            'action="/workouts/quick/sets"' in quick.text
        )


def test_665_source_and_rendering_contract():
    route = (ROOT / "app/routers/workouts665.py").read_text()
    html = (ROOT / "app/templates/workout_plan665.html").read_text()
    js = (ROOT / "app/static/js/tracker-workout-plan665.js").read_text()
    Environment().parse(html)
    for token in (
        "get_scoped_db390",
        '@router.get("/workouts/routines/{routine_id}/plan")',
        "WorkoutSession654.completed_at.is_not(None)",
        "WorkoutSession654.started_at < tomorrow",
        "WorkoutSet654.equipment_id == equipment.id",
        "WorkoutRoutineItem655.routine_id == routine.id",
        "WorkoutSession654.started_at.desc()",
        ".limit(MAX_COMPARISON_SESSIONS665)",
    ):
        assert token in route
    for forbidden in (
        "@router.post(", "db.add(", "db.commit(", "db.delete(",
        "Base.metadata", "urlopen(", "requests.", "httpx",
    ):
        assert forbidden not in route
    assert "app.include_router(workouts665.router)" in (ROOT / "app/main.py").read_text()
    assert "localStorage" in js
    assert "tracker.workout665.plan.routine." in js
    assert "JSON.stringify" in js and "JSON.parse" in js
    for forbidden in ("fetch(", "XMLHttpRequest", "innerHTML", "document.cookie"):
        assert forbidden not in js
