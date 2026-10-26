from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db import Base
from app.models import Purchase, Supply, SupplyUsage, Vial, DoseLog, Compound
from app.routers import purchases
from fastapi import HTTPException
import pytest

@pytest.fixture
def db(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(purchases.services, 'flash_redirect', lambda url, **kw: (url, kw))
    with Session(engine) as session:
        yield session
    engine.dispose()


def purchase(db):
    p = Purchase(vendor='Vendor', purchased_on=date(2026, 10, 26))
    db.add(p); db.flush()
    return p


def test_edit_pill_preserves_used_inventory(db):
    p = purchase(db)
    s = Supply(purchase_id=p.id, name='Pills', kind='pill', purchased_qty=50,
               remaining_qty=42, unit_price_cents=100)
    db.add(s); db.flush()
    db.add(SupplyUsage(supply_id=s.id, amount=8)); db.commit()
    url, msg = purchases.edit_purchase_supply(p.id, s.id, 'Pills new', 'pill', 60., '1.50', '', 'updated', db)
    db.refresh(s)
    assert 'msg' in msg and s.remaining_qty == 52 and s.purchased_qty == 60
    assert s.unit_price_cents == 150 and s.name == 'Pills new'
    assert 'err' in purchases.edit_purchase_supply(p.id, s.id, 'Pills', 'pill', 4., '1', '', '', db)[1]
    assert 'err' in purchases.delete_purchase_supply(p.id, s.id, db)[1]
    assert db.get(Supply, s.id) is not None


def test_supply_can_delete_when_unused(db):
    p = purchase(db)
    s = Supply(purchase_id=p.id, name='BAC', kind='bac_water', purchased_qty=30,
               remaining_qty=30, unit_price_cents=40)
    db.add(s); db.commit()
    sid = s.id
    assert 'msg' in purchases.delete_purchase_supply(p.id, sid, db)[1]
    assert db.get(Supply, sid) is None


def test_wrong_purchase_cannot_edit_or_delete(db):
    p = purchase(db)
    other = Purchase(vendor='Other', purchased_on=date(2026, 10, 26))
    db.add(other); db.flush()
    s = Supply(purchase_id=p.id, name='BAC', kind='bac_water', purchased_qty=5, remaining_qty=5)
    db.add(s); db.commit()
    with pytest.raises(HTTPException):
        purchases.delete_purchase_supply(other.id, s.id, db)
    with pytest.raises(HTTPException):
        purchases.edit_purchase_supply(other.id, s.id, 'BAC', 'bac_water', 5, '0', '', '', db)


def test_vial_delete_blocked_if_dosed(db):
    p = purchase(db)
    c = Compound(name='Example compound')
    db.add(c); db.flush()
    v = Vial(compound_id=c.id, purchase_id=p.id, content_value=10, content_unit='mg')
    db.add(v); db.flush()
    from datetime import datetime
    db.add(DoseLog(vial_id=v.id, taken_at=datetime(2026, 10, 26), entered_value=1,
                   entered_unit='mg', amount_base=1000, kind='dose'))
    db.commit()
    assert 'err' in purchases.delete_purchase_vial(p.id, v.id, db)[1]
    assert db.get(Vial, v.id) is not None
