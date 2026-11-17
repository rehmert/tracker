"""Release 667: persistent plans, immutable session snapshots, set types and goals."""
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, event, func, inspect, select
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal
from app.main import app
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from app.workout_models655 import WorkoutRoutine655, WorkoutRoutineItem655, WorkoutSessionRoutine655
from app.workout_models667 import (
    WorkoutRoutineConfig667, WorkoutRoutineTarget667,
    WorkoutSessionTarget667, WorkoutSetType667,
)
from app.workout_program667 import parse_goal667, rest667, snapshots667, progress667

ROOT = Path(__file__).resolve().parents[1]


def post667(client, path, data=None):
    return client.post(path, data=data or {}, follow_redirects=False)


@pytest.fixture
def cleanup_shared_workout667():
    """Undo all shared-DB records created by this Release 667 HTTP test.

    The historical dashboard shows only five completed sessions. Retaining
    new completed fixtures from this module can displace its older recorded
    session, even though neither dashboard code nor actual data is wrong.
    Keep new tests isolated instead of weakening older regression coverage.
    """
    with SessionLocal() as db:
        prior_sessions = set(db.scalars(select(WorkoutSession654.id)))
        prior_routines = set(db.scalars(select(WorkoutRoutine655.id)))
        prior_equipment = set(db.scalars(select(WorkoutEquipment654.id)))
    yield
    with SessionLocal() as db:
        session_ids = set(db.scalars(select(WorkoutSession654.id))) - prior_sessions
        routine_ids = set(db.scalars(select(WorkoutRoutine655.id))) - prior_routines
        equipment_ids = set(db.scalars(select(WorkoutEquipment654.id))) - prior_equipment
        if session_ids:
            set_ids = set(db.scalars(
                select(WorkoutSet654.id).where(
                    WorkoutSet654.session_id.in_(session_ids)
                )
            ))
            if set_ids:
                db.execute(delete(WorkoutSetType667).where(
                    WorkoutSetType667.set_id.in_(set_ids)
                ))
                db.execute(delete(WorkoutSet654).where(
                    WorkoutSet654.id.in_(set_ids)
                ))
            db.execute(delete(WorkoutSessionTarget667).where(
                WorkoutSessionTarget667.session_id.in_(session_ids)
            ))
            db.execute(delete(WorkoutSessionRoutine655).where(
                WorkoutSessionRoutine655.session_id.in_(session_ids)
            ))
            db.execute(delete(WorkoutSession654).where(
                WorkoutSession654.id.in_(session_ids)
            ))
        if routine_ids:
            item_ids = set(db.scalars(select(WorkoutRoutineItem655.id).where(
                WorkoutRoutineItem655.routine_id.in_(routine_ids)
            )))
            if item_ids:
                db.execute(delete(WorkoutRoutineTarget667).where(
                    WorkoutRoutineTarget667.routine_item_id.in_(item_ids)
                ))
                db.execute(delete(WorkoutRoutineItem655).where(
                    WorkoutRoutineItem655.id.in_(item_ids)
                ))
            db.execute(delete(WorkoutRoutineConfig667).where(
                WorkoutRoutineConfig667.routine_id.in_(routine_ids)
            ))
            db.execute(delete(WorkoutRoutine655).where(
                WorkoutRoutine655.id.in_(routine_ids)
            ))
        if equipment_ids:
            db.execute(delete(WorkoutEquipment654).where(
                WorkoutEquipment654.id.in_(equipment_ids)
            ))
        db.commit()


@pytest.mark.parametrize("fields,expected", [
    (("", "", ""), (None, None, None)),
    (("3", "10", "100.5"), (3, 10, 100.5)),
    (("20", "200", "0"), (20, 200, 0.0)),
])
def test_667_goal_parser_valid(fields, expected):
    assert parse_goal667(*fields) == expected


