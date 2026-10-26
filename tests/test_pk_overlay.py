"""Regression tests for normalized multi-compound exposure overlay."""
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models import Compound


def test_overlay_validates_selection_and_normalizes():
    with TestClient(app) as client:
        with SessionLocal() as db:
            a = Compound(name='Tirzepatide Overlay Test', category='peptide')
            b = Compound(name='Semaglutide Overlay Test', category='peptide')
            db.add_all([a, b]); db.commit()
            ids = f'{a.id},{b.id}'
        response = client.get('/pk/overlay', params={'compound_ids': ids, 'days_back': 3, 'days_forward': 3})
        assert response.status_code == 200
        body = response.json()
        assert len(body['series']) == 2
        assert len(body['at']) > 1
        assert all(len(item['values_percent']) == len(body['at']) for item in body['series'])
        assert all(0 <= v <= 100 for item in body['series'] for v in item['values_percent'])
        assert client.get('/pk/overlay', params={'compound_ids': 'oops'}).status_code == 400
        assert client.get('/pk/overlay', params={'compound_ids': ''}).status_code == 400
        assert client.get('/pk/overlay', params={'compound_ids': ids, 'days_back': 400}).status_code == 400
        assert client.get('/pk/overlay', params={'compound_ids': f'{ids},999999999'}).status_code == 400
        assert client.get('/pk/overlay', params={'compound_ids': ','.join(['1','2','3','4','5'])}).status_code == 400
