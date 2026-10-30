"""Stage 23 read-only integrity checks; isolated by tests/conftest.py."""
from datetime import date
from uuid import uuid4
from sqlalchemy import select, func
from app.db import Base, engine, SessionLocal
from app.models import Purchase, Supply, SupplyUsage, InventoryAdjustment
from app.inventory_consistency import inspect_inventory


def make_supply(purchased=10, remaining=10):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        p = Purchase(vendor='Stage23-'+str(uuid4()), purchased_on=date(2026,10,30))
        db.add(p); db.flush()
        s = Supply(purchase_id=p.id, name='Stage23-'+str(uuid4()), kind='needle',
                   purchased_qty=purchased, remaining_qty=remaining)
        db.add(s); db.commit()
        return s.id


def test_clean_supply_and_read_only():
    sid = make_supply()
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(SupplyUsage))
        assert not [f for f in inspect_inventory(db) if f.category=='supply' and f.record_id==sid]
        assert db.scalar(select(func.count()).select_from(SupplyUsage)) == before
        assert not db.dirty and not db.new and not db.deleted


def test_usage_and_reconciliation_balance():
    sid = make_supply(10, 6)
    with SessionLocal() as db:
        db.add(SupplyUsage(supply_id=sid, amount=3))
        db.add(InventoryAdjustment(supply_id=sid, previous_qty=7, counted_qty=6, reason='count'))
        db.commit()
        assert not [f for f in inspect_inventory(db) if f.category=='supply' and f.record_id==sid]


def test_detects_mismatch_without_mutation():
    sid = make_supply(10, 3)
    with SessionLocal() as db:
        findings = [f for f in inspect_inventory(db) if f.record_id==sid and f.category=='supply']
        assert len(findings)==1 and findings[0].code=='ledger_mismatch'
        assert findings[0].expected==10 and findings[0].observed==3
        assert db.get(Supply,sid).remaining_qty==3


def test_detects_negative_balance():
    sid = make_supply(10, -2)
    with SessionLocal() as db:
        codes = {f.code for f in inspect_inventory(db) if f.record_id==sid and f.category=='supply'}
        assert {'negative','ledger_mismatch'} <= codes
