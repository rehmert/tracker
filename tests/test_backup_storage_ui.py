"""Read-only backup storage signals are rendered in existing Tracker pages."""
import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import backup, config
from app.routers import backups, maintenance_review


def client(tmp_path, monkeypatch, *, with_secondary=True):
    data = tmp_path / "data"
    data.mkdir()
    with sqlite3.connect(data / "tracker.db") as conn:
        conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
    primary = tmp_path / "backup"
    primary.mkdir()
    monkeypatch.setattr(backup, "BACKUP_DIR", primary)
    monkeypatch.setattr(config, "DB_URL", f"sqlite:///{data / 'tracker.db'}")
    if with_secondary:
        secondary = tmp_path / "replica"
        secondary.mkdir()
        monkeypatch.setenv("TRACKER_BACKUP_REPLICA_DIR", str(secondary))
    else:
        monkeypatch.setenv("TRACKER_BACKUP_REPLICA_DIR", str(tmp_path / "missing"))
    app = FastAPI()
    app.include_router(backups.router)
    app.include_router(maintenance_review.router)
    return TestClient(app)


def test_backups_page_displays_free_space_and_shared_filesystem(tmp_path, monkeypatch):
    test_client = client(tmp_path, monkeypatch)
    with test_client:
        response = test_client.get("/backups")
    assert response.status_code == 200
    assert "Backup storage &amp; placement" in response.text
    assert "Primary backup storage" in response.text
    assert "Secondary local filesystem" in response.text
    assert "Same filesystem" in response.text
    assert "free" in response.text
    assert "off-site protection" in response.text


def test_maintenance_review_includes_headroom_and_placement(tmp_path, monkeypatch):
    test_client = client(tmp_path, monkeypatch)
    with test_client:
        response = test_client.get("/maintenance-review")
    assert response.status_code == 200
    assert "Backup volume headroom" in response.text
    assert "Secondary local storage placement" in response.text
    assert "Same filesystem" in response.text
    assert "needing attention" in response.text


def test_unavailable_secondary_is_presented_as_review_not_server_error(tmp_path, monkeypatch):
    test_client = client(tmp_path, monkeypatch, with_secondary=False)
    with test_client:
        response = test_client.get("/backups")
    assert response.status_code == 200
    assert "Cannot inspect secondary backup storage" in response.text
    assert "REVIEW" in response.text
