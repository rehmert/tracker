"""Release 716: active workout machine insertion, existing set safety, and stale form gates.

All writes use the scoped, disposable test database supplied by qualification.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from app.workout_models655 import (
    WorkoutRoutine655, WorkoutRoutineItem655, WorkoutSessionRoutine655,
)


def setup716(*, routine=False):
    # Tracker creates scoped Workout tables during the app lifespan.
    # Initialize the disposable test app before opening SessionLocal.
    with TestClient(app):
        pass
    with SessionLocal() as db:
        for other in db.scalars(select(WorkoutSession654).where(
            WorkoutSession654.completed_at.is_(None)
        )):
            other.completed_at = datetime.now()
        tag = uuid4().hex[:12]
        machines = []
        for label in ("Chest Press", "Seated Row"):
            machine = WorkoutEquipment654(
                name=f"QA716 {label} {tag}", gym="QA716 Gym", kind="selectorized",
            )
            db.add(machine)
            machines.append(machine)
        db.flush()
        session = WorkoutSession654(started_at=datetime.now())
        db.add(session)
        db.flush()
        rid = None
        if routine:
            program = WorkoutRoutine655(name="QA716 routine " + tag)
            db.add(program)
            db.flush()
            rid = program.id
            db.add(WorkoutRoutineItem655(
                routine_id=rid, equipment_id=machines[0].id, position=0
            ))
            db.add(WorkoutSessionRoutine655(session_id=session.id, routine_id=rid))
        db.commit()
        return session.id, machines[0].id, machines[1].id, rid


def test_716_active_free_workout_select_machine_without_creating_fake_sets():
    sid, first, second, _ = setup716()
    with TestClient(app) as client:
        page = client.get("/workouts/quick")
        assert page.status_code == 200
        assert 'id="workout716-add-machine"' in page.text
        # Global page-title casing would otherwise modify equipment labels.
        assert '<h2 data-no-title-case>' in page.text
        assert '[data-no-title-case]' in (
            __import__("pathlib").Path(__file__).resolve().parents[1] /
            "app/static/js/tracker-page-title-case.js"
        ).read_text(encoding="utf-8")
        assert 'href="/workouts#workout-sets657"' in page.text
        assert 'action="/workouts/quick/machines"' in page.text
        response = client.post("/workouts/quick/machines", data={
            "session_id": sid, "equipment_id": second,
        }, follow_redirects=False)
        assert response.status_code == 303
        assert f"/workouts/quick?machine={second}" in response.headers["location"]
        with SessionLocal() as db:
            assert list(db.scalars(select(WorkoutSet654).where(
                WorkoutSet654.session_id == sid
            ))) == []
            assert db.get(WorkoutSessionRoutine655, sid) is None


def test_716_routine_add_is_saved_once_without_rewriting_active_sets():
    sid, first, second, rid = setup716(routine=True)
    with SessionLocal() as db:
        db.add(WorkoutSet654(
            session_id=sid, equipment_id=first, weight_lb=95, reps=8
        ))
        db.commit()
    with TestClient(app) as client:
        page = client.get("/workouts/quick")
        assert page.status_code == 200
        assert f'/workouts/routines/{rid}#routine-exercises655' in page.text
        assert "Adding a machine also updates your saved routine" in page.text
        response = client.post("/workouts/quick/machines", data={
            "session_id": sid, "equipment_id": second,
        }, follow_redirects=False)
        assert response.status_code == 303
        assert f"/workouts/quick?machine={second}" in response.headers["location"]
        updated = client.get(f"/workouts/quick?machine={second}")
        assert "1 of 2 exercises logged" in updated.text
        assert f'option value="{second}" selected' in updated.text
        duplicate = client.post("/workouts/quick/machines", data={
            "session_id": sid, "equipment_id": second,
        }, follow_redirects=False)
        assert "err=" in duplicate.headers["location"]
    with SessionLocal() as db:
        items = list(db.scalars(select(WorkoutRoutineItem655).where(
            WorkoutRoutineItem655.routine_id == rid
        ).order_by(WorkoutRoutineItem655.position)))
        assert [(item.equipment_id, item.position) for item in items] == [
            (first, 0), (second, 1),
        ]
        sets = list(db.scalars(select(WorkoutSet654).where(
            WorkoutSet654.session_id == sid
        )))
        assert len(sets) == 1
        assert (sets[0].equipment_id, sets[0].weight_lb, sets[0].reps) == (
            first, 95, 8,
        )


def test_716_create_new_machine_during_active_routine_and_open_it():
    sid, first, second, rid = setup716(routine=True)
    name = "QA716 new " + uuid4().hex[:12]
    with TestClient(app) as client:
        invalid = client.post("/workouts/quick/machines/new", data={
            "session_id": sid, "name": "Nope", "kind": "invalid", "gym": "Gym"
        }, follow_redirects=False)
        assert "err=" in invalid.headers["location"]
        created = client.post("/workouts/quick/machines/new", data={
            "session_id": sid, "name": name, "kind": "plate_loaded",
            "gym": "QA716 Gym", "manufacturer": "Nautilus", "seat_setting": "3",
        }, follow_redirects=False)
        assert created.status_code == 303
        assert "msg=" in created.headers["location"]
        with SessionLocal() as db:
            machine = db.scalar(select(WorkoutEquipment654).where(
                WorkoutEquipment654.name == name
            ))
            assert machine is not None
            assert (machine.kind, machine.manufacturer, machine.seat_setting) == (
                "plate_loaded", "Nautilus", "3"
            )
            added = db.scalar(select(WorkoutRoutineItem655).where(
                WorkoutRoutineItem655.routine_id == rid,
                WorkoutRoutineItem655.equipment_id == machine.id,
            ))
            assert added is not None
            assert f"machine={machine.id}" in created.headers["location"]
        repeat = client.post("/workouts/quick/machines/new", data={
            "session_id": sid, "name": name.lower(), "gym": "QA716 Gym",
        }, follow_redirects=False)
        assert "err=" in repeat.headers["location"]
    with SessionLocal() as db:
        assert len(list(db.scalars(select(WorkoutEquipment654).where(
            WorkoutEquipment654.name.ilike(name)
        )))) == 1


def test_716_stale_session_form_and_missing_machine_do_not_change_workout():
    sid, first, second, rid = setup716(routine=True)
    with TestClient(app) as client:
        for endpoint, data in (
            ("/workouts/quick/machines", {"equipment_id": second}),
            ("/workouts/quick/machines/new", {"name": "Stale 716", "gym": "Gym"}),
        ):
            response = client.post(endpoint, data={
                "session_id": sid + 900000, **data,
            }, follow_redirects=False)
            assert "err=" in response.headers["location"]
        response = client.post("/workouts/quick/machines", data={
            "session_id": sid, "equipment_id": 999999999,
        }, follow_redirects=False)
        assert response.status_code == 404
    with SessionLocal() as db:
        items = list(db.scalars(select(WorkoutRoutineItem655).where(
            WorkoutRoutineItem655.routine_id == rid
        )))
        assert len(items) == 1 and items[0].equipment_id == first
        assert db.scalar(select(WorkoutEquipment654).where(
            WorkoutEquipment654.name == "Stale 716"
        )) is None


def test_716_free_workout_new_machine_does_not_change_any_routine():
    sid, _, _, _ = setup716()
    name = "QA716 free " + uuid4().hex[:12]
    with TestClient(app) as client:
        created = client.post("/workouts/quick/machines/new", data={
            "session_id": sid, "name": name, "gym": "QA716 Gym",
        }, follow_redirects=False)
        assert created.status_code == 303
        assert "msg=" in created.headers["location"]
    with SessionLocal() as db:
        machine = db.scalar(select(WorkoutEquipment654).where(
            WorkoutEquipment654.name == name
        ))
        assert machine and f"machine={machine.id}" in created.headers["location"]
        assert db.get(WorkoutSessionRoutine655, sid) is None
        assert not list(db.scalars(select(WorkoutSet654).where(
            WorkoutSet654.session_id == sid
        )))
