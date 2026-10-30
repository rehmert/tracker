"""Integration regressions: durable replay, conflicts, atomic audit, rollback, SQLite contention."""
from datetime import date
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from app.db import Base
from app.models import Purchase, Supply, SupplyUsage, InventorySubmission, InventoryAdjustment, ChangeAudit
from app.routers.purchases import create_purchase, add_purchase_supply, add_bac_water_vials
from app.routers.supplies import use
from app.routers.reliability import reconcile
from app.inventory_lock import reserve_inventory_write

@pytest.fixture
def db_engine(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'inventory.sqlite'}", connect_args={'timeout': 0.1})
    Base.metadata.create_all(engine)
    monkeypatch.setattr('app.services.flash_redirect', lambda url, **kw: (url, kw))
    yield engine
    engine.dispose()

def seed(engine):
    with Session(engine) as db:
        p = Purchase(vendor='Test', purchased_on=date(2026, 10, 30))
        db.add(p); db.flush()
        s = Supply(purchase_id=p.id, name='Syringe', kind='needle', purchased_qty=10, remaining_qty=10)
        db.add(s); db.commit()
        return p.id, s.id

def totals(engine, sid):
    with Session(engine) as db:
        return (db.get(Supply,sid).remaining_qty,
                db.scalar(select(func.count()).select_from(SupplyUsage).where(SupplyUsage.supply_id==sid)),
                db.scalar(select(func.count()).select_from(InventorySubmission)))

def test_supply_use_replay_conflict_and_stock(db_engine):
    _, sid = seed(db_engine)
    token=str(uuid4())
    with Session(db_engine) as db:
        assert 'msg' in use(sid, 3, token, db)[1]
    assert totals(db_engine,sid)==(7,1,1)
    with Session(db_engine) as db:
        assert 'already' in use(sid,3,token,db)[1]['msg']
    assert totals(db_engine,sid)==(7,1,1)
    with Session(db_engine) as db:
        assert 'err' in use(sid,2,token,db)[1]
    assert totals(db_engine,sid)==(7,1,1)
    with Session(db_engine) as db:
        assert 'err' in use(sid,9,str(uuid4()),db)[1]
    assert totals(db_engine,sid)==(7,1,1)

def test_reconciliation_replay_stale_and_audit(db_engine):
    _, sid=seed(db_engine)
    token=str(uuid4())
    with Session(db_engine) as db:
        assert 'msg' in reconcile(sid,8,'Counted',10,'yes',token,db)[1]
    with Session(db_engine) as db:
        assert 'already' in reconcile(sid,8,'Counted',10,'yes',token,db)[1]['msg']
        assert 'err' in reconcile(sid,6,'Counted',10,'yes',str(uuid4()),db)[1]
    with Session(db_engine) as db:
        assert db.get(Supply,sid).remaining_qty==8
        assert db.scalar(select(func.count()).select_from(InventoryAdjustment))==1
        assert db.scalar(select(func.count()).select_from(ChangeAudit).where(ChangeAudit.action=='reconcile'))==1
        assert db.scalar(select(func.count()).select_from(InventorySubmission))==1

def test_purchase_replay_and_audit(db_engine):
    token=str(uuid4())
    with Session(db_engine) as db:
        assert 'msg' in create_purchase('Vendor','','','','','','',token,db)[1]
    with Session(db_engine) as db:
        assert 'already' in create_purchase('Vendor','','','','','','',token,db)[1]['msg']
        assert 'err' in create_purchase('Other','','','','','','',token,db)[1]
        assert db.scalar(select(func.count()).select_from(Purchase))==1
        assert db.scalar(select(func.count()).select_from(ChangeAudit).where(ChangeAudit.entity_type=='purchase'))==1

def test_purchased_supply_and_bac_replay(db_engine):
    pid,_=seed(db_engine)
    t1,t2=str(uuid4()),str(uuid4())
    with Session(db_engine) as db:
        assert 'msg' in add_purchase_supply(pid,'Needle','needle',1,'0','','',db,'2','50','10.00','box',t1)[1]
    with Session(db_engine) as db:
        assert 'already' in add_purchase_supply(pid,'Needle','needle',1,'0','','',db,'2','50','10.00','box',t1)[1]['msg']
        assert 'msg' in add_bac_water_vials(pid,2,10.0,'BAC','','','',t2,db)[1]
    with Session(db_engine) as db:
        assert 'already' in add_bac_water_vials(pid,2,10.0,'BAC','','','',t2,db)[1]['msg']
        assert db.scalar(select(func.count()).select_from(Supply))==3
        assert db.scalar(select(func.count()).select_from(InventorySubmission))==2

def test_rollback_removes_token_and_mutation(db_engine):
    _,sid=seed(db_engine)
    from app.idempotency import check,record
    token=str(uuid4())
    with Session(db_engine) as db:
        assert reserve_inventory_write(db)
        state,digest=check(db,token,'supply_use',{'sid':sid,'quantity':4})
        assert state=='new'
        db.get(Supply,sid).remaining_qty-=4
        record(db,token,'supply_use',digest)
        db.flush()
        db.rollback()
    assert totals(db_engine,sid)==(10,0,0)

def test_write_reservation_blocks_second_writer(db_engine):
    _,sid=seed(db_engine)
    with Session(db_engine) as first, Session(db_engine) as second:
        assert reserve_inventory_write(first)
        assert not reserve_inventory_write(second)
        first.get(Supply,sid).remaining_qty=9
        first.commit()
        assert reserve_inventory_write(second)
        assert second.get(Supply,sid).remaining_qty==9
        second.rollback()
