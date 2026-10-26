"""v2.3 audit trail regression tests for corrections and deletions."""
import json
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.db import SessionLocal
from app.models import ChangeAudit, Compound, DoseLog, Purchase, Vial


def test_dose_edit_and_delete_capture_full_audit():
    with TestClient(app, follow_redirects=False) as client:
        with SessionLocal() as db:
            compound = Compound(name='Audit Regression Compound', category='peptide')
            purchase = Purchase(vendor='Audit Test', purchased_on=date.today())
            db.add_all([compound, purchase]); db.flush()
            vial = Vial(compound_id=compound.id, purchase_id=purchase.id,
                        content_value=20, content_unit='mg', status='in_use')
            db.add(vial); db.commit(); vid = vial.id
        response = client.post('/doses', data={'vial_id': vid, 'amount': 5, 'unit': 'mg',
                                                'notes': 'original note', 'kind': 'dose'})
        assert response.status_code == 200
        with SessionLocal() as db:
            did = db.scalar(select(DoseLog.id).where(DoseLog.vial_id == vid).order_by(DoseLog.id.desc()))
        response = client.post(f'/doses/{did}/edit', data={'amount': 4, 'unit': 'mg',
                         'kind': 'waste', 'site': 'Abdomen lower left', 'notes': 'corrected note'})
        assert response.status_code == 303
        with SessionLocal() as db:
            audit = db.scalar(select(ChangeAudit).where(ChangeAudit.entity_type == 'dose',
                        ChangeAudit.entity_id == did, ChangeAudit.action == 'edit'))
            assert audit is not None
            before, after = json.loads(audit.before_json), json.loads(audit.after_json)
            assert before['entered_value'] == 5 and before['notes'] == 'original note'
            assert after['entered_value'] == 4 and after['notes'] == 'corrected note'
            assert before['kind'] == 'dose' and after['kind'] == 'waste'
            assert before['vial_id'] == after['vial_id'] == vid
        page = client.get(f'/doses/{did}/edit')
        assert page.status_code == 200
        assert 'Change history' in page.text and 'corrected note' in page.text
        response = client.delete(f'/doses/{did}')
        assert response.status_code == 200
        with SessionLocal() as db:
            assert db.get(DoseLog, did) is None
            deletion = db.scalar(select(ChangeAudit).where(ChangeAudit.entity_type == 'dose',
                        ChangeAudit.entity_id == did, ChangeAudit.action == 'delete'))
            assert deletion is not None
            assert json.loads(deletion.before_json)['notes'] == 'corrected note'
