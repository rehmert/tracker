from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.db import SessionLocal
from app.models import Compound, Vial, ChangeAudit


def test_bulk_vials_selective_update_and_validation():
    with TestClient(app) as client:
        with SessionLocal() as db:
            compound = Compound(name='Bulk vial test')
            db.add(compound)
            db.flush()
            v1 = Vial(compound_id=compound.id, content_value=10, content_unit='mg', status='sealed', lot='old')
            v2 = Vial(compound_id=compound.id, content_value=10, content_unit='mg', status='sealed', lot='old')
            db.add_all([v1, v2]); db.commit(); ids = (v1.id, v2.id)
        resp = client.post('/vials/bulk', data={'vial_ids':str(ids[0]), 'mode_lot':'set','value_lot':'new','mode_expires_on':'set','value_expires_on':'2027-01-01'}, follow_redirects=False)
        assert resp.status_code == 303
        with SessionLocal() as db:
            assert db.get(Vial,ids[0]).lot == 'new'
            assert db.get(Vial,ids[1]).lot == 'old'
            assert db.get(Vial,ids[0]).expires_on.isoformat() == '2027-01-01'
            assert db.scalar(select(ChangeAudit).where(ChangeAudit.entity_type=='vial',ChangeAudit.entity_id==ids[0],ChangeAudit.action=='bulk_update')) is not None
        resp = client.post('/vials/bulk', data={'vial_ids':[str(i) for i in ids], 'mode_status':'set','value_status':'invalid'}, follow_redirects=False)
        assert 'err=' in resp.headers['location']
        with SessionLocal() as db:
            assert all(db.get(Vial,i).status=='sealed' for i in ids)
