"""Stage 31 compound management regression tests (isolated by conftest)."""
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.db import Base, engine
Base.metadata.create_all(bind=engine)
from app.models import Compound, Vial


def _compound(name, unit='mg'):
    with SessionLocal() as db:
        c = Compound(name=name, category='peptide', primary_unit=unit, notes='original')
        db.add(c)
        db.commit()
        return c.id


def test_compound_edit_and_search_preserves_identity():
    suffix = uuid4().hex[:8]
    a, b = f'Stage31-alpha-{suffix}', f'Stage31-beta-{suffix}'
    cid = _compound(a)
    _compound(b)
    with TestClient(app) as client:
        page = client.get('/compounds', params={'q': a, 'sort': 'name', 'direction': 'desc'})
        assert page.status_code == 200
        assert a in page.text and b not in page.text
        response = client.post(f'/compounds/{cid}/edit', data={'name': a + '-edited', 'category': 'peptide', 'primary_unit': 'mg', 'notes': 'updated'}, follow_redirects=False)
        assert response.status_code in (302, 303)
    with SessionLocal() as db:
        c = db.get(Compound, cid)
        assert c.name == a + '-edited' and c.notes == 'updated'


def test_compound_edit_rejects_duplicate_and_unit_change_with_vial():
    suffix = uuid4().hex[:8]
    a, b = f'Stage31-one-{suffix}', f'Stage31-two-{suffix}'
    cid = _compound(a)
    _compound(b)
    with TestClient(app) as client:
        client.post(f'/compounds/{cid}/edit', data={'name': b, 'category': 'peptide', 'primary_unit': 'mg', 'notes': 'bad'})
    with SessionLocal() as db:
        assert db.get(Compound, cid).name == a
        db.add(Vial(compound_id=cid, content_value=10, content_unit='mg', status='sealed'))
        db.commit()
    with TestClient(app) as client:
        client.post(f'/compounds/{cid}/edit', data={'name': a, 'category': 'peptide', 'primary_unit': 'IU', 'notes': 'bad'})
    with SessionLocal() as db:
        assert db.get(Compound, cid).primary_unit == 'mg'


def test_compound_sort_allowlist_and_category_filter():
    suffix = uuid4().hex[:8]
    name = f'Stage31-search-{suffix}'
    _compound(name)
    with TestClient(app) as client:
        response = client.get('/compounds', params={'q': name, 'category_filter': 'peptide', 'sort': 'not-a-column', 'direction': 'invalid'})
        assert response.status_code == 200 and name in response.text
        response = client.get('/compounds', params={'q': name, 'category_filter': 'other'})
        assert '0 compounds shown.' in response.text
