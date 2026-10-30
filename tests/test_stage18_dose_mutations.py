"""Regression checks for locked dose correction and deletion."""
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.main import app
from app.db import SessionLocal
from app.models import DoseLog, ChangeAudit, Vial
from app.services import vial_views
from tests.test_stage17_dose_blend_integrity import seed_vials

def test_edit_then_delete_restores_vial_and_audits():
    vid = seed_vials("Stage18-"+str(uuid4()), 1)[0]
    with TestClient(app) as client:
        response = client.post("/doses", data={"vial_id": str(vid), "taken_at": "2026-10-30T12:00", "amount": "2", "unit": "mg", "submission_token": str(uuid4())})
        assert response.status_code == 200
        with SessionLocal() as db:
            did = db.scalar(select(DoseLog.id).where(DoseLog.vial_id == vid))
        response = client.post(f"/doses/{did}/edit", data={"taken_at": "2026-10-30T12:00", "amount": "3", "unit": "mg"}, follow_redirects=False)
        assert response.status_code == 303
        with SessionLocal() as db:
            assert db.get(DoseLog, did).amount_base == 3000
            assert vial_views(db,[db.get(Vial,vid)])[vid].remaining_base == 7000
        assert client.delete(f"/doses/{did}").status_code == 200
        with SessionLocal() as db:
            assert db.get(DoseLog,did) is None
            assert vial_views(db,[db.get(Vial,vid)])[vid].remaining_base == 10000
            assert db.scalar(select(func.count()).select_from(ChangeAudit).where(ChangeAudit.entity_type=="dose",ChangeAudit.entity_id==did)) == 2

def test_rejected_edit_keeps_original_record():
    vid = seed_vials("Stage18-"+str(uuid4()), 1)[0]
    with TestClient(app) as client:
        assert client.post("/doses", data={"vial_id":str(vid),"taken_at":"2026-10-30T12:00","amount":"2","unit":"mg"}).status_code == 200
        with SessionLocal() as db:
            did=db.scalar(select(DoseLog.id).where(DoseLog.vial_id==vid))
        response=client.post(f"/doses/{did}/edit",data={"taken_at":"2026-10-30T12:00","amount":"11","unit":"mg"},follow_redirects=False)
        assert response.status_code==303 and "err=" in response.headers["location"]
        with SessionLocal() as db:
            assert db.get(DoseLog,did).amount_base==2000
            assert vial_views(db,[db.get(Vial,vid)])[vid].remaining_base==8000
