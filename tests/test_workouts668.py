"""Release 668 integrated tests: all remaining workout roadmap features.

Each HTTP test uses a completely separate SQLite database through the scoped
dependency override; no completed fixtures leak to older dashboard tests.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.main import app
from app.scoped_db390 import get_scoped_db390
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from app.workout_models655 import WorkoutRoutine655, WorkoutRoutineItem655, WorkoutSessionRoutine655
from app.workout_models667 import WorkoutRoutineConfig667, WorkoutRoutineTarget667, WorkoutSessionTarget667, WorkoutSetType667
from app.workout_models668 import (
    WorkoutTrainingDay668, WorkoutRoutineGroup668, WorkoutSessionSubstitution668,
    WorkoutSetAudit668, WorkoutLoadSemantics668, WorkoutImportReceipt668,
    WorkoutOfflineReceipt668,
)
from app.routers.workouts668_csv import parse_csv668, CSV_COLUMNS668
from app.routers.workouts668_insights import summary668

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def isolated668(tmp_path):
    engine = create_engine(
        "sqlite:///" + str(tmp_path / "test668.sqlite"),
        connect_args={"check_same_thread": False},
    )
    @event.listens_for(engine, "connect")
    def _foreign_keys(conn, record):
        conn.execute("PRAGMA foreign_keys=ON")
    tables = [
        WorkoutEquipment654.__table__, WorkoutSession654.__table__,
        WorkoutSet654.__table__, WorkoutRoutine655.__table__,
        WorkoutRoutineItem655.__table__, WorkoutSessionRoutine655.__table__,
        WorkoutRoutineConfig667.__table__, WorkoutRoutineTarget667.__table__,
        WorkoutSessionTarget667.__table__, WorkoutSetType667.__table__,
        WorkoutTrainingDay668.__table__, WorkoutRoutineGroup668.__table__,
        WorkoutSessionSubstitution668.__table__, WorkoutSetAudit668.__table__,
        WorkoutLoadSemantics668.__table__, WorkoutImportReceipt668.__table__,
        WorkoutOfflineReceipt668.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    Local = sessionmaker(engine, expire_on_commit=False)
    def scoped():
        with Local() as db:
            yield db
    prior = app.dependency_overrides.get(get_scoped_db390)
    app.dependency_overrides[get_scoped_db390] = scoped
    try:
        with TestClient(app) as client:
            yield client, Local
    finally:
        if prior is None:
            app.dependency_overrides.pop(get_scoped_db390, None)
        else:
            app.dependency_overrides[get_scoped_db390] = prior
        engine.dispose()


def post(client, path, data=None):
    return client.post(path, data=data or {}, follow_redirects=False)


def fixture_equipment(db, label="Press"):
    machine = WorkoutEquipment654(name="668 " + label, kind="selectorized", gym="QA")
    db.add(machine)
    db.flush()
    return machine


def fixture_routine(db, machines, name="668 Upper"):
    routine = WorkoutRoutine655(name=name)
    db.add(routine)
    db.flush()
    items = []
    for pos, machine in enumerate(machines):
        item = WorkoutRoutineItem655(
            routine_id=routine.id, equipment_id=machine.id, position=pos
        )
        db.add(item)
        db.flush()
        items.append(item)
    return routine, items


def test_668_weekly_groups_duplicate_routine_and_calendar(isolated668):
    client, Local = isolated668
    with Local() as db:
        a, b = fixture_equipment(db), fixture_equipment(db, "Row")
        routine, items = fixture_routine(db, (a,b))
        db.add(WorkoutRoutineTarget667(
            routine_item_id=items[0].id, target_sets=3, target_reps=8,
            target_weight_lb=100, rest_seconds=120, setup_note="Seat 3",
        ))
        db.commit()
        rid, iid, bid, aid = routine.id, items[0].id, items[1].id, a.id

    assert client.get("/workouts/programs").status_code == 200
    assert "msg=" in post(client, "/workouts/programs/schedule", {
        "weekday": "2", "routine_id": rid, "note": "Upper A",
    }).headers["location"]
    assert "err=" in post(client, "/workouts/programs/schedule", {
        "weekday": "7", "routine_id": rid
    }).headers["location"]
    assert "msg=" in post(client, f"/workouts/routines/{rid}/groups/{iid}", {
        "label": "A", "mode": "superset",
    }).headers["location"]
    assert "msg=" in post(client, f"/workouts/routines/{rid}/groups/{bid}", {
        "label": "A", "mode": "superset",
    }).headers["location"]
    detail = client.get(f"/workouts/routines/{rid}")
    assert detail.status_code == 200
    assert "Group label" in detail.text and "superset" in detail.text
    assert "Duplicate Routine" in detail.text
    assert "Upper A" in client.get("/workouts/programs").text
    assert "Weekly Program" in client.get("/workouts/calendar").text

    response = post(client, f"/workouts/routines/{rid}/duplicate")
    assert response.status_code == 303
    with Local() as db:
        copies = list(db.scalars(select(WorkoutRoutine655).where(
            WorkoutRoutine655.id != rid
        )))
        assert len(copies) == 1
        copied = copies[0]
        copy_items = list(db.scalars(select(WorkoutRoutineItem655).where(
            WorkoutRoutineItem655.routine_id == copied.id
        ).order_by(WorkoutRoutineItem655.position)))
        assert len(copy_items) == 2
        assert db.get(WorkoutRoutineTarget667, copy_items[0].id).target_weight_lb == 100
        assert db.get(WorkoutRoutineGroup668, copy_items[0].id).label == "A"
        assert db.get(WorkoutTrainingDay668, 1).weekday == 2
        assert db.scalar(select(func.count(WorkoutSession654.id))) == 0


def test_668_substitution_is_explicit_and_not_an_equivalent_goal(isolated668):
    client, Local = isolated668
    with Local() as db:
        a = fixture_equipment(db)
        alt = fixture_equipment(db, "Alternative")
        routine, items = fixture_routine(db, [a])
        db.add(WorkoutRoutineTarget667(
            routine_item_id=items[0].id, target_sets=2,
            target_reps=10, target_weight_lb=90,
        ))
        db.commit()
        rid, original, alternate = routine.id, a.id, alt.id
    assert post(client, f"/workouts/routines/{rid}/start").status_code == 303
    response = post(client, "/workouts/quick/substitution", {
        "original_equipment_id": original, "alternate_equipment_id": alternate,
    })
    assert response.status_code == 303 and "machine=" + str(alternate) in response.headers["location"]
    page = client.get(f"/workouts/quick?machine={original}")
    assert "not credited as equivalent" in page.text
    assert "Alternative" in page.text
    assert "Substituted machine" in client.get(f"/workouts/quick?machine={alternate}").text
    assert post(client, "/workouts/quick/sets", {
        "equipment_id": alternate, "weight_lb": "100", "reps": "12"
    }).status_code == 303
    locked = post(client, "/workouts/quick/substitution", {
        "original_equipment_id": original, "alternate_equipment_id": "0",
    })
    assert "err=" in locked.headers["location"]
    with Local() as db:
        active = db.scalar(select(WorkoutSession654).where(
            WorkoutSession654.completed_at.is_(None)
        ))
        assert db.get(WorkoutSessionTarget667, (active.id, original)).target_weight_lb == 90
    assert post(client, "/workouts/quick/finish").status_code == 303


def test_668_audited_completed_set_corrections_delete_and_copy_draft(isolated668):
    client, Local = isolated668
    with Local() as db:
        machine = fixture_equipment(db)
        db.commit()
        mid = machine.id
    assert post(client, "/workouts/quick/start").status_code == 303
    assert post(client, "/workouts/quick/sets", {
        "equipment_id": mid, "weight_lb": "95",
        "reps": "9", "set_type": "warmup",
    }).status_code == 303
    assert post(client, "/workouts/quick/finish").status_code == 303
    with Local() as db:
        entry = db.scalar(select(WorkoutSet654))
        sid, setid = entry.session_id, entry.id
    invalid = post(client, f"/workouts/sessions/{sid}/sets/{setid}/correct", {
        "action": "delete", "reason": "short", "confirm_delete": "yes",
    })
    assert invalid.status_code == 303 and "err=" in invalid.headers["location"]
    correction = post(client, f"/workouts/sessions/{sid}/sets/{setid}/correct", {
        "action": "edit", "weight_lb": "100", "reps": "10",
        "set_type": "working", "reason": "Corrected original transcription",
    })
    assert correction.status_code == 303 and "msg=" in correction.headers["location"]
    with Local() as db:
        updated = db.get(WorkoutSet654, setid)
        assert (updated.weight_lb, updated.reps) == (100, 10)
        assert db.get(WorkoutSetType667, setid) is None
        prior = db.scalar(select(WorkoutSetAudit668))
        assert '"weight_lb": 95.0' in prior.before_json
        assert '"weight_lb": 100.0' in prior.after_json
    copy = post(client, f"/workouts/sessions/{sid}/duplicate")
    assert copy.status_code == 303 and "/program" in copy.headers["location"]
    with Local() as db:
        new = db.scalar(select(WorkoutRoutine655))
        item = db.scalar(select(WorkoutRoutineItem655))
        assert new and item
        assert db.get(WorkoutRoutineTarget667, item.id).target_sets == 1
        assert db.scalar(select(func.count(WorkoutSet654.id))) == 1
    delete = post(client, f"/workouts/sessions/{sid}/sets/{setid}/correct", {
        "action": "delete", "reason": "Recorded set was a duplicate",
        "confirm_delete": "yes",
    })
    assert delete.status_code == 303 and "msg=" in delete.headers["location"]
    with Local() as db:
        assert db.get(WorkoutSet654, setid) is None
        audit = list(db.scalars(select(WorkoutSetAudit668).order_by(WorkoutSetAudit668.id)))
        assert [a.action for a in audit] == ["edit", "delete"]
        assert all(a.original_set_id == setid for a in audit)
    view = client.get(f"/workouts/sessions/{sid}")
    assert view.status_code == 200
    assert "Correction History" in view.text
    assert "Recorded set was a duplicate" in view.text


def test_668_load_semantics_and_readonly_insights(isolated668):
    client, Local = isolated668
    with Local() as db:
        m = fixture_equipment(db, "Dumbbell")
        db.commit()
        mid = m.id
    assert post(client, f"/workouts/equipment/{mid}/load-semantics", {
        "mode": "per_hand",
    }).status_code == 303
    assert "err=" in post(client, f"/workouts/equipment/{mid}/load-semantics", {
        "mode": "unsafe",
    }).headers["location"]
    with Local() as db:
        assert db.get(WorkoutLoadSemantics668, mid).mode == "per_hand"
    progress = client.get(f"/workouts/equipment/{mid}/progress")
    assert progress.status_code == 200
    assert "Per hand" in progress.text
    analytics = client.get("/workouts/insights")
    assert analytics.status_code == 200
    assert "Exact-rep recorded personal bests" in analytics.text
    with Local() as db:
        assert summary668(db)["sessions28"] == 0


def test_668_csv_roundtrip_and_duplicate_rejection(isolated668):
    client, Local = isolated668
    with Local() as db:
        m = fixture_equipment(db)
        db.commit()
        mid = m.id
    start = (datetime.now() - timedelta(days=2)).replace(hour=9, minute=0, second=0, microsecond=0)
    finish = start + timedelta(hours=1)
    text = ",".join(CSV_COLUMNS668) + "\n" + ",".join((
        "alpha", start.isoformat(timespec="seconds"), finish.isoformat(timespec="seconds"),
        str(mid), "75", "10", "6", "warmup",
        start.isoformat(timespec="seconds"),
    )) + "\n"
    with Local() as db:
        parsed = parse_csv668(text, {mid}, datetime.now())
        assert len(parsed) == 1 and parsed[0][1][0]["kind"] == "warmup"
    bad = text.replace(str(mid) + ",75,", "999999,75,")
    assert "err=" in post(client, "/workouts/data/import", {"csv_text": bad}).headers["location"]
    result = post(client, "/workouts/data/import", {"csv_text": text})
    assert result.status_code == 303 and "msg=" in result.headers["location"]
    assert "err=" in post(client, "/workouts/data/import", {"csv_text": text}).headers["location"]
    with Local() as db:
        assert db.scalar(select(func.count(WorkoutImportReceipt668.digest))) == 1
        actual = db.scalar(select(WorkoutSet654))
        assert actual and actual.weight_lb == 75
        assert db.get(WorkoutSetType667, actual.id).set_type == "warmup"
    exported = client.get("/workouts/data/export.csv")
    assert exported.status_code == 200
    assert "attachment" in exported.headers["content-disposition"]
    rows = list(csv.DictReader(StringIO(exported.text)))
    assert len(rows) == 1
    assert rows[0]["weight_lb"] == "75.0"
    assert rows[0]["set_type"] == "warmup"


def test_668_offline_replay_is_idempotent_and_rejects_stale_session(isolated668):
    client, Local = isolated668
    with Local() as db:
        m = fixture_equipment(db)
        db.commit()
        mid = m.id
    assert post(client, "/workouts/quick/start").status_code == 303
    with Local() as db:
        active = db.scalar(select(WorkoutSession654))
        sid = active.id
    token = str(uuid4())
    payload = dict(
        token=token, session_id=sid, equipment_id=mid,
        weight_lb="88", reps="10", effort="8", set_type="working",
    )
    assert post(client, "/workouts/offline/sync", {
        **payload, "token": "not-a-uuid",
    }).status_code == 400
    assert post(client, "/workouts/offline/sync", {
        **payload, "weight_lb": "-1",
    }).status_code == 400
    result = post(client, "/workouts/offline/sync", payload)
    assert result.status_code == 200 and result.json()["ok"] is True
    repeated = post(client, "/workouts/offline/sync", payload)
    assert repeated.status_code == 200 and repeated.json()["duplicate"] is True
    with Local() as db:
        assert db.scalar(select(func.count(WorkoutSet654.id))) == 1
        assert db.scalar(select(func.count(WorkoutOfflineReceipt668.token))) == 1
    assert post(client, "/workouts/quick/finish").status_code == 303
    stale = post(client, "/workouts/offline/sync", {
        **payload, "token": str(uuid4()),
    })
    assert stale.status_code == 409
    with Local() as db:
        assert db.scalar(select(func.count(WorkoutSet654.id))) == 1


def test_668_source_contract_and_additive_tables():
    source = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "from . import workout_models668" in source
    for router in ("program", "history", "csv", "offline", "insights"):
        assert f"app.include_router(workouts668_{router}.router)" in source
    from jinja2 import Environment
    for name in (
        "workout_programs668.html", "workout_data668.html",
        "workout_insights668.html", "workout_quick659.html",
        "workout_calendar664.html", "workout_routine_detail655.html",
        "workout_history654.html", "workout_progress656.html",
        "_workout_dashboard661.html",
    ):
        Environment().parse((ROOT / "app/templates" / name).read_text(encoding="utf-8"))
    import app.workout_models668 as models
    assert {
        item.__tablename__ for name, item in vars(models).items()
        if isinstance(item, type) and name.startswith("Workout") and
        hasattr(item, "__tablename__")
    } >= {
        "workout_training_days668", "workout_routine_groups668",
        "workout_session_substitutions668", "workout_set_audit668",
        "workout_load_semantics668", "workout_import_receipts668",
        "workout_offline_receipts668",
    }
