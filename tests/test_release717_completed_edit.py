"""Release 717: completed workout editing, audited removal, FK integrity, and navigation.

Uses only the disposable scoped test DB; all setup records are cleaned up.
"""
from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.main import app
from app.models import ChangeAudit
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from app.workout_models667 import WorkoutSetType667
from app.workout_models668 import WorkoutSetCorrection668


@pytest.fixture
def completed717():
    with TestClient(app) as client:
        with SessionLocal() as db:
            suffix = uuid4().hex[:12]
            first = WorkoutEquipment654(
                name="QA717 Row " + suffix, kind="selectorized", gym="QA717 Gym",
            )
            second = WorkoutEquipment654(
                name="QA717 Press " + suffix, kind="selectorized", gym="QA717 Gym",
            )
            db.add_all([first, second])
            db.flush()
            session = WorkoutSession654(
                started_at=datetime(2026, 11, 19, 10, 0),
                completed_at=datetime(2026, 11, 19, 11, 0),
            )
            db.add(session)
            db.flush()
            rows = [
                WorkoutSet654(
                    session_id=session.id, equipment_id=gear.id,
                    weight_lb=weight, reps=reps,
                    performed_at=datetime(2026, 11, 19, 10, i + 1),
                )
                for i, (gear, weight, reps) in enumerate(
                    ((first, 100, 10), (first, 100, 10), (first, 100, 10),
                     (second, 50, 8))
                )
            ]
            db.add_all(rows)
            db.flush()
            ids = dict(
                sid=session.id, first=first.id, second=second.id,
                rows=[row.id for row in rows],
            )
            db.commit()
        try:
            yield client, ids
        finally:
            with SessionLocal() as db:
                row_ids = ids["rows"]
                db.execute(delete(ChangeAudit).where(
                    ChangeAudit.entity_type == "workout_set",
                    ChangeAudit.entity_id.in_(row_ids),
                ))
                db.execute(delete(WorkoutSetCorrection668).where(
                    WorkoutSetCorrection668.set_id.in_(row_ids),
                ))
                db.execute(delete(WorkoutSetType667).where(
                    WorkoutSetType667.set_id.in_(row_ids),
                ))
                db.execute(delete(WorkoutSet654).where(
                    WorkoutSet654.session_id == ids["sid"],
                ))
                db.execute(delete(WorkoutSession654).where(
                    WorkoutSession654.id == ids["sid"],
                ))
                db.execute(delete(WorkoutEquipment654).where(
                    WorkoutEquipment654.id.in_([ids["first"], ids["second"]]),
                ))
                db.commit()


def remove717(client, sid, set_id, **data):
    return client.post(
        f"/workouts/sessions/{sid}/sets/{set_id}/remove",
        data=data, follow_redirects=False,
    )


def test_717_completed_session_navigation_and_exact_set_selection(completed717):
    client, ids = completed717
    sid = ids["sid"]
    recent = client.get("/workouts")
    assert recent.status_code == 200
    assert f'/workouts/sessions/{sid}/correct' in recent.text
    assert "Edit Workout" in recent.text
    review = client.get(f"/workouts/sessions/{sid}/review")
    assert review.status_code == 200
    assert "4" in review.text
    assert "Edit Workout" in review.text
    history = client.get(f"/workouts/sessions/{sid}")
    assert "Edit Completed Workout" in history.text
    page = client.get(f"/workouts/sessions/{sid}/correct")
    assert page.status_code == 200
    assert "Edit Completed Workout" in page.text
    assert page.text.count('type="checkbox" name="confirm_remove"') == 4
    assert f'workout717-set-{ids["rows"][2]}' in page.text
    assert "Set 3" in page.text
    assert "Extra set logged" in page.text


