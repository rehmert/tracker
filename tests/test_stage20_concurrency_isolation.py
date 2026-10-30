"""Stage 20: isolated database and concurrent inventory requests."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
from pathlib import Path
import os
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.main import app
from app.config import DATA_DIR, DB_PATH
from app.db import SessionLocal
from app.models import DoseLog, Vial, InventorySubmission
from app.services import vial_views
from tests.test_stage17_dose_blend_integrity import seed_vials


def test_database_is_automatically_isolated():
    assert Path(DATA_DIR).resolve() == Path(os.environ["TRACKER_DATA_DIR"]).resolve()
    assert Path(DB_PATH).resolve().parent == Path(DATA_DIR).resolve()
    assert Path(DATA_DIR).name.startswith('tracker-pytest-isolated-')
    assert os.environ['TRACKER_DATA_DIR'] == str(DATA_DIR)


def test_simultaneous_overdraw_does_not_overspend_vial():
    vid = seed_vials('Stage20Race-' + str(uuid4()), 1)[0]
    barrier = Barrier(2)
    tokens = [str(uuid4()), str(uuid4())]

    def submit(token):
        with TestClient(app) as client:
            barrier.wait(timeout=10)
            return client.post('/doses', data={
                'vial_id': str(vid), 'taken_at': '2026-10-30T12:00',
                'amount': '8', 'unit': 'mg', 'submission_token': token,
            }).text

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(submit, token) for token in tokens]
        bodies = [f.result(timeout=25) for f in futures]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(DoseLog).where(DoseLog.vial_id == vid)) == 1
        assert vial_views(db, [db.get(Vial, vid)])[vid].remaining_base == 2000
        assert sum(db.get(InventorySubmission, token) is not None for token in tokens) == 1
    assert any('exceeds remaining' in body.lower() or 'busy' in body.lower() or 'locked' in body.lower() for body in bodies)


def test_simultaneous_identical_token_creates_one_dose():
    vid = seed_vials('Stage20Replay-' + str(uuid4()), 1)[0]
    barrier = Barrier(2)
    token = str(uuid4())

    def submit():
        with TestClient(app) as client:
            barrier.wait(timeout=10)
            return client.post('/doses', data={
                'vial_id': str(vid), 'taken_at': '2026-10-30T12:00',
                'amount': '2', 'unit': 'mg', 'submission_token': token,
            }).text

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(submit) for _ in range(2)]
        bodies = [f.result(timeout=25) for f in futures]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(DoseLog).where(DoseLog.vial_id == vid)) == 1
        assert vial_views(db, [db.get(Vial, vid)])[vid].remaining_base == 8000
        assert db.get(InventorySubmission, token) is not None
    assert any('already recorded' in body.lower() or 'busy' in body.lower() or 'locked' in body.lower() for body in bodies)
