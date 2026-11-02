"""Keep all sidebar pages on Tracker's shared, configured Jinja environment.

Uses tests/conftest.py's isolated SQLite database and never the live service.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("instance", ["DEV", "PROD"])
@pytest.mark.parametrize("route,heading", [
    ("/workflow-hub", "Workflow hub"),
    ("/protocol-coverage", "Protocol inventory coverage"),
])
def test_shared_renderer_preserves_instance_label(
    monkeypatch, instance, route, heading
):
    monkeypatch.setenv("TRACKER_INSTANCE", instance)
    with TestClient(app) as client:
        response = client.get(route)
    assert response.status_code == 200
    assert heading in response.text
    assert f"<title>[{instance}] " in response.text
    assert f"tracker-instance--{instance.lower()}" in response.text


def test_routers_do_not_create_independent_jinja_environments():
    # Jinja globals and filters must be installed once in app.templating.
    offenders = [
        path.name
        for path in sorted((ROOT / "app/routers").glob("*.py"))
        if "Jinja2Templates(" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, f"Independent router Jinja environments: {offenders}"