def test_717_remove_one_extra_set_updates_review_and_preserves_audit(completed717):
    client, ids = completed717
    sid, set_id = ids["sid"], ids["rows"][2]
    before = client.get(f"/workouts/sessions/{sid}/review")
    assert "4" in before.text
    assert remove717(client, sid, set_id, reason="Extra set logged",
                     confirm_remove="yes").status_code == 303
    with SessionLocal() as db:
        assert db.get(WorkoutSet654, set_id) is None
        saved = list(db.scalars(
            select(ChangeAudit).where(
                ChangeAudit.entity_type == "workout_set",
                ChangeAudit.entity_id == set_id,
                ChangeAudit.action == "remove_completed",
            )
        ))
        assert len(saved) == 1
        old = json.loads(saved[0].before_json)
        assert old["session_id"] == sid
        assert old["equipment_id"] == ids["first"]
        assert old["weight_lb"] == 100 and old["reps"] == 10
        assert old["reason"] == "Extra set logged"
        assert old["correction_history"] == []
        assert db.get(WorkoutSession654, sid).completed_at is not None
        assert len(list(db.scalars(select(WorkoutSet654).where(
            WorkoutSet654.session_id == sid
        )))) == 3
    review = client.get(f"/workouts/sessions/{sid}/review")
    assert review.status_code == 200
    assert '3' in review.text
    assert '2' in review.text
    page = client.get(f"/workouts/sessions/{sid}/correct")
    assert "<strong>3</strong> recorded sets remaining" in page.text
    assert f"Set #{set_id} removed" in page.text
    assert "Extra set logged" in page.text
    again = remove717(client, sid, set_id, reason="Extra set logged",
                      confirm_remove="yes")
    assert again.status_code == 404


def test_717_stale_cross_session_and_unconfirmed_posts_do_not_mutate(completed717):
    client, ids = completed717
    sid, set_id = ids["sid"], ids["rows"][0]
    for values in (
        {"reason": "Extra set logged"},
        {"confirm_remove": "yes", "reason": ""},
        {"confirm_remove": "yes", "reason": "x"},
        {"confirm_remove": "no", "reason": "Extra set"},
    ):
        attempt = remove717(client, sid, set_id, **values)
        assert attempt.status_code == 303
        assert "err=" in attempt.headers["location"]
    assert remove717(client, sid + 99999, set_id,
                     reason="Extra set", confirm_remove="yes").status_code == 404
    assert remove717(client, sid, 999999999,
                     reason="Extra set", confirm_remove="yes").status_code == 404
    with SessionLocal() as db:
        assert db.get(WorkoutSet654, set_id)
        assert not list(db.scalars(select(ChangeAudit).where(
            ChangeAudit.entity_type == "workout_set",
            ChangeAudit.entity_id == set_id,
        )))


def test_717_active_session_cannot_remove_historical_set(completed717):
    client, ids = completed717
    with SessionLocal() as db:
        session = db.get(WorkoutSession654, ids["sid"])
        end = session.completed_at
        session.completed_at = None
        db.commit()
    try:
        response = remove717(client, ids["sid"], ids["rows"][0],
                             reason="Extra set", confirm_remove="yes")
        assert response.status_code == 303 and "err=" in response.headers["location"]
        with SessionLocal() as db:
            assert db.get(WorkoutSet654, ids["rows"][0]) is not None
    finally:
        with SessionLocal() as db:
            db.get(WorkoutSession654, ids["sid"]).completed_at = end
            db.commit()


def test_717_removal_preserves_prior_audited_corrections_in_snapshot(completed717):
    client, ids = completed717
    sid, set_id = ids["sid"], ids["rows"][1]
    with SessionLocal() as db:
        row = db.get(WorkoutSet654, set_id)
        db.add(WorkoutSetCorrection668(
            set_id=set_id, old_weight_lb=100, new_weight_lb=90,
            old_reps=10, new_reps=8, old_effort=None, new_effort=None,
            old_type="working", new_type="warmup",
            reason="Earlier correction",
        ))
        db.add(WorkoutSetType667(set_id=set_id, set_type="warmup"))
        row.weight_lb = 90
        row.reps = 8
        db.commit()
    attempt = remove717(client, sid, set_id,
                        reason="Duplicated set", confirm_remove="yes")
    assert attempt.status_code == 303
    with SessionLocal() as db:
        assert db.get(WorkoutSet654, set_id) is None
        assert db.get(WorkoutSetType667, set_id) is None
        assert db.scalars(select(WorkoutSetCorrection668).where(
            WorkoutSetCorrection668.set_id == set_id,
        )).first() is None
        audit = db.scalar(select(ChangeAudit).where(
            ChangeAudit.entity_type == "workout_set",
            ChangeAudit.entity_id == set_id,
            ChangeAudit.action == "remove_completed",
        ))
        old = json.loads(audit.before_json)
        assert old["set_type"] == "warmup"
        assert old["weight_lb"] == 90 and old["reps"] == 8
        assert len(old["correction_history"]) == 1
        assert old["correction_history"][0]["reason"] == "Earlier correction"
        assert old["correction_history"][0]["old_weight_lb"] == 100
    page = client.get(f"/workouts/sessions/{sid}/correct")
    assert "Earlier corrections (1)" in page.text
    assert "Earlier correction" in page.text
