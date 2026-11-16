"""Release 655 focused tests: ordered routines and safe last-set repetition."""
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text

from app.db import Base, SessionLocal, engine
from app.main import app
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from app.workout_models655 import (
    WorkoutRoutine655, WorkoutRoutineItem655, WorkoutSessionRoutine655,
)

ROOT = Path(__file__).resolve().parents[1]


def post(client, path, data=None):
    return client.post(path, data=data or {}, follow_redirects=False)


def _equipment(client, name):
    result = post(client, "/workouts/equipment", {
        "name": name, "kind": "selectorized", "gym": "Merritt Eldersburg",
    })
    assert result.status_code == 303
    with SessionLocal() as db:
        return db.scalar(select(WorkoutEquipment654.id).where(
            WorkoutEquipment654.name == name
        ))


def test_655_routine_workflow_order_and_repeat_last_set():
    with TestClient(app) as client:
        assert {"workout_routines655", "workout_routine_items655",
                "workout_session_routines655"} <= set(inspect(engine).get_table_names())

        chest = _equipment(client, "Nautilus Chest Press 655")
        row = _equipment(client, "Nautilus Seated Row 655")
        assert chest and row

        result = post(client, "/workouts/routines", {"name": "Upper Body A"})
        assert result.status_code == 303
        with SessionLocal() as db:
            rid = db.scalar(select(WorkoutRoutine655.id).where(
                WorkoutRoutine655.name == "Upper Body A"
            ))
        target = f"/workouts/routines/{rid}"
        assert result.headers["location"].startswith(target)
        assert client.get(target).status_code == 200
        assert post(client, target + "/start").headers["location"].startswith(target + "?err=")

        assert post(client, target + "/equipment", {"equipment_id": chest}).status_code == 303
        assert post(client, target + "/equipment", {"equipment_id": row}).status_code == 303
        duplicate = post(client, target + "/equipment", {"equipment_id": row})
        assert duplicate.headers["location"].startswith(target + "?err=")

        with SessionLocal() as db:
            items = list(db.scalars(select(WorkoutRoutineItem655).where(
                WorkoutRoutineItem655.routine_id == rid
            ).order_by(WorkoutRoutineItem655.position, WorkoutRoutineItem655.id)))
            assert [x.equipment_id for x in items] == [chest, row]
            row_item = next(x for x in items if x.equipment_id == row)

        assert post(client, f"{target}/items/{row_item.id}/move", {
            "direction": "up"
        }).status_code == 303
        with SessionLocal() as db:
            ids = list(db.scalars(select(WorkoutRoutineItem655.equipment_id).where(
                WorkoutRoutineItem655.routine_id == rid
            ).order_by(WorkoutRoutineItem655.position, WorkoutRoutineItem655.id)))
            assert ids == [row, chest]

        started = post(client, target + "/start")
        assert started.status_code == 303
        assert started.headers["location"].startswith(f"/workouts?machine={row}")
        with SessionLocal() as db:
            session_id = db.scalar(select(WorkoutSession654.id).where(
                WorkoutSession654.completed_at.is_(None)
            ))
            assert session_id
            link = db.get(WorkoutSessionRoutine655, session_id)
            assert link and link.routine_id == rid

        home = client.get("/workouts")
        assert home.status_code == 200
        assert home.text.index("Nautilus Seated Row 655") < home.text.index("Nautilus Chest Press 655")
        assert "Upper Body A" in home.text

        original = post(client, "/workouts/sets", {
            "equipment_id": row, "weight_lb": "90", "reps": "12", "effort": "7",
        })
        assert original.status_code == 303
        with SessionLocal() as db:
            prior = db.scalar(select(WorkoutSet654).where(
                WorkoutSet654.equipment_id == row
            ).order_by(WorkoutSet654.id.desc()))
            source_id = prior.id

        # Never trust weight or reps supplied by a repeat request: the server
        # looks up the latest set for this exact equipment.
        repeated = post(client, "/workouts/sets/repeat", {
            "equipment_id": row, "source_set_id": source_id,
            "weight_lb": "2000", "reps": "200",
        })
        assert repeated.status_code == 303
        assert repeated.headers["location"].startswith(f"/workouts?machine={row}&msg=")
        with SessionLocal() as db:
            logs = list(db.scalars(select(WorkoutSet654).where(
                WorkoutSet654.equipment_id == row
            ).order_by(WorkoutSet654.id)))
            assert len(logs) == 2
            assert [(x.weight_lb, x.reps, x.effort) for x in logs] == [
                (90, 12, 7), (90, 12, 7)
            ]

        # Old form cannot repeat after a newer set is recorded.
        stale = post(client, "/workouts/sets/repeat", {
            "equipment_id": row, "source_set_id": source_id,
        })
        assert stale.headers["location"].startswith(f"/workouts?machine={row}&err=")

        # A source set from a different machine is also rejected.
        mismatch = post(client, "/workouts/sets/repeat", {
            "equipment_id": chest, "source_set_id": source_id,
        })
        assert mismatch.headers["location"].startswith(f"/workouts?machine={chest}&err=")

        assert post(client, "/workouts/finish").status_code == 303
        blocked = post(client, "/workouts/sets/repeat", {
            "equipment_id": row, "source_set_id": source_id,
        })
        assert blocked.headers["location"].startswith("/workouts?err=")

        # Historical sessions retain the selected routine association.
        history = client.get(f"/workouts/sessions/{session_id}")
        assert history.status_code == 200
        assert "90.0 lb" in history.text


