"""Stage 24 read-only inventory health UI regression tests."""
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.db import Base, engine, SessionLocal
from app.models import Purchase, Supply
from datetime import date


def test_inventory_health_reports_mismatch_without_mutating_stock():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        p = Purchase(vendor='stage24-'+str(uuid4()), purchased_on=date(2026,10,30))
        db.add(p); db.flush()
        s = Supply(purchase_id=p.id, name='stage24-'+str(uuid4()), kind='needle', purchased_qty=10, remaining_qty=8)
        db.add(s); db.commit(); sid=s.id
    with TestClient(app) as client:
        response=client.get('/inventory-health')
    assert response.status_code==200
    assert 'ledger_mismatch' in response.text
    assert 'No stock is changed' in response.text
    with SessionLocal() as db:
        assert db.get(Supply,sid).remaining_qty==8


def test_inventory_health_does_not_create_inventory_audit_events():
    from sqlalchemy import func
    from app.models import ChangeAudit, InventoryAdjustment
    with SessionLocal() as db:
        audits_before=db.scalar(select(func.count()).select_from(ChangeAudit))
        adjustments_before=db.scalar(select(func.count()).select_from(InventoryAdjustment))
    with TestClient(app) as client:
        response=client.get('/inventory-health')
    assert response.status_code==200
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ChangeAudit))==audits_before
        assert db.scalar(select(func.count()).select_from(InventoryAdjustment))==adjustments_before
