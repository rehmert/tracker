from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

ROOT = Path(__file__).resolve().parents[1]

def test_803_pinned_today_and_dashboard():
    with TestClient(app) as client:
        for route in ('/', '/mobile'):
            response = client.get(route)
            assert response.status_code == 200
            pinned = response.text.split('class="nav-links nav-pinned"', 1)[1].split('</ul>', 1)[0]
            assert 'href="/mobile"' in pinned and 'href="/"' in pinned
            assert pinned.count('aria-current="page"') == 1
            assert 'Search Records' in response.text
            assert 'Go to page' in response.text