@pytest.mark.parametrize("fields", [
    ("3", "", "100"), ("", "10", "100"), ("3", "10", ""),
    ("0", "10", "100"), ("21", "10", "100"),
    ("3", "201", "100"), ("3", "-2", "100"),
    ("3.5", "10", "100"), ("3", "10", "-5"),
    ("3", "10", "nan"), ("3", "10", "Infinity"),
    ("3", "10", "2001"), ("3", "10", "1e309"),
    ("３", "10", "100"),
])
def test_667_goal_parser_fails_closed(fields):
    with pytest.raises(ValueError):
        parse_goal667(*fields)


def test_667_rest_presets_are_bounded():
    assert rest667("90") == 90
    assert rest667("", optional=True) is None
    for bad in ("", "13", "0", "999", "90.5", "nan", "-90"):
        with pytest.raises(ValueError):
            rest667(bad)


def test_667_additive_schema_snapshots_and_achievement_isolated(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "workout667.sqlite"))
    @event.listens_for(engine, "connect")
    def fk_on(conn, record):
        conn.execute("PRAGMA foreign_keys=ON")

    tables = [
        WorkoutEquipment654.__table__,
        WorkoutSession654.__table__,
        WorkoutSet654.__table__,
        WorkoutRoutine655.__table__,
        WorkoutRoutineItem655.__table__,
        WorkoutSessionRoutine655.__table__,
        WorkoutRoutineConfig667.__table__,
        WorkoutRoutineTarget667.__table__,
        WorkoutSessionTarget667.__table__,
        WorkoutSetType667.__table__,
    ]
    try:
        Base.metadata.create_all(engine, tables=tables)
        assert {"workout_routine_config667", "workout_routine_targets667",
                "workout_session_targets667", "workout_set_types667"} <= set(
                    inspect(engine).get_table_names()
                )
        with Session(engine) as db:
            routine = WorkoutRoutine655(name="667 Upper")
            machine = WorkoutEquipment654(name="667 Press", kind="selectorized", gym="QA")
            db.add_all([routine, machine])
            db.flush()
            item = WorkoutRoutineItem655(
                routine_id=routine.id, equipment_id=machine.id, position=0,
            )
            db.add(item)
            db.flush()
            db.add(WorkoutRoutineConfig667(routine_id=routine.id, rest_seconds=120))
            db.add(WorkoutRoutineTarget667(
                routine_item_id=item.id, target_sets=2, target_reps=10,
                target_weight_lb=100, setup_note="Seat 4 / neutral grip",
                rest_seconds=None,
            ))
            db.flush()
            workout = WorkoutSession654(started_at=datetime(2026, 11, 16, 9))
            db.add(workout)
            db.flush()
            snapshots667(db, routine.id, workout.id)
            db.flush()
            snap = db.get(WorkoutSessionTarget667, (workout.id, machine.id))
            assert snap and snap.rest_seconds == 120
            assert snap.setup_note == "Seat 4 / neutral grip"
            # Repeated start logic cannot create duplicates.
            snapshots667(db, routine.id, workout.id)
            db.flush()
            assert db.scalar(select(func.count(WorkoutSessionTarget667.session_id))) == 1
            target = db.get(WorkoutRoutineTarget667, item.id)
            target.target_sets, target.target_weight_lb = 5, 110
            db.flush()
            assert snap.target_sets == 2 and snap.target_weight_lb == 100

            def add_set(weight, reps, kind=None):
                entry = WorkoutSet654(
                    session_id=workout.id, equipment_id=machine.id,
                    weight_lb=weight, reps=reps,
                )
                db.add(entry)
                db.flush()
                if kind is not None:
                    db.add(WorkoutSetType667(set_id=entry.id, set_type=kind))
                return entry

            add_set(150, 20, "warmup")
            first = add_set(100, 10)
            add_set(100, 9)
            db.flush()
            status = progress667(db, workout.id, machine.id)
            assert status["working_sets"] == 2
            assert status["warmup_sets"] == 1
            assert status["credited_sets"] == 1
            assert status["progress_percent"] == 50
            assert status["achieved"] is False
            add_set(105, 10, "working")
            db.flush()
            status = progress667(db, workout.id, machine.id)
            assert status["working_sets"] == 3
            assert status["credited_sets"] == 2
            assert status["achieved"] is True
            assert status["progress_percent"] == 100
            # Deleting an actual set cascades only its type annotation.
            db.delete(first)
            db.commit()
            assert progress667(db, workout.id, machine.id)["achieved"] is False
    finally:
        engine.dispose()


