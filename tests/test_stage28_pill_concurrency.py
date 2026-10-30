"""Regression coverage for the legacy pill-use route's atomic stock updates."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.main import app
from app.db import SessionLocal
from app.models import Purchase, Supply, SupplyUsage, InventorySubmission


def _seed():
    with SessionLocal() as db:
        p = Purchase(vendor='Stage28-' + str(uuid4()), purchased_on=date.today())
        db.add(p)
        db.flush()
        s = Supply(purchase_id=p.id, name='Stage28 pills', kind='pill',
                   purchased_qty=10, remaining_qty=10, unit_price_cents=1)
        db.add(s)
        db.commit()
        return s.id


def _race(sid, quantities, tokens):
    barrier = Barrier(2)
    def submit(i):
        with TestClient(app) as client:
            barrier.wait(timeout=10)
            return client.post(f'/supplies/{sid}/dose', data={
                'quantity': str(quantities[i]), 'submission_token': tokens[i],
            }).text
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(submit, i) for i in range(2)]
        return [f.result(timeout=25) for f in futures]


def test_simultaneous_pill_overdraw_is_serialized():
    with TestClient(app):
        sid = _seed()
        tokens = [str(uuid4()), str(uuid4())]
        _race(sid, [8, 8], tokens)
        with SessionLocal() as db:
            assert db.get(Supply, sid).remaining_qty == 2
            assert db.scalar(select(func.count()).select_from(SupplyUsage).where(SupplyUsage.supply_id == sid)) == 1
            assert sum(db.get(InventorySubmission, t) is not None for t in tokens) == 1


def test_simultaneous_pill_replay_is_idempotent():
    with TestClient(app):
        sid = _seed()
        token = str(uuid4())
        _race(sid, [3, 3], [token, token])
        with SessionLocal() as db:
            assert db.get(Supply, sid).remaining_qty == 7
            assert db.scalar(select(func.count()).select_from(SupplyUsage).where(SupplyUsage.supply_id == sid)) == 1
            assert db.get(InventorySubmission, token) is not None
