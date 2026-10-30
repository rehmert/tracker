"""Stage 24: verify duplicate purchase submission is serialized and idempotent."""
from datetime import date
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.main import app
from app.db import SessionLocal, Base, engine
from app.models import Purchase, InventorySubmission


def test_sequential_duplicate_purchase_is_recorded_once():
    Base.metadata.create_all(bind=engine)
    token=str(uuid4())
    payload={'vendor':'Stage24-'+str(uuid4()),'purchased_on':'2026-10-30','submission_token':token}
    with TestClient(app) as client:
        first=client.post('/purchases',data=payload,follow_redirects=False)
        second=client.post('/purchases',data=payload,follow_redirects=False)
    assert first.status_code==303 and second.status_code==303
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Purchase).where(Purchase.vendor==payload['vendor']))==1
        assert db.get(InventorySubmission,token) is not None