def test_655_routines_are_isolated_from_each_other():
    with TestClient(app) as client:
        first_id = _equipment(client, "Leg Extension 655")
        r1 = post(client, "/workouts/routines", {"name": "Leg Day A"})
        r2 = post(client, "/workouts/routines", {"name": "Leg Day B"})
        assert r1.status_code == r2.status_code == 303
        with SessionLocal() as db:
            routines = list(db.scalars(select(WorkoutRoutine655).where(
                WorkoutRoutine655.name.in_(["Leg Day A", "Leg Day B"])
            ).order_by(WorkoutRoutine655.id)))
            assert len(routines) == 2
            a, b = (routine.id for routine in routines)
        assert post(client, f"/workouts/routines/{a}/equipment", {
            "equipment_id": first_id
        }).status_code == 303
        with SessionLocal() as db:
            item = db.scalar(select(WorkoutRoutineItem655).where(
                WorkoutRoutineItem655.routine_id == a
            ))
            assert item
        # Cannot mutate a routine item by supplying a different routine id.
        forbidden = post(client, f"/workouts/routines/{b}/items/{item.id}/remove")
        assert forbidden.status_code == 404
        assert post(client, f"/workouts/routines/{a}/start").status_code == 303
        collision = post(client, f"/workouts/routines/{b}/start")
        assert collision.headers["location"].startswith(f"/workouts/routines/{b}?err=")
        assert post(client, f"/workouts/routines/{a}/items/{item.id}/remove").status_code == 303
        with SessionLocal() as db:
            assert db.get(WorkoutRoutineItem655, item.id) is None


def test_655_additive_schema_rehearsal_preserves_654_rows(tmp_path):
    from sqlalchemy import create_engine

    sandbox = create_engine("sqlite:///" + str(tmp_path / "existing654.db"))
    try:
        with sandbox.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TABLE existing_654_canary(id INTEGER PRIMARY KEY, marker TEXT NOT NULL)"
            )
            conn.exec_driver_sql(
                "INSERT INTO existing_654_canary(id,marker) VALUES(1,'preserved')"
            )
        Base.metadata.create_all(sandbox)
        Base.metadata.create_all(sandbox)
        assert {"workout_routines655", "workout_routine_items655",
                "workout_session_routines655"} <= set(inspect(sandbox).get_table_names())
        with sandbox.connect() as conn:
            assert conn.execute(text(
                "SELECT marker FROM existing_654_canary WHERE id=1"
            )).scalar_one() == "preserved"
    finally:
        sandbox.dispose()


def test_655_ui_and_isolation_contract():
    from jinja2 import Environment

    for name in ("workout_routines655.html", "workout_routine_detail655.html", "workouts654.html"):
        Environment().parse((ROOT / "app/templates" / name).read_text())
    main = (ROOT / "app/main.py").read_text()
    assert "app.include_router(workouts655.router)" in main
    router = (ROOT / "app/routers/workouts655.py").read_text()
    assert "get_scoped_db390" in router
    assert "urlopen(" not in router
    assert "Repeat Last Set" in (ROOT / "app/templates/workouts654.html").read_text()