def test_667_http_program_snapshots_import_and_rapid_gym_workflow(cleanup_shared_workout667):
    nonce = uuid4().hex
    with TestClient(app) as client:
        with SessionLocal() as db:
            machine = WorkoutEquipment654(
                name="667 Chest " + nonce, gym="QA", kind="selectorized",
                seat_setting="3", setup_notes="Equipment cue",
            )
            outsider = WorkoutEquipment654(
                name="667 Row " + nonce, gym="QA", kind="selectorized",
            )
            routine = WorkoutRoutine655(name="667 Push " + nonce)
            other = WorkoutRoutine655(name="667 Other " + nonce)
            db.add_all([machine, outsider, routine, other])
            db.flush()
            item = WorkoutRoutineItem655(
                routine_id=routine.id, equipment_id=machine.id, position=0,
            )
            external = WorkoutRoutineItem655(
                routine_id=other.id, equipment_id=outsider.id, position=0,
            )
            db.add_all([item, external])
            db.commit()
            rid, iid, other_id, eid = routine.id, item.id, other.id, external.id
            machine_id = machine.id
        url = f"/workouts/routines/{rid}/program"
        rendered = client.get(url)
        assert rendered.status_code == 200
        assert "Persisted" not in rendered.text or "Program" in rendered.text
        assert "Workout Program" in rendered.text
        assert "Equipment cue" in rendered.text
        assert "target_sets" in rendered.text
        assert "Import This Browser" in rendered.text
        assert client.get("/workouts/routines/99999999/program").status_code == 404

        invalid = post667(client, url + f"/items/{iid}", {
            "target_sets": "3", "target_reps": "10", "target_weight_lb": "NaN",
            "setup_note": "Should not save",
        })
        assert invalid.status_code == 303 and "err=" in invalid.headers["location"]
        assert post667(client, url + f"/items/{eid}", {
            "target_sets": "3", "target_reps": "10", "target_weight_lb": "100",
        }).status_code == 404
        assert "err=" in post667(client, url + "/rest", {"rest_seconds": "919"}).headers["location"]

        assert "msg=" in post667(client, url + "/rest", {"rest_seconds": "120"}).headers["location"]
        assert "msg=" in post667(client, url + f"/items/{iid}", {
            "target_sets": "2", "target_reps": "10", "target_weight_lb": "100",
            "rest_seconds": "75", "setup_note": "Seat 3, neutral grip",
        }).headers["location"]
        with SessionLocal() as db:
            saved = db.get(WorkoutRoutineTarget667, iid)
            assert saved and saved.target_sets == 2 and saved.rest_seconds == 75
            assert saved.setup_note == "Seat 3, neutral grip"

        bad_import = post667(client, url + "/import", {
            "targets_json": '{"version":1,"targets":{"' + str(eid) +
                            '":{"sets":"2","reps":"8","weight":"95"}}}',
        })
        assert bad_import.status_code == 303 and "err=" in bad_import.headers["location"]
        with SessionLocal() as db:
            assert db.get(WorkoutRoutineTarget667, iid).target_weight_lb == 100
        good_import = post667(client, url + "/import", {
            "targets_json": '{"version":1,"targets":{"' + str(iid) +
                            '":{"sets":"3","reps":"10","weight":"95.5"}}}',
        })
        assert good_import.status_code == 303 and "msg=" in good_import.headers["location"]
        incomplete_import = post667(client, url + "/import", {
            "targets_json": '{"version":1,"targets":{"' + str(iid) +
                            '":{"sets":"2","reps":"","weight":"100"}}}',
        })
        assert incomplete_import.status_code == 303
        assert "err=" in incomplete_import.headers["location"]
        with SessionLocal() as db:
            assert db.get(WorkoutRoutineTarget667, iid).target_weight_lb == 95.5

        started = post667(client, f"/workouts/quick/routines/{rid}/start")
        assert started.status_code == 303
        with SessionLocal() as db:
            sid = db.scalar(select(WorkoutSession654.id).where(
                WorkoutSession654.completed_at.is_(None),
            ).order_by(WorkoutSession654.id.desc()))
            assert sid
            frozen = db.get(WorkoutSessionTarget667, (sid, machine_id))
            assert frozen and frozen.target_sets == 3
            assert frozen.target_weight_lb == 95.5
            assert frozen.rest_seconds == 75

        quick = client.get(f"/workouts/quick?machine={machine_id}")
        assert quick.status_code == 200
        assert 'id="workout667-active-goal"' in quick.text
        assert "3 working sets" in quick.text
        assert 'data-rest-seconds667="75"' in quick.text
        assert 'id="workout667-use-goal"' in quick.text
        assert 'name="set_type"' in quick.text
        assert "Seat 3, neutral grip" in quick.text

        rejected_kind = post667(client, "/workouts/quick/sets", {
            "equipment_id": machine_id, "weight_lb": "110", "reps": "20",
            "set_type": "rest",
        })
        assert rejected_kind.status_code == 303
        assert "err=" in rejected_kind.headers["location"]
        with SessionLocal() as db:
            assert db.scalar(select(func.count(WorkoutSet654.id)).where(
                WorkoutSet654.session_id == sid
            )) == 0

        warmup = post667(client, "/workouts/quick/sets", {
            "equipment_id": machine_id, "weight_lb": "110", "reps": "20",
            "set_type": "warmup",
        })
        assert warmup.status_code == 303 and "logged=1" in warmup.headers["location"]
        for _ in range(2):
            recorded = post667(client, "/workouts/quick/sets", {
                "equipment_id": machine_id, "weight_lb": "95.5",
                "reps": "10", "set_type": "working",
            })
            assert recorded.status_code == 303
        with SessionLocal() as db:
            actuals = list(db.scalars(select(WorkoutSet654).where(
                WorkoutSet654.session_id == sid
            ).order_by(WorkoutSet654.id)))
            assert len(actuals) == 3
            assert db.get(WorkoutSetType667, actuals[0].id).set_type == "warmup"
            assert db.get(WorkoutSetType667, actuals[1].id) is None
            assert progress667(db, sid, machine_id)["credited_sets"] == 2

        change = post667(client, url + f"/items/{iid}", {
            "target_sets": "1", "target_reps": "5", "target_weight_lb": "60",
            "setup_note": "New setup",
        })
        assert change.status_code == 303
        with SessionLocal() as db:
            frozen = db.get(WorkoutSessionTarget667, (sid, machine_id))
            assert frozen.target_sets == 3 and frozen.target_weight_lb == 95.5
            assert frozen.setup_note == "Seat 3, neutral grip"

        finish = post667(client, "/workouts/finish-review")
        assert finish.status_code == 303
        review = client.get(f"/workouts/sessions/{sid}/review")
        assert review.status_code == 200
        assert "Planned vs actual" in review.text
        assert "2 / 3 qualifying" in review.text
        assert "2 working, 1 warm-up" in review.text
        assert "Goal not yet achieved" in review.text
        with SessionLocal() as db:
            assert db.get(WorkoutSession654, sid).completed_at is not None
            assert db.get(WorkoutSessionTarget667, (sid, machine_id)).target_sets == 3


