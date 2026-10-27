from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models import Coa, Compound, Vial
from app.services import effective_content
from app.migrations import migrate_coa_links
from app.db import engine


def test_multiple_coas_average_and_unlink():
    with TestClient(app) as client:
        with SessionLocal() as db:
            compound = Compound(name='Multi-COA example', category='peptide')
            db.add(compound)
            db.flush()
            vial = Vial(compound_id=compound.id, content_value=10, content_unit='mg',
                        kit_ref='purchase-1-kit-1', form='lyophilized', use_coa_content=True)
            first = Coa(lab_name='Lab A', reported_content_value=9, reported_content_unit='mg')
            second = Coa(lab_name='Lab B', reported_content_value=11000, reported_content_unit='mcg')
            db.add_all([vial, first, second]); db.flush()
            vial.coa_id = first.id
            vial.linked_coas.extend([first, second])
            db.commit(); vid, c1, c2 = vial.id, first.id, second.id
        with SessionLocal() as db:
            vial = db.get(Vial, vid)
            assert len(vial.all_coas) == 2
            assert effective_content(vial) == (10000, 'mass')
        migrate_coa_links(engine)
        with SessionLocal() as db:
            assert len(db.get(Vial, vid).all_coas) == 2
        assert 'Average reported content' in client.get(f'/vials/{vid}').text
        assert client.post(f'/coas/{c1}/unlink/{vid}', follow_redirects=False).status_code == 303
        with SessionLocal() as db:
            vial = db.get(Vial, vid)
            assert [c.id for c in vial.all_coas] == [c2]
            assert effective_content(vial) == (11000, 'mass')
