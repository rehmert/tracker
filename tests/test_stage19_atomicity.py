"""Stage 19: HTTP/SQLite transaction fault injection and write contention."""
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func, event
from sqlalchemy.orm import Session
from app.main import app
from app.db import SessionLocal, engine
from app.models import DoseLog, ChangeAudit, Vial, InventorySubmission
from app.services import vial_views
from tests.test_stage17_dose_blend_integrity import seed_vials


def _snapshot(vid):
    with SessionLocal() as db:
        return (db.scalar(select(func.count()).select_from(DoseLog).where(DoseLog.vial_id == vid)),
                vial_views(db, [db.get(Vial, vid)])[vid].remaining_base)


def test_dose_create_failure_rolls_back_inventory_and_replay_token():
    vid = seed_vials('Stage19Create-' + str(uuid4()), 1)[0]
    token = str(uuid4())
    before = _snapshot(vid)
    def fail_flush(session, flush_context, instances):
        if any(isinstance(obj, InventorySubmission) and obj.token == token for obj in session.new):
            raise RuntimeError('injected submission write failure')
    event.listen(Session, 'before_flush', fail_flush)
    try:
        with TestClient(app) as client:
            with pytest.raises(RuntimeError, match='injected submission'):
                client.post('/doses', data={'vial_id': str(vid), 'taken_at': '2026-10-30T12:00',
                                            'amount': '2', 'unit': 'mg', 'submission_token': token})
    finally:
        event.remove(Session, 'before_flush', fail_flush)
    assert _snapshot(vid) == before
    with SessionLocal() as db:
        assert db.get(InventorySubmission, token) is None


def test_dose_edit_failure_rolls_back_record_and_audit():
    vid = seed_vials('Stage19Edit-' + str(uuid4()), 1)[0]
    with TestClient(app) as client:
        assert client.post('/doses', data={'vial_id': str(vid), 'taken_at': '2026-10-30T12:00',
                                           'amount': '2', 'unit': 'mg'}).status_code == 200
        with SessionLocal() as db:
            did = db.scalar(select(DoseLog.id).where(DoseLog.vial_id == vid))
        before = _snapshot(vid)
        def fail_flush(session, flush_context, instances):
            if any(isinstance(obj, ChangeAudit) and obj.entity_type == 'dose' and obj.entity_id == did and obj.action == 'edit' for obj in session.new):
                raise RuntimeError('injected audit write failure')
        event.listen(Session, 'before_flush', fail_flush)
        try:
            with pytest.raises(RuntimeError, match='injected audit'):
                client.post(f'/doses/{did}/edit', data={'taken_at': '2026-10-30T12:00', 'amount': '3', 'unit': 'mg'})
        finally:
            event.remove(Session, 'before_flush', fail_flush)
    assert _snapshot(vid) == before
    with SessionLocal() as db:
        assert db.get(DoseLog, did).amount_base == 2000
        assert db.scalar(select(func.count()).select_from(ChangeAudit).where(ChangeAudit.entity_type == 'dose', ChangeAudit.entity_id == did)) == 0


def test_dose_delete_failure_rolls_back_record_and_audit():
    vid = seed_vials('Stage19Delete-' + str(uuid4()), 1)[0]
    with TestClient(app) as client:
        assert client.post('/doses', data={'vial_id': str(vid), 'taken_at': '2026-10-30T12:00',
                                           'amount': '2', 'unit': 'mg'}).status_code == 200
        with SessionLocal() as db:
            did = db.scalar(select(DoseLog.id).where(DoseLog.vial_id == vid))
        before = _snapshot(vid)
        def fail_flush(session, flush_context, instances):
            if any(isinstance(obj, ChangeAudit) and obj.entity_type == 'dose' and obj.entity_id == did and obj.action == 'delete' for obj in session.new):
                raise RuntimeError('injected audit write failure')
        event.listen(Session, 'before_flush', fail_flush)
        try:
            with pytest.raises(RuntimeError, match='injected audit'):
                client.delete(f'/doses/{did}')
        finally:
            event.remove(Session, 'before_flush', fail_flush)
    assert _snapshot(vid) == before
    with SessionLocal() as db:
        assert db.get(DoseLog, did) is not None
        assert db.scalar(select(func.count()).select_from(ChangeAudit).where(ChangeAudit.entity_type == 'dose', ChangeAudit.entity_id == did)) == 0


def test_locked_writer_rejects_dose_edit_and_delete_without_mutation():
    vid = seed_vials('Stage19Lock-' + str(uuid4()), 1)[0]
    with TestClient(app) as client:
        assert client.post('/doses', data={'vial_id': str(vid), 'taken_at': '2026-10-30T12:00',
                                           'amount': '2', 'unit': 'mg'}).status_code == 200
        with SessionLocal() as db:
            did = db.scalar(select(DoseLog.id).where(DoseLog.vial_id == vid))
        before = _snapshot(vid)
        with engine.connect() as blocker:
            blocker.exec_driver_sql('BEGIN IMMEDIATE')
            try:
                assert client.delete(f'/doses/{did}').status_code == 409
                assert client.post(f'/doses/{did}/edit', data={'taken_at': '2026-10-30T12:00', 'amount': '3', 'unit': 'mg'}).status_code == 409
            finally:
                blocker.rollback()
    assert _snapshot(vid) == before
