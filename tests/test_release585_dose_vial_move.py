"""Release 585: correction can reassign a dose to a different same-compound vial."""
from uuid import uuid4
import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db import Base, SessionLocal, engine
from app.models import ChangeAudit, Compound, DoseLog, Vial
from app.services import vial_views


def stock():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        compound = Compound(name="Vial move " + str(uuid4()), primary_unit="mg")
        other = Compound(name="Other vial move " + str(uuid4()), primary_unit="mg")
        db.add_all([compound, other])
        db.flush()
        ids = []
        for cid, ml in ((compound.id, 1), (compound.id, 2), (other.id, 1)):
            vial = Vial(compound_id=cid, content_value=10, content_unit="mg",
                        volume_ml=ml, status="sealed")
            db.add(vial)
            db.flush()
            ids.append(vial.id)
        db.commit()
        return ids


def add_dose(client, vial_id, amount="2", unit="mg"):
    response = client.post("/doses", data={
        "vial_id": str(vial_id), "taken_at": "2026-11-12T11:30",
        "amount": amount, "unit": unit, "submission_token": str(uuid4()),
    })
    assert response.status_code == 200, response.text[:600]
    with SessionLocal() as db:
        dose = db.scalar(select(DoseLog).where(DoseLog.vial_id == vial_id)
                         .order_by(DoseLog.id.desc()))
        return dose.id


def correct(client, dose_id, vial_id, amount="2", unit="mg"):
    return client.post(f"/doses/{dose_id}/edit", data={
        "vial_id": str(vial_id), "taken_at": "2026-11-12T11:30",
        "amount": amount, "unit": unit, "kind": "dose",
    }, follow_redirects=False)


def remaining(db, *ids):
    return [vial_views(db, [db.get(Vial, vid)])[vid].remaining_base for vid in ids]


def test_vial_move_restores_source_and_consumes_destination_once():
    source, dest, other = stock()
    with TestClient(app) as client:
        did = add_dose(client, source)
        page = client.get(f"/doses/{did}/edit")
        assert page.status_code == 200
        assert 'name="vial_id"' in page.text
        assert f'value="{source}" selected' in page.text
        assert f'value="{dest}"' in page.text
        assert f'value="{other}"' not in page.text
        response = correct(client, did, dest)
        assert response.status_code == 303
        assert "err=" not in response.headers["location"]
        with SessionLocal() as db:
            dose = db.get(DoseLog, did)
            assert dose.vial_id == dest
            assert dose.amount_base == 2000
            assert remaining(db, source, dest) == [10000, 8000]
            audits = list(db.scalars(select(ChangeAudit).where(
                ChangeAudit.entity_type == "dose", ChangeAudit.entity_id == did,
                ChangeAudit.action == "edit")))
            assert len(audits) == 1
            assert json.loads(audits[0].before_json)["vial_id"] == source
            assert json.loads(audits[0].after_json)["vial_id"] == dest
        response = correct(client, did, source)
        assert response.status_code == 303
        assert "err=" not in response.headers["location"]
        with SessionLocal() as db:
            assert remaining(db, source, dest) == [8000, 10000]
            assert db.get(DoseLog, did).vial_id == source


def test_reject_other_compound_and_destination_overdraw_without_mutation():
    source, dest, other = stock()
    with TestClient(app) as client:
        did = add_dose(client, source)
        for target, amount in ((other, "2"), (dest, "11"), (999999999, "2")):
            response = correct(client, did, target, amount=amount)
            assert response.status_code == 303
            assert "err=" in response.headers["location"]
            with SessionLocal() as db:
                assert db.get(DoseLog, did).vial_id == source
                assert remaining(db, source, dest) == [8000, 10000]


def test_volume_recalculated_at_destination_concentration():
    source, dest, other = stock()
    with TestClient(app) as client:
        did = add_dose(client, source, amount="0.2", unit="mL")
        with SessionLocal() as db:
            assert db.get(DoseLog, did).amount_base == 2000
        response = correct(client, did, dest, amount="0.2", unit="mL")
        assert response.status_code == 303
        assert "err=" not in response.headers["location"]
        with SessionLocal() as db:
            assert db.get(DoseLog, did).amount_base == 1000
            assert remaining(db, source, dest) == [10000, 9000]
