from fastapi.testclient import TestClient
from app.main import app


def test_search_short_query_returns_empty():
    with TestClient(app) as client:
        r = client.get('/search', params={'q': 'a'})
        assert r.status_code == 200
        assert r.json() == {'results': []}


def test_search_returns_local_results_structure():
    with TestClient(app) as client:
        r = client.get('/search', params={'q': 'unlikely-record-name-xyz'})
        assert r.status_code == 200
        assert 'results' in r.json()


def test_command_palette_markup():
    with TestClient(app) as client:
        r = client.get('/')
        assert r.status_code == 200
        assert 'command-overlay' in r.text
        assert 'command-open' in r.text
