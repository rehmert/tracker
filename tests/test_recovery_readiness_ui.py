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


def test_scheduled_backup_refuses_prune_when_restore_fails(
    monkeypatch, tmp_path
):
    """Failed restoration must not prune existing archives."""
    from types import SimpleNamespace
    import pytest
    from scripts import tracker_backup

    data = tmp_path / "data"
    data.mkdir()
    database = data / "tracker.db"
    database.write_bytes(b"test-fixture")

    archives = tmp_path / "archives"
    archives.mkdir()

    existing = archives / "tracker-existing.zip"
    existing.write_bytes(b"preserve-existing")

    created = archives / "tracker-20261102T000000000000Z.zip"
    created.write_bytes(b"created-fixture")

    context = SimpleNamespace(
        user_id=1,
        scope="legacy-admin-instance",
        data_dir=data,
        database=database,
        backup_dir=archives,
    )

    calls = []

    def selected_context():
        calls.append("context")
        return context

    def create_scoped(*, data_dir, backup_dir):
        assert data_dir == context.data_dir
        assert backup_dir == context.backup_dir
        calls.append("create")
        return created

    def failed_restore(archive):
        assert archive == created
        calls.append("restore")
        raise RuntimeError("simulated restore failure")

    def forbidden_prune(*, backup_dir):
        calls.append("prune")
        raise AssertionError(
            "Pruning after failed restore is forbidden"
        )

    monkeypatch.setattr(
        tracker_backup, "administrator_context410",
        selected_context,
    )
    monkeypatch.setattr(
        tracker_backup, "create_backup",
        create_scoped,
    )
    monkeypatch.setattr(
        tracker_backup, "verify_restorable",
        failed_restore,
    )
    monkeypatch.setattr(
        tracker_backup, "prune_backups",
        forbidden_prune,
    )
    monkeypatch.setattr(
        sys, "argv", ["tracker_backup", "create"]
    )

    with pytest.raises(RuntimeError, match="simulated"):
        tracker_backup.main()

    assert calls == ["context", "create", "restore"]
    assert created.read_bytes() == b"created-fixture"
    assert existing.read_bytes() == b"preserve-existing"
