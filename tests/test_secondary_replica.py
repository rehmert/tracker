"""Verified local-only backup replication: no modifications to primary DB."""
import importlib.util
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from app import backup
from app.replica_health import replica_health

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "tracker_local_replica", ROOT / "scripts/tracker_replica.py"
)
replica = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replica)


@pytest.fixture
def copies(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    with sqlite3.connect(data / "tracker.db") as connection:
        connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, text TEXT)")
        connection.execute("INSERT INTO sample VALUES (1, 'preserve')")
    upload = data / "uploads" / "coa" / "sample.pdf"
    upload.parent.mkdir(parents=True)
    upload.write_bytes(b"%PDF-local-copy-test")
    primary = tmp_path / "primary"
    secondary = tmp_path / "secondary"
    secondary.mkdir()
    archive = backup.create_backup(data, primary)
    return data, primary, secondary, archive


def test_first_replica_verifies_latest_copy_and_receipt(copies):
    data, source, target, archive = copies
    before_db = (data / "tracker.db").read_bytes()
    result = replica.replicate(source, target, keep=4)
    assert (result["copied"], result["matched"]) == (1, 0)
    assert replica.fingerprint(target / archive.name) == replica.fingerprint(archive)
    assert (target / replica.RECEIPT).stat().st_mode & 0o777 == 0o644
    assert replica_health(source, target)["ok"]
    assert (data / "tracker.db").read_bytes() == before_db


def test_second_replica_matches_without_replacing_existing(copies):
    _, source, target, archive = copies
    replica.replicate(source, target)
    inode = (target / archive.name).stat().st_ino
    result = replica.replicate(source, target)
    assert result["copied"] == 0 and result["matched"] == 1
    assert (target / archive.name).stat().st_ino == inode


def test_corrupt_primary_refuses_copy_and_prune(copies):
    _, source, target, archive = copies
    old = target / "tracker-20200101T000000000000Z.zip"
    old.write_bytes(b"existing-old")
    archive.write_bytes(b"not a real ZIP")
    with pytest.raises(Exception):
        replica.replicate(source, target, keep=1)
    assert old.read_bytes() == b"existing-old"
    assert not (target / replica.RECEIPT).exists()


def test_existing_wrong_copy_refuses_overwrite_or_prune(copies):
    _, source, target, archive = copies
    (target / archive.name).write_bytes(b"bad replica data")
    old = target / "tracker-20200101T000000000000Z.zip"
    old.write_bytes(b"do not delete")
    with pytest.raises(ValueError, match="hash mismatch"):
        replica.replicate(source, target, keep=1)
    assert (target / archive.name).read_bytes() == b"bad replica data"
    assert old.exists()


def test_replica_status_fails_when_primary_advances(copies):
    data, source, target, archive = copies
    replica.replicate(source, target)
    new = backup.create_backup(data, source)
    assert new.name != archive.name
    status = replica_health(source, target)
    assert not status["ok"] and status["state"] == "behind"


def test_replica_status_fails_when_target_changes(copies):
    _, source, target, archive = copies
    replica.replicate(source, target)
    (target / archive.name).write_bytes(b"tampered")
    status = replica_health(source, target)
    assert not status["ok"] and status["state"] == "changed"


def test_replica_symlink_is_rejected(copies):
    _, source, target, archive = copies
    (target / archive.name).symlink_to(archive)
    with pytest.raises(ValueError, match="Unsafe replica"):
        replica.replicate(source, target)


def test_replica_refuses_same_or_nested_directories(copies):
    _, source, target, _ = copies
    with pytest.raises(ValueError):
        replica.replicate(source, source)
    nested = source / "nested"
    nested.mkdir()
    with pytest.raises(ValueError):
        replica.replicate(source, nested)


def test_replica_command_works_without_pythonpath(copies, tmp_path):
    _, source, target, archive = copies
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["TRACKER_DATA_DIR"] = str(tmp_path / "no-real-data")
    result = subprocess.run(
        [sys.executable, "-I", str(ROOT / "scripts/tracker_replica.py"),
         "--source", str(source), "--dest", str(target), "--keep", "4"],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, (result.stdout[:500], result.stderr[:500])
    assert "Secondary local copy verified" in result.stdout
    assert (target / archive.name).is_file()


def test_missing_optional_replica_is_informational(copies, monkeypatch):
    _, source, target, _ = copies
    target.rmdir()
    # Explicit configuration with a nonexistent destination is actionable.
    # No replica is copied and the primary remains untouched.
    configured = replica_health(source, target)
    assert not configured["ok"] and configured["state"] == "invalid"


def test_successful_copy_prunes_only_after_verifying_current_set(copies):
    _, source, target, archive = copies
    old = target / "tracker-20200101T000000000000Z.zip"
    old.write_bytes(b"expired secondary file")
    result = replica.replicate(source, target, keep=1)
    assert result["pruned"] == 1
    assert not old.exists()
    assert (target / archive.name).exists()


def test_status_requires_replica_receipt(copies):
    _, source, target, archive = copies
    (target / archive.name).write_bytes(archive.read_bytes())
    status = replica_health(source, target)
    assert status["state"] == "unverified"
    assert not status["ok"]


def test_maintenance_review_reports_verified_local_copy(copies, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.maintenance_review import router
    from app import config
    data, source, target, archive = copies
    monkeypatch.setattr(config, "DB_URL", f"sqlite:///{data / 'tracker.db'}")
    monkeypatch.setattr(backup, "BACKUP_DIR", source)
    monkeypatch.setenv("TRACKER_BACKUP_REPLICA_DIR", str(target))
    replica.replicate(source, target)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        result = client.get("/maintenance-review")
    assert result.status_code == 200
    assert "Secondary local backup copy" in result.text
    assert "Local secondary copy byte-matched" in result.text
    assert "not off-host" in result.text
