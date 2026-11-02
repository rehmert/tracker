"""Isolated restore evidence in Maintenance Review and Backups."""
from pathlib import Path
import sqlite3
import subprocess
import sys
import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import backup, config
from app.recovery_status import record_restore
from app.routers import backups, maintenance_review


def example(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    database = data / "tracker.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
    monkeypatch.setattr(config, "DB_URL", f"sqlite:///{database}")
    root = tmp_path / "archives"
    root.mkdir()
    monkeypatch.setattr(backup, "BACKUP_DIR", root)
    archive = backup.create_backup(data, root)
    app = FastAPI()
    app.include_router(backups.router)
    app.include_router(maintenance_review.router)
    return TestClient(app), archive, root


def test_unverified_backup_is_not_mislabeled(tmp_path, monkeypatch):
    client, _, _ = example(tmp_path, monkeypatch)
    with client:
        history = client.get("/backups")
        maintenance = client.get("/maintenance-review")
    assert history.status_code == maintenance.status_code == 200
    assert "RESTORE CHECK NEEDED" in history.text
    assert "No current restore evidence" in history.text
    assert "Isolated backup restoration" in maintenance.text
    assert "No isolated backup restore recorded" in maintenance.text


def test_recorded_restoration_appears_on_both_pages(tmp_path, monkeypatch):
    client, archive, root = example(tmp_path, monkeypatch)
    record_restore(archive, {"files": 1, "uploads": 0, "tables": 1, "bytes": 8192}, root)
    with client:
        history = client.get("/backups")
        maintenance = client.get("/maintenance-review")
    assert history.status_code == maintenance.status_code == 200
    assert "RESTORE CHECK PASSED" in history.text
    assert "Restore-tested" in history.text
    assert "Isolated restore passed" in maintenance.text


def test_cli_isolated_restore_creates_real_receipt(tmp_path, monkeypatch):
    client, archive, root = example(tmp_path, monkeypatch)
    project = Path(__file__).resolve().parents[1]
    environment = dict(os.environ, TRACKER_BACKUP_DIR=str(root))
    result = subprocess.run(
        [sys.executable, "scripts/tracker-restore-verify.py",
         "--archive", str(archive), "--record-status"],
        cwd=project, env=environment, capture_output=True, text=True,
        timeout=40, check=False,
    )
    assert result.returncode == 0, (result.stderr[:500], result.stdout[:500])
    assert "Recovery receipt recorded" in result.stdout
    with client:
        response = client.get("/backups")
    assert "RESTORE CHECK PASSED" in response.text


def test_scheduled_backup_refuses_prune_when_restore_fails(monkeypatch, tmp_path):
    from scripts import tracker_backup
    archive = tmp_path / "tracker-20261102T000000000000Z.zip"
    archive.write_bytes(b"fixture")
    monkeypatch.setattr(tracker_backup, "create_backup", lambda: archive)
    actions = []
    monkeypatch.setattr(
        tracker_backup, "prune_backups", lambda: actions.append("PRUNE")
    )
    def fail_restore(_archive):
        raise RuntimeError("simulated restore failure")
    monkeypatch.setattr(tracker_backup, "verify_restorable", fail_restore)
    monkeypatch.setattr(sys, "argv", ["tracker_backup", "create"])
    import pytest
    with pytest.raises(RuntimeError, match="simulated"):
        tracker_backup.main()
    assert actions == []
    assert archive.exists()
