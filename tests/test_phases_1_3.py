"""Regression checks for the new data protection and UX flows."""
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db import Base
from app.main import app
from app.models import (Compound, Purchase, Supply, SupplyUsage, InventoryAdjustment,
                        Protocol, ProtocolItem, ProtocolRevision, PreparationEvent,
                        PreparationSupply, Vial, DoseLog)
from app.routers.protocols import _revision


def test_revision_snapshots_are_immutable():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        p=Protocol(name='Original',horizon_weeks=12,is_active=False)
        db.add(p);db.flush();_revision(db,p);db.flush()
        p.name='Updated';_revision(db,p);db.commit()
        versions=list(db.scalars(select(ProtocolRevision).order_by(ProtocolRevision.revision)))
        assert len(versions)==2
        assert 'Original' in versions[0].snapshot_json
        assert 'Updated' in versions[1].snapshot_json
        assert versions[0].revision==1 and versions[1].revision==2


def test_manual_supply_credit_allows_correction():
    import inspect
    from app.manual_supplies import selections
    assert 'credits' in inspect.signature(selections).parameters


def test_new_routes_render():
    with TestClient(app) as client:
        for path in ('/quick-entry','/reconciliation','/consumption','/data-integrity','/release-info'):
            response=client.get(path)
            assert response.status_code==200,(path,response.text[:200])


def test_reconciliation_audit():
    from app.db import SessionLocal
    with TestClient(app) as client:
        with SessionLocal() as db:
            purchase=Purchase(vendor='Test vendor',purchased_on=__import__('datetime').date.today())
            db.add(purchase);db.flush()
            supply=Supply(purchase_id=purchase.id,name='Test syringes',kind='syringe',purchased_qty=10,remaining_qty=10,unit_price_cents=10)
            db.add(supply);db.commit();sid=supply.id
        r=client.post(f'/reconciliation/{sid}',data={'counted':'8','reason':'Physical count','expected':'10','confirmed':'yes'},follow_redirects=False)
        assert r.status_code in (302,303)
        with SessionLocal() as db:
            assert db.get(Supply,sid).remaining_qty==8
            record=db.scalars(select(InventoryAdjustment).where(InventoryAdjustment.supply_id==sid)).one()
            assert record.previous_qty==10 and record.counted_qty==8
