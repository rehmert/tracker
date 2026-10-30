"""HTTP + SQLite regression checks for single-vial and blended inventory."""
from uuid import uuid4
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.main import app
from app.db import SessionLocal, Base, engine
from app.models import Compound, Vial, DoseLog, Blend, BlendDose, ChangeAudit, InventorySubmission
from app.services import vial_views


def seed_vials(prefix, count=2):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        ids=[]
        for i in range(count):
            c=Compound(name=f'{prefix}-{i}',primary_unit='mg')
            db.add(c); db.flush()
            v=Vial(compound_id=c.id, content_value=10,content_unit='mg',volume_ml=1,status='sealed')
            db.add(v);db.flush();ids.append(v.id)
        db.commit()
        return ids


def test_dose_replay_conflict_and_rejected_overdraw():
    ids=seed_vials('Stage17Dose-'+str(uuid4()),1)
    token=str(uuid4())
    payload={'vial_id':str(ids[0]),'taken_at':'2026-10-30T12:00','amount':'2','unit':'mg','kind':'dose','submission_token':token}
    with TestClient(app) as client:
        assert client.post('/doses',data=payload).status_code==200
        assert 'already recorded' in client.post('/doses',data=payload).text
        assert 'reused submission' in client.post('/doses',data=dict(payload,amount='3')).text
        assert 'exceeds remaining' in client.post('/doses',data=dict(payload,amount='9',submission_token=str(uuid4()))).text
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(DoseLog).where(DoseLog.vial_id==ids[0]))==1
        assert vial_views(db,[db.get(Vial,ids[0])])[ids[0]].remaining_base==8000
        assert db.get(InventorySubmission,token).operation=='dose_create'


def test_blend_create_draw_replay_audit_and_form_token():
    ids=seed_vials('Stage17Blend-'+str(uuid4()))
    token=str(uuid4())
    payload={'label':'Stage17-'+str(uuid4()),'diluent_ml':'0','capacity_ml':'3',
             'source_id':[str(i) for i in ids], 'transfer_amount':['5','5'],
             'transfer_unit':['mg','mg'],'target_amount':['1','1'],
             'target_unit':['mg','mg'],'submission_token':token}
    with TestClient(app) as client:
        first=client.post('/blends',data=payload,follow_redirects=False)
        assert first.status_code==303 and '/blends/' in first.headers['location']
        assert 'already' in client.post('/blends',data=payload,follow_redirects=False).headers['location']
        assert 'err=' in client.post('/blends',data=dict(payload,label='Changed'),follow_redirects=False).headers['location']
        with SessionLocal() as db:
            b=db.scalar(select(Blend).where(Blend.label==payload['label']))
            assert b is not None
            bid=b.id
            assert db.scalar(select(func.count()).select_from(Blend).where(Blend.label==payload['label']))==1
            assert all(vial_views(db,[db.get(Vial,i)])[i].remaining_base==5000 for i in ids)
            assert db.scalar(select(func.count()).select_from(ChangeAudit).where(ChangeAudit.entity_type=='blend',ChangeAudit.entity_id==bid,ChangeAudit.action=='create'))==1
        detail=client.get(f'/blends/{bid}')
        assert 'name="submission_token" value="' in detail.text
        drawtoken=str(uuid4())
        draw={'volume_ml':'0.2','taken_at':'2026-10-30T12:00','kind':'dose','submission_token':drawtoken}
        assert 'msg=' in client.post(f'/blends/{bid}/doses',data=draw,follow_redirects=False).headers['location']
        assert 'already' in client.post(f'/blends/{bid}/doses',data=draw,follow_redirects=False).headers['location']
        assert 'err=' in client.post(f'/blends/{bid}/doses',data=dict(draw,volume_ml='0.3'),follow_redirects=False).headers['location']
        assert 'err=' in client.post(f'/blends/{bid}/doses',data=dict(draw,volume_ml='5',submission_token=str(uuid4())),follow_redirects=False).headers['location']
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(BlendDose).where(BlendDose.blend_id==bid))==1
        assert db.scalar(select(func.count()).select_from(ChangeAudit).where(ChangeAudit.entity_type=='blend',ChangeAudit.entity_id==bid,ChangeAudit.action=='draw'))==1
        assert db.get(InventorySubmission,drawtoken).operation=='blend_draw'
