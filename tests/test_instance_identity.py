"""Instance identity is local configuration, not an alternate code branch."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app


@pytest.mark.parametrize("value, expected, style, accessible", [
    ("DEV", "DEV", "dev", "Development"),
    ("prod", "PROD", "prod", "Production"),
    (" prod ", "PROD", "prod", "Production"),
])
def test_instance_badge_and_browser_title(monkeypatch, value, expected, style, accessible):
    monkeypatch.setenv("TRACKER_INSTANCE", value)
    assert config.instance_label() == expected
    with TestClient(app) as client:
        response = client.get("/compounds")
    assert response.status_code == 200
    assert f"<title>[{expected}] Compounds · Tracker</title>" in response.text
    assert response.text.count(f'class="tracker-instance tracker-instance--{style}"') == 2
    assert response.text.count(f'aria-label="{accessible} instance"') == 2
    assert "/static/css/tracker-instance.css" in response.text
    assert 'href="/"' in response.text


@pytest.mark.parametrize("value", ["", "STAGING", "some<script>", "DEV-OTHER"])
def test_unrecognized_or_empty_instance_cannot_be_misrepresented(monkeypatch, value):
    monkeypatch.setenv("TRACKER_INSTANCE", value)
    assert config.instance_label() == ""
    with TestClient(app) as client:
        response = client.get("/compounds")
    assert response.status_code == 200
    assert "<title>Compounds · Tracker</title>" in response.text
    assert 'class="tracker-instance ' not in response.text
    assert "some&lt;script&gt;" not in response.text


def test_missing_instance_uses_normal_brand(monkeypatch):
    monkeypatch.delenv("TRACKER_INSTANCE", raising=False)
    assert config.instance_label() == ""
    with TestClient(app) as client:
        response = client.get("/compounds")
    assert response.status_code == 200
    assert "<title>Compounds · Tracker</title>" in response.text
    assert '<a class="brand" href="/">Tracker</a>' in response.text


def test_stylesheet_and_environment_example():
    root = Path(__file__).resolve().parents[1]
    css = (root / "app/static/css/tracker-instance.css").read_text()
    example = (root / ".env.example").read_text()
    assert ".tracker-instance--dev" in css
    assert ".tracker-instance--prod" in css
    assert "TRACKER_INSTANCE=" in example
