"""Stage 22: concurrent purchase inventory, supply usage, and reconciliation.

Runs under tests/conftest.py isolated temporary SQLite database.
"""
from uuid import uuid4
from datetime import date
from sqlalchemy import select, func
from app.db import SessionLocal, Base, engine
from app.models import Purchase, Supply, Vial, Compound, InventorySubmission, InventoryAdjustment, ChangeAudit, SupplyUsage
from tests.test_stage21_concurrent_inventory import race


def purchase():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        p = Purchase(vendor='Stage22-'+str(uuid4()), purchased_on=date(2026,10,30))
        db.add(p); db.commit(); return p.id


def supply(pid, name, quantity=10):
    with SessionLocal() as db:
        s=Supply(purchase_id=pid,name=name,kind='needle',purchased_qty=quantity,remaining_qty=quantity)
        db.add(s); db.commit(); return s.id


def test_concurrent_purchased_vials_same_token():
    pid=purchase(); token=str(uuid4())
    with SessionLocal() as db:
        c=Compound(name='Stage22-'+str(uuid4()),primary_unit='mg'); db.add(c); db.commit(); cid=c.id
    payload={'compound_id':str(cid),'form':'lyophilized','quantity':'2','content_value':'10',
             'content_unit':'mg','unit_price':'0','submission_token':token}
    result=race(f'/purchases/{pid}/vials',[payload,payload])
    assert all(code==303 for code,_ in result)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Vial).where(Vial.purchase_id==pid))==2
        assert db.get(InventorySubmission,token) is not None
    assert any('already' in loc or 'busy' in loc.lower() for _,loc in result)


def test_concurrent_bac_water_same_token():
    pid=purchase(); token=str(uuid4()); name='Stage22BAC-'+str(uuid4())
    payload={'vial_count':'2','ml_per_vial':'10','name':name,'submission_token':token}
    result=race(f'/purchases/{pid}/bac-water',[payload,payload])
    assert all(code==303 for code,_ in result)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Supply).where(Supply.purchase_id==pid,Supply.name==name))==1
        assert db.get(InventorySubmission,token) is not None
    assert any('already' in loc or 'busy' in loc.lower() for _,loc in result)


def test_concurrent_purchased_supplies_same_token():
    pid=purchase(); token=str(uuid4()); name='Stage22Needle-'+str(uuid4())
    payload={'name':name,'kind':'needle','quantity':'10','unit_price':'0','submission_token':token}
    result=race(f'/purchases/{pid}/supplies',[payload,payload])
    assert all(code==303 for code,_ in result)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Supply).where(Supply.purchase_id==pid,Supply.name==name))==1
        assert db.get(InventorySubmission,token) is not None
    assert any('already' in loc or 'busy' in loc.lower() for _,loc in result)


def test_concurrent_supply_usage_cannot_overdraw():
    pid=purchase(); sid=supply(pid,'Stage22Usage-'+str(uuid4()))
    tokens=[str(uuid4()),str(uuid4())]
    result=race(f'/supplies/{sid}/use',[{'quantity':'7','submission_token':t} for t in tokens])
    assert all(code==303 for code,_ in result)
    with SessionLocal() as db:
        assert db.get(Supply,sid).remaining_qty==3
        assert db.scalar(select(func.count()).select_from(SupplyUsage).where(SupplyUsage.supply_id==sid))==1
        assert sum(db.get(InventorySubmission,t) is not None for t in tokens)==1
    assert any('err=' in loc for _,loc in result)


def test_concurrent_reconciliation_rejects_stale_expected_stock():
    pid=purchase(); sid=supply(pid,'Stage22Reconcile-'+str(uuid4()))
    tokens=[str(uuid4()),str(uuid4())]
    payloads=[{'counted':str(count),'expected':'10','reason':'Physical count',
               'confirmed':'yes','submission_token':token} for count,token in zip((8,6),tokens)]
    result=race(f'/reconciliation/{sid}',payloads)
    assert all(code==303 for code,_ in result)
    with SessionLocal() as db:
        assert db.get(Supply,sid).remaining_qty in (8,6)
        assert db.scalar(select(func.count()).select_from(InventoryAdjustment).where(InventoryAdjustment.supply_id==sid))==1
        assert db.scalar(select(func.count()).select_from(ChangeAudit).where(ChangeAudit.entity_type=='supply',ChangeAudit.entity_id==sid,ChangeAudit.action=='reconcile'))==1
        assert sum(db.get(InventorySubmission,t) is not None for t in tokens)==1
    assert any('err=' in loc for _,loc in result)
