"""Health insights dashboard smoke and query-validation tests."""
from fastapi.testclient import TestClient
from app.main import app


def test_health_insights_filters_and_empty_state():
    with TestClient(app) as client:
        response = client.get('/health-insights')
        assert response.status_code == 200
        assert 'Health insights' in response.text
        assert 'Laboratory trend' in response.text
        assert '/vitals' in response.text
        assert client.get('/health-insights?days=30&events=0').status_code == 200
        assert client.get('/health-insights?days=999&analyte=unknown').status_code == 200
        assert 'name="days"' in response.text
