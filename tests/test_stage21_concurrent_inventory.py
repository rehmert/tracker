"""Stage 21: simultaneous blend and purchase requests on isolated SQLite."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.db import SessionLocal
from app.models import Blend, BlendDose, ChangeAudit, InventorySubmission, Purchase, Vial
from app.services import vial_views
from tests.test_stage17_dose_blend_integrity import seed_vials


def race(path, payloads):
    barrier = Barrier(len(payloads))
    def submit(data):
        with TestClient(app) as client:
            barrier.wait(timeout=15)
            response = client.post(path, data=data, follow_redirects=False)
            return response.status_code, response.headers.get('location', '')
    with ThreadPoolExecutor(max_workers=len(payloads)) as pool:
        return [f.result(timeout=35) for f in [pool.submit(submit, p) for p in payloads]]


def blend_payload(ids, token, label, transfer='8'):
    return {'label':label, 'diluent_ml':'0', 'capacity_ml':'3',
            'source_id':[str(i) for i in ids], 'transfer_amount':[transfer]*len(ids),
            'transfer_unit':['mg']*len(ids), 'target_amount':['1']*len(ids),
            'target_unit':['mg']*len(ids), 'submission_token':token}


def test_simultaneous_blend_creation_cannot_overdraw_sources():
    ids = seed_vials('Stage21Blend-'+str(uuid4()))
    tokens = [str(uuid4()),str(uuid4())]
    results = race('/blends',[blend_payload(ids,t,'Stage21-'+t) for t in tokens])
    assert all(code==303 for code,_ in results)
    with SessionLocal() as db:
        created = list(db.scalars(select(Blend).where(Blend.label.in_(['Stage21-'+t for t in tokens]))))
        assert len(created)==1
        assert all(vial_views(db,[db.get(Vial,i)])[i].remaining_base==2000 for i in ids)
        assert sum(db.get(InventorySubmission,t) is not None for t in tokens)==1
        assert db.scalar(select(func.count()).select_from(ChangeAudit).where(ChangeAudit.entity_type=='blend',ChangeAudit.entity_id==created[0].id,ChangeAudit.action=='create'))==1
    assert any('err=' in location for _,location in results)


def test_simultaneous_identical_blend_token_creates_once():
    ids=seed_vials('Stage21BlendReplay-'+str(uuid4()))
    token=str(uuid4()); label='Stage21Replay-'+str(uuid4())
    payload=blend_payload(ids,token,label,'3')
    results=race('/blends',[payload,payload])
    assert all(code==303 for code,_ in results)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Blend).where(Blend.label==label))==1
        assert all(vial_views(db,[db.get(Vial,i)])[i].remaining_base==7000 for i in ids)
        assert db.get(InventorySubmission,token) is not None
    assert any('already' in loc or 'busy' in loc.lower() for _,loc in results)


def make_blend():
    ids=seed_vials('Stage21Draw-'+str(uuid4()))
    token=str(uuid4()); label='Stage21Draw-'+str(uuid4())
    with TestClient(app) as client:
        r=client.post('/blends',data=blend_payload(ids,token,label,'5'),follow_redirects=False)
        assert r.status_code==303, r.text
    with SessionLocal() as db:
        return db.scalar(select(Blend.id).where(Blend.label==label))


def test_simultaneous_blend_draws_cannot_overdraw():
    bid=make_blend(); tokens=[str(uuid4()),str(uuid4())]
    payloads=[{'volume_ml':'0.7','taken_at':'2026-10-30T12:00','kind':'dose','submission_token':t} for t in tokens]
    results=race(f'/blends/{bid}/doses',payloads)
    assert all(code==303 for code,_ in results)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(BlendDose).where(BlendDose.blend_id==bid))==1
        assert sum(db.get(InventorySubmission,t) is not None for t in tokens)==1
        assert db.scalar(select(func.count()).select_from(ChangeAudit).where(ChangeAudit.entity_type=='blend',ChangeAudit.entity_id==bid,ChangeAudit.action=='draw'))==1
    assert any('err=' in loc for _,loc in results)


def test_simultaneous_identical_blend_draw_is_idempotent():
    bid=make_blend(); token=str(uuid4())
    payload={'volume_ml':'0.2','taken_at':'2026-10-30T12:00','kind':'dose','submission_token':token}
    results=race(f'/blends/{bid}/doses',[payload,payload])
    assert all(code==303 for code,_ in results)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(BlendDose).where(BlendDose.blend_id==bid))==1
        assert db.get(InventorySubmission,token) is not None
    assert any('already' in loc or 'busy' in loc.lower() for _,loc in results)


def test_simultaneous_purchase_header_submission_creates_once():
    token=str(uuid4()); vendor='Stage21Vendor-'+str(uuid4())
    payload={'vendor':vendor,'purchased_on':'2026-10-30','submission_token':token}
    results=race('/purchases',[payload,payload])
    assert all(code==303 for code,_ in results)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Purchase).where(Purchase.vendor==vendor))==1
        assert db.get(InventorySubmission,token) is not None
    assert any('already' in loc or 'busy' in loc.lower() for _,loc in results)
