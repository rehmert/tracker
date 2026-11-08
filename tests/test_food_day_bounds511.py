"""Extremely early/late Food Journal days must not crash date navigation."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.parametrize("day", ["0001-01-01", "9999-12-31"])
def test_511_food_day_navigation_rejects_unrepresentable_neighbors(day):
    with TestClient(app, follow_redirects=False) as client:
        response = client.get("/food", params={"day": day})
    assert response.status_code == 422
    assert "supported navigation range" in response.text