def test_667_repeat_and_active_correction_preserve_set_kind(cleanup_shared_workout667):
    nonce = uuid4().hex
    with TestClient(app) as client:
        with SessionLocal() as db:
            machine = WorkoutEquipment654(
                name="667 Repeat " + nonce, gym="QA", kind="selectorized",
            )
            db.add(machine)
            db.commit()
            machine_id = machine.id
        started = post667(client, "/workouts/quick/start")
        assert started.status_code == 303
        first = post667(client, "/workouts/quick/sets", {
            "equipment_id": machine_id, "weight_lb": "45",
            "reps": "12", "set_type": "warmup",
        })
        assert first.status_code == 303
        with SessionLocal() as db:
            sid = db.scalar(select(WorkoutSession654.id).where(
                WorkoutSession654.completed_at.is_(None)
            ).order_by(WorkoutSession654.id.desc()).limit(1))
            last = db.scalar(select(WorkoutSet654).where(
                WorkoutSet654.session_id == sid
            ).order_by(WorkoutSet654.id.desc()))
            source_id = last.id
            assert db.get(WorkoutSetType667, source_id).set_type == "warmup"

        repeated = post667(client, "/workouts/quick/repeat", {
            "equipment_id": machine_id, "source_set_id": source_id,
        })
        assert repeated.status_code == 303
        with SessionLocal() as db:
            sets = list(db.scalars(select(WorkoutSet654).where(
                WorkoutSet654.session_id == sid
            ).order_by(WorkoutSet654.id.asc())))
            assert len(sets) == 2
            assert all(db.get(WorkoutSetType667, entry.id).set_type == "warmup"
                       for entry in sets)
            copied_id = sets[-1].id

        corrected = post667(client, f"/workouts/sets/{copied_id}/edit", {
            "weight_lb": "50", "reps": "8",
            "set_type": "working", "effort": "6",
        })
        assert corrected.status_code == 303
        with SessionLocal() as db:
            saved = db.get(WorkoutSet654, copied_id)
            assert saved and saved.weight_lb == 50 and saved.reps == 8
            assert db.get(WorkoutSetType667, copied_id) is None
            assert progress667(db, sid, machine_id)["working_sets"] == 1
            assert progress667(db, sid, machine_id)["warmup_sets"] == 1

        view = client.get("/workouts")
        assert view.status_code == 200
        assert "Recorded set type" in view.text
        assert 'value="warmup" selected' in view.text
        assert post667(client, "/workouts/quick/finish").status_code == 303


