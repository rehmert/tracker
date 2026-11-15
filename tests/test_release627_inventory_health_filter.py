"""Release 627 regression: finding levels must not override the URL severity filter.

Synthetic read-only findings are injected into the isolated test process.
No live database records are created or modified.
"""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import reliability


@pytest.mark.parametrize("requested,selected,shown,hidden", [
    ("all", "all", True, True),
    ("error", "error", True, False),
    ("warning", "warning", False, True),
    ("not-valid", "all", True, True),
])
def test_inventory_health_severity_filter_ignores_finding_level(
    monkeypatch, requested, selected, shown, hidden,
):
    # Deliberately order the records error -> warning. The legacy bug
    # accidentally overwrote the requested filter with "Warning".
    findings = [
        SimpleNamespace(
            code="negative", category="supply", record_id=62701,
            message="QA627 error finding", observed=None, expected=None,
        ),
        SimpleNamespace(
            code="other", category="vial", record_id=62702,
            message="QA627 warning finding", observed=None, expected=None,
        ),
    ]
    monkeypatch.setattr(reliability, "inspect_inventory", lambda db: findings)
    with TestClient(app) as client:
        response = client.get("/inventory-health", params={"severity": requested})
    assert response.status_code == 200
    assert f'<option value="{selected}" selected>' in response.text
    assert ("QA627 error finding" in response.text) is shown
    assert ("QA627 warning finding" in response.text) is hidden
    assert "Severity filtering does not change stock" in response.text
