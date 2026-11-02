"""Manual backup actions provide genuine isolated restore evidence.

Only synthetic databases and sandbox backup paths are used in these tests.
"""
from pathlib import Path
import sqlite3
import subprocess

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import backup, config
from app.recovery_status import record_restore
from app.routers import backups


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    with sqlite3.connect(data / "tracker.db") as db:
        db.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
    root = tmp_path / "archives"
    root.mkdir()
    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(backup, "BACKUP_DIR", root)

    calls = []

    def verified(archive):
        calls.append(("restore", archive.name))
        record_restore(
            archive, {"files": 1, "uploads": 0, "tables": 1, "bytes": 8192},
            root,
        )

    monkeypatch.setattr(backups, "verify_restorable", verified)

    def prune():
        calls.append(("prune", None))
        return []

    monkeypatch.setattr(backups, "prune_backups", prune)
    app = FastAPI()
    app.include_router(backups.router)
    return TestClient(app, follow_redirects=False), root, calls, monkeypatch


def test_manual_create_runs_restore_before_prune(fixture):
    client, root, calls, _ = fixture
    with client:
        response = client.post("/backups/create")
        assert response.status_code == 303
        assert "isolated%20restoration%20verified" in response.headers["location"]
        page = client.get("/backups")
        assert page.status_code == 200
        assert "RESTORE CHECK PASSED" in page.text
        assert "Test latest backup restoration" in page.text
    assert [action for action, _ in calls] == ["restore", "prune"]
    assert len(list(root.glob("tracker-*.zip"))) == 1


def test_manual_restore_failure_does_not_prune(fixture):
    client, root, calls, monkeypatch = fixture

    def failed(archive):
        calls.append(("restore failed", archive.name))
        raise subprocess.CalledProcessError(1, ["restore-check"])

    monkeypatch.setattr(backups, "verify_restorable", failed)
    with client:
        response = client.post("/backups/create")
    assert response.status_code == 303
    assert "err=" in response.headers["location"]
    assert [action for action, _ in calls] == ["restore failed"]
    assert len(list(root.glob("tracker-*.zip"))) == 1
    assert not (root / ".tracker-restore-receipt.json").exists()


def test_on_demand_latest_restore_succeeds_and_records_evidence(fixture):
    client, root, calls, _ = fixture
    archive = backup.create_backup()
    with client:
        page = client.get("/backups")
        assert "RESTORE CHECK NEEDED" in page.text
        response = client.post("/backups/restore-check", data={"name": archive.name})
        assert response.status_code == 303
        assert "err=" not in response.headers["location"]
        assert "RESTORE CHECK PASSED" in client.get("/backups").text
    assert [action for action, _ in calls] == ["restore"]


@pytest.mark.parametrize("name", [
    "../tracker-evil.zip", "/etc/passwd", "tracker-missing.zip", "untrusted.zip",
])
def test_restore_form_rejects_untrusted_names(fixture, name):
    client, _, calls, _ = fixture
    backup.create_backup()
    with client:
        response = client.post("/backups/restore-check", data={"name": name})
    assert response.status_code == 303
    assert "err=" in response.headers["location"]
    assert calls == []


def test_previous_backup_cannot_replace_latest_receipt(fixture):
    client, root, calls, _ = fixture
    previous = backup.create_backup()
    newest = backup.create_backup()
    assert previous.name != newest.name
    with client:
        response = client.post("/backups/restore-check", data={"name": previous.name})
    assert response.status_code == 303
    assert "err=" in response.headers["location"]
    assert calls == []
    assert not (root / ".tracker-restore-receipt.json").exists()


def test_on_demand_restore_failure_preserves_live_archive(fixture):
    client, root, calls, monkeypatch = fixture
    archive = backup.create_backup()

    def failed(path):
        calls.append(("failed", path.name))
        raise subprocess.TimeoutExpired(["restore"], 1)

    monkeypatch.setattr(backups, "verify_restorable", failed)
    with client:
        response = client.post("/backups/restore-check", data={"name": archive.name})
        page = client.get("/backups")
    assert "err=" in response.headers["location"]
    assert "RESTORE CHECK NEEDED" in page.text
    assert archive.is_file()
    assert [action for action, _ in calls] == ["failed"]
