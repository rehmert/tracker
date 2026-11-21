"""Release 719: scoped workout deletion and ten-at-a-time dashboard history."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal
from app.main import app
from app.models import ChangeAudit
from app.workout_dashboard661 import workout_dashboard661
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from app.workout_models655 import (
    WorkoutRoutine655, WorkoutRoutineItem655, WorkoutSessionRoutine655,
)
from app.workout_models667 import WorkoutSessionTarget667, WorkoutSetType667
from app.workout_models668 import WorkoutSetCorrection668, WorkoutOfflineReceipt668


@pytest.fixture
def sessions719():
    """Disposable QA fixture with an accidental active and a fully linked completed session."""
    with TestClient(app) as client:
        with SessionLocal() as db:
            suffix = uuid4().hex[:12]
            machine = WorkoutEquipment654(
                name="QA719 Press " + suffix, gym="QA719", kind="selectorized",
            )
            routine = WorkoutRoutine655(name="QA719 Routine " + suffix)
            db.add_all([machine, routine])
            db.flush()
            db.add(WorkoutRoutineItem655(
                routine_id=routine.id, equipment_id=machine.id, position=0,
            ))
            started = datetime.now().replace(microsecond=0) - timedelta(minutes=20)
            accidental = WorkoutSession654(started_at=started)
            completed = WorkoutSession654(
                started_at=started - timedelta(days=1),
                completed_at=started - timedelta(days=1) + timedelta(minutes=45),
            )
            db.add_all([accidental, completed])
            db.flush()
            db.add(WorkoutSessionRoutine655(
                session_id=completed.id, routine_id=routine.id,
            ))
            db.add(WorkoutSessionTarget667(
                session_id=completed.id, equipment_id=machine.id,
                target_sets=2, target_reps=10, target_weight_lb=100,
                rest_seconds=90, setup_note="Seat 4",
            ))
            sets = [
                WorkoutSet654(
                    session_id=completed.id, equipment_id=machine.id,
                    weight_lb=100, reps=10,
                    performed_at=completed.started_at + timedelta(minutes=i),
                ) for i in (1, 2)
            ]
            db.add_all(sets)
            db.flush()
            db.add(WorkoutSetType667(set_id=sets[0].id, set_type="warmup"))
            db.add(WorkoutSetCorrection668(
                set_id=sets[1].id,
                old_weight_lb=95, new_weight_lb=100,
                old_reps=8, new_reps=10,
                old_effort=None, new_effort=None,
                old_type="working", new_type="working",
                reason="Earlier correction",
            ))
            offline = WorkoutOfflineReceipt668(
                client_key=str(uuid4()), payload_sha256="a" * 64,
                session_id=completed.id, set_id=sets[1].id,
            )
            db.add(offline)
            db.flush()
            db.commit()
            result = dict(
                offline_id=offline.id, offline_key=offline.client_key,
                empty_id=accidental.id, empty_started=accidental.started_at.isoformat(),
                sid=completed.id, started=completed.started_at.isoformat(),
                completed_at=completed.completed_at,
                set_ids=[set_.id for set_ in sets],
                machine=machine.id, routine=routine.id,
            )
        try:
            yield client, result
        finally:
            with SessionLocal() as db:
                sids = [result["empty_id"], result["sid"]]
                ids = result["set_ids"]
                db.execute(delete(WorkoutOfflineReceipt668).where(
                    WorkoutOfflineReceipt668.session_id.in_(sids)))
                db.execute(delete(WorkoutSetCorrection668).where(
                    WorkoutSetCorrection668.set_id.in_(ids)))
                db.execute(delete(WorkoutSetType667).where(
                    WorkoutSetType667.set_id.in_(ids)))
                db.execute(delete(WorkoutSet654).where(
                    WorkoutSet654.session_id.in_(sids)))
                db.execute(delete(WorkoutSessionTarget667).where(
                    WorkoutSessionTarget667.session_id.in_(sids)))
                db.execute(delete(WorkoutSessionRoutine655).where(
                    WorkoutSessionRoutine655.session_id.in_(sids)))
                db.execute(delete(WorkoutSession654).where(
                    WorkoutSession654.id.in_(sids)))
                db.execute(delete(WorkoutRoutineItem655).where(
                    WorkoutRoutineItem655.routine_id == result["routine"]))
                db.execute(delete(WorkoutRoutine655).where(
                    WorkoutRoutine655.id == result["routine"]))
                db.execute(delete(WorkoutEquipment654).where(
                    WorkoutEquipment654.id == result["machine"]))
                db.execute(delete(ChangeAudit).where(
                    ChangeAudit.entity_type == "workout_session",
                    ChangeAudit.entity_id.in_(sids)))
                db.execute(delete(ChangeAudit).where(
                    ChangeAudit.entity_type == "workout_offline_action",
                    ChangeAudit.entity_id == result["offline_id"]))
                db.commit()


def delete_workout719(client, sid, started, **fields):
    return client.post(
        f"/workouts/sessions/{sid}/delete",
        data=dict(expected_started_at=started, **fields),
        follow_redirects=False,
    )


def test_719_empty_active_workout_can_be_deleted_with_audit(sessions719):
    client, item = sessions719
    sid = item["empty_id"]
    response = client.get("/workouts")
    assert response.status_code == 200
    assert f'workout719-delete-{sid}' in response.text
    assert 'workout720-delete-form' in response.text
    assert '>Delete</button>' in response.text
    assert 'onsubmit="return confirm(' in response.text
    history = client.get(f"/workouts/sessions/{sid}")
    assert history.status_code == 200
    assert f'/workouts/sessions/{sid}/delete' in history.text

    deleted = delete_workout719(
        client, sid, item["empty_started"],
        confirm_delete="yes", reason="Started by mistake",
    )
    assert deleted.status_code == 303
    assert deleted.headers["location"].startswith("/workouts")
    with SessionLocal() as db:
        assert db.get(WorkoutSession654, sid) is None
        audit = db.scalar(select(ChangeAudit).where(
            ChangeAudit.entity_type == "workout_session",
            ChangeAudit.entity_id == sid, ChangeAudit.action == "delete",
        ))
        assert audit is not None
        snapshot = json.loads(audit.before_json)
        assert snapshot["sets"] == []
        assert snapshot["completed_at"] is None
        assert snapshot["reason"] == "Started by mistake"
        assert db.get(WorkoutSession654, item["sid"]) is not None
    assert delete_workout719(
        client, sid, item["empty_started"],
        confirm_delete="yes", reason="Started by mistake",
    ).status_code == 404


def test_719_completed_delete_preserves_dependent_history_and_routine(sessions719):
    client, item = sessions719
    sid = item["sid"]
    review = client.get(f"/workouts/sessions/{sid}/review")
    assert review.status_code == 200
    assert f'/workouts/sessions/{sid}/delete' in review.text

    result = delete_workout719(
        client, sid, item["started"],
        confirm_delete="yes", reason="Duplicate workout",
    )
    assert result.status_code == 303 and "msg=" in result.headers["location"]
    with SessionLocal() as db:
        assert db.get(WorkoutSession654, sid) is None
        assert db.get(WorkoutRoutine655, item["routine"]) is not None
        assert db.get(WorkoutEquipment654, item["machine"]) is not None
        for set_id in item["set_ids"]:
            assert db.get(WorkoutSet654, set_id) is None
            assert db.get(WorkoutSetType667, set_id) is None
        assert db.get(WorkoutSessionRoutine655, sid) is None
        assert not list(db.scalars(select(WorkoutSessionTarget667).where(
            WorkoutSessionTarget667.session_id == sid)))
        assert not list(db.scalars(select(WorkoutOfflineReceipt668).where(
            WorkoutOfflineReceipt668.session_id == sid)))
        assert not list(db.scalars(select(WorkoutSetCorrection668).where(
            WorkoutSetCorrection668.set_id.in_(item["set_ids"]))))
        audit = db.scalar(select(ChangeAudit).where(
            ChangeAudit.entity_type == "workout_session",
            ChangeAudit.entity_id == sid, ChangeAudit.action == "delete",
        ))
        assert audit is not None
        old = json.loads(audit.before_json)
        assert old["completed_at"] == item["completed_at"].isoformat()
        assert len(old["sets"]) == 2
        assert len(old["corrections"]) == 1
        assert old["corrections"][0]["reason"] == "Earlier correction"
        assert len(old["frozen_targets"]) == 1
        assert len(old["offline_receipts"]) == 1
        tombstone = db.scalar(select(ChangeAudit).where(
            ChangeAudit.entity_type == "workout_offline_action",
            ChangeAudit.entity_id == item["offline_id"],
            ChangeAudit.action == "session_deleted",
        ))
        assert tombstone is not None
        assert json.loads(tombstone.before_json)["client_key"] == item["offline_key"]
        assert old["routine_id"] == item["routine"]
        assert old["reason"] == "Duplicate workout"


def test_719_missing_confirmation_stale_form_and_wrong_session_are_safe(sessions719):
    client, item = sessions719
    sid = item["empty_id"]
    for fields in (
        dict(reason="Started by mistake"),
        dict(confirm_delete="no", reason="Started by mistake"),
        dict(confirm_delete="yes", reason="x"),
    ):
        response = delete_workout719(
            client, sid, item["empty_started"], **fields)
        assert response.status_code == 303
        assert "err=" in response.headers["location"]
    stale = delete_workout719(
        client, sid, item["started"],
        confirm_delete="yes", reason="Started by mistake",
    )
    assert stale.status_code == 303 and "err=" in stale.headers["location"]
    assert delete_workout719(
        client, sid + 100000, item["empty_started"],
        confirm_delete="yes", reason="Started by mistake",
    ).status_code == 404
    with SessionLocal() as db:
        assert db.get(WorkoutSession654, sid) is not None
        assert db.get(WorkoutSession654, item["sid"]) is not None
        assert not list(db.scalars(select(ChangeAudit).where(
            ChangeAudit.entity_type == "workout_session",
            ChangeAudit.entity_id == sid, ChangeAudit.action == "delete",
        )))


def test_719_recent_workouts_page_by_tens_including_empty_and_active(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "workout719.sqlite"))
    try:
        Base.metadata.create_all(engine, tables=[
            WorkoutEquipment654.__table__, WorkoutSession654.__table__,
            WorkoutSet654.__table__,
        ])
        with Session(engine) as db:
            today = date(2026, 11, 20)
            machine = WorkoutEquipment654(
                name="719 QA Press", gym="QA719", kind="selectorized")
            db.add(machine)
            db.flush()
            inserted = []
            for i in range(23):
                started = datetime(2026, 11, 20, 9) - timedelta(days=i)
                session = WorkoutSession654(
                    started_at=started,
                    completed_at=(started + timedelta(minutes=45) if i % 3 else None),
                )
                db.add(session)
                db.flush()
                inserted.append(session.id)
                if i % 4:
                    db.add(WorkoutSet654(
                        session_id=session.id, equipment_id=machine.id,
                        weight_lb=85, reps=8, performed_at=started,
                    ))
            db.commit()
            first = workout_dashboard661(db, today)
            assert first["limit"] == 10
            assert first["recent_total"] == 23
            assert first["recent_pages"] == 3
            assert first["recent_page"] == 1
            assert first["recent_expanded"] is False
            assert [r.session_id for r in first["recent"]] == inserted[:10]
            assert first["recent"][0].sets == 0
            second = workout_dashboard661(db, today, page=2, expanded=True)
            assert [r.session_id for r in second["recent"]] == inserted[10:20]
            assert second["recent_first"] == 11 and second["recent_last"] == 20
            assert second["recent_expanded"] is True
            third = workout_dashboard661(db, today, page=3, expanded=True)
            assert [r.session_id for r in third["recent"]] == inserted[20:]
            assert third["recent_first"] == 21 and third["recent_last"] == 23
            last = workout_dashboard661(db, today, page=1000, expanded=True)
            assert last["recent_page"] == 3
            assert [r.session_id for r in last["recent"]] == inserted[20:]
    finally:
        engine.dispose()


def test_719_dashboard_markup_defaults_closed_and_page_links_open(sessions719):
    client, item = sessions719
    home = client.get("/")
    assert home.status_code == 200
    assert '<details class="tracker-workout-recent661"' in home.text
    assert 'id="tracker-workout-recent661"' in home.text
    assert "10 per page" in home.text
    first = home.text.split('<details class="tracker-workout-recent661"', 1)[1]
    assert 'open' not in first.split('>', 1)[0]
    page = client.get("/?workout_page=1")
    assert page.status_code == 200
    current = page.text.split('<details class="tracker-workout-recent661"', 1)[1]
    assert "open" in current.split(">", 1)[0]
    assert f'/workouts/sessions/{item["empty_id"]}' in page.text
    assert client.get("/?workout_page=0").status_code == 422



def test_719_deleted_offline_client_key_cannot_be_replayed(sessions719):
    client, item = sessions719
    assert delete_workout719(
        client, item["sid"], item["started"],
        confirm_delete="yes", reason="Delete duplicated workout",
    ).status_code == 303
    # Even if an old SQLite INTEGER PRIMARY KEY gets reused in the future,
    # a deleted offline UUID must not log a new set.
    rejected = client.post("/workouts/quick/offline-sync", data={
        "session_id": item["sid"],
        "equipment_id": item["machine"],
        "client_key": item["offline_key"],
        "weight_lb": "100", "reps": "10", "effort": "",
        "performed_at": datetime.now().astimezone().isoformat(),
        "set_type": "working",
    })
    assert rejected.status_code == 409
