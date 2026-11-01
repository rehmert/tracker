"""Read-only maintenance checks use Tracker's actual archive location."""
import sqlite3
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import backup, config
from app.routers.maintenance_review import router


def _client(tmp_path, monkeypatch, with_backup=False, missing_db=False):
    dbfile = tmp_path / "tracker.db"
    if not missing_db:
        with sqlite3.connect(dbfile) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("CREATE TABLE example (id INTEGER PRIMARY KEY)")
    monkeypatch.setattr(config, "DB_URL", f"sqlite:///{dbfile}")
    directory = tmp_path / "real-backup-archives"
    directory.mkdir()
    monkeypatch.setattr(backup, "BACKUP_DIR", directory)
    if with_backup:
        (directory / "tracker-20261031T010203000000Z.zip").write_bytes(
            b"fixture archive name only"
        )
    app = FastAPI()
    app.include_router(router)
    return TestClient(app), directory


def test_maintenance_reports_configured_backup_location(tmp_path, monkeypatch):
    client, root = _client(tmp_path, monkeypatch, with_backup=True)
    with client:
        result = client.get("/maintenance-review")
    assert result.status_code == 200
    assert str(root) in result.text
    assert "Tracker backup archives" in result.text
    assert "1 archive(s) available" in result.text
    assert "Latest backup age" in result.text
    assert "passing" in result.text
    assert "needing attention" in result.text
    assert "does not verify archive contents" in result.text
    assert "/tmp/tracker-backups" not in result.text


def test_maintenance_handles_missing_backups(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    with client:
        result = client.get("/maintenance-review")
    assert result.status_code == 200
    assert "No backup archives found" in result.text
    assert "ATTENTION" in result.text


def test_maintenance_missing_db_is_an_attention_not_a_500(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch, missing_db=True)
    with client:
        result = client.get("/maintenance-review")
    assert result.status_code == 200
    assert "Database inspection" in result.text
    assert "ATTENTION" in result.text


def test_maintenance_missing_backup_dir_is_visible(tmp_path, monkeypatch):
    client, root = _client(tmp_path, monkeypatch)
    root.rmdir()
    with client:
        response = client.get("/maintenance-review")
    assert response.status_code == 200
    assert "Missing:" in response.text
    assert "No backup archives found" in response.text
