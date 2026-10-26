from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models import Coa, Vial


def test_coa_manager_pages_and_metadata_edit():
    client = TestClient(app)
    assert client.get('/coas').status_code == 200
    assert 'Add COA' in client.get('/coas').text
    assert client.get('/coas/new').status_code == 200
    with SessionLocal() as db:
        coa = Coa(lab_name='Before', stored_name='metadata-test-manager')
        db.add(coa)
        db.commit()
        cid = coa.id
    assert client.get(f'/coas/{cid}').status_code == 200
    response = client.post(f'/coas/{cid}/edit', data={'lab_name':'After', 'purity_pct':'98.5', 'reported_content':'5', 'reported_unit':'mg'}, follow_redirects=False)
    assert response.status_code == 303
    with SessionLocal() as db:
        assert db.get(Coa, cid).lab_name == 'After'
        assert db.get(Coa, cid).purity_pct == 98.5
    assert client.post(f'/coas/{cid}/edit', data={'purity_pct':'101'}, follow_redirects=False).headers['location'].find('err=') >= 0
    with SessionLocal() as db:
        assert db.get(Coa, cid).purity_pct == 98.5
    assert client.post(f'/coas/{cid}/delete', follow_redirects=False).status_code == 303
    with SessionLocal() as db:
        assert db.get(Coa, cid) is None


def test_coa_unknown_ids():
    client = TestClient(app)
    assert client.get('/coas/99999999').status_code == 404
    assert client.post('/coas/99999999/edit', data={}).status_code == 404