def test_667_exercise_notes_display_without_numeric_goal(cleanup_shared_workout667):
    nonce = uuid4().hex
    with TestClient(app) as client:
        with SessionLocal() as db:
            machine = WorkoutEquipment654(
                name="667 Note only " + nonce, gym="QA", kind="selectorized",
            )
            routine = WorkoutRoutine655(name="667 Note routine " + nonce)
            db.add_all([machine, routine])
            db.flush()
            item = WorkoutRoutineItem655(
                routine_id=routine.id, equipment_id=machine.id, position=0,
            )
            db.add(item)
            db.commit()
            rid, iid, mid = routine.id, item.id, machine.id
        saved = post667(client, f"/workouts/routines/{rid}/program/items/{iid}", {
            "setup_note": "Neutral handle, seat position 5",
            "rest_seconds": "120",
        })
        assert saved.status_code == 303 and "msg=" in saved.headers["location"]
        assert post667(client, f"/workouts/quick/routines/{rid}/start").status_code == 303
        with SessionLocal() as db:
            sid = db.scalar(select(WorkoutSession654.id).where(
                WorkoutSession654.completed_at.is_(None)
            ).order_by(WorkoutSession654.id.desc()).limit(1))
            assert db.get(WorkoutSessionTarget667, (sid, mid)) is None
        quick = client.get(f"/workouts/quick?machine={mid}")
        assert quick.status_code == 200
        assert "Neutral handle, seat position 5" in quick.text
        assert 'data-rest-seconds667="120"' in quick.text
        assert 'id="workout667-active-goal"' not in quick.text
        assert post667(client, "/workouts/quick/finish").status_code == 303


def test_667_existing_source_separation_and_model_registration():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "from . import workout_models667" in main
    assert "app.include_router(workouts667.router)" in main
    route = (ROOT / "app/routers/workouts667.py").read_text(encoding="utf-8")
    assert "get_scoped_db390" in route
    assert "WorkoutRoutineItem655.routine_id == routine_id" in route
    assert "@router.post" in route
    snapshot = (ROOT / "app/routers/workouts655.py").read_text(encoding="utf-8")
    assert "snapshots667(db, routine_id, workout.id)" in snapshot
    log = (ROOT / "app/routers/workouts654.py").read_text(encoding="utf-8")
    assert "db.add(WorkoutSetType667(" in log and "db.commit()" in log
    assert "workout_set_types667" in (ROOT / "app/workout_models667.py").read_text()
