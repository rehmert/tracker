"""Point-in-time backup restore receipts; no live database usage."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import sqlite3

import pytest
from app.backup import create_backup
from app.recovery_status import RECEIPT_NAME, record_restore, restore_status


def sample(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    with sqlite3.connect(data / "tracker.db") as conn:
        conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
    root = tmp_path / "backups"
    archive = create_backup(data, root)
    return archive, root, data


def proof():
    return {"files": 1, "uploads": 0, "tables": 1, "bytes": 8192}


def test_successful_receipt_is_private_and_visible(tmp_path):
    archive, root, _ = sample(tmp_path)
    result = record_restore(archive, proof(), root)
    assert result["archive"] == archive.name
    assert (root / RECEIPT_NAME).stat().st_mode & 0o777 == 0o600
    status = restore_status(root)
    assert status["ok"] and status["state"] == "verified"
    assert archive.name in status["detail"]


def test_no_receipt_is_not_an_assumed_success(tmp_path):
    _, root, _ = sample(tmp_path)
    status = restore_status(root)
    assert not status["ok"] and status["state"] == "never"


def test_changed_archive_invalidates_receipt(tmp_path):
    archive, root, _ = sample(tmp_path)
    record_restore(archive, proof(), root)
    archive.write_bytes(archive.read_bytes() + b"x")
    status = restore_status(root)
    assert not status["ok"] and status["state"] == "changed"


def test_newer_archive_invalidates_latest_status(tmp_path):
    archive, root, data = sample(tmp_path)
    record_restore(archive, proof(), root)
    next_backup = create_backup(data, root)
    assert next_backup.name != archive.name
    status = restore_status(root)
    assert not status["ok"] and status["state"] == "not_latest"


def test_old_receipt_is_reported_stale(tmp_path):
    archive, root, _ = sample(tmp_path)
    result = record_restore(archive, proof(), root)
    verified = datetime.fromisoformat(result["verified_utc"])
    status = restore_status(root, now=verified + timedelta(hours=26))
    assert not status["ok"] and status["state"] == "old"


def test_symlinked_receipt_not_trusted(tmp_path):
    archive, root, _ = sample(tmp_path)
    record_restore(archive, proof(), root)
    receipt = root / RECEIPT_NAME
    receipt.rename(root / "old-receipt.json")
    receipt.symlink_to(root / "old-receipt.json")
    assert not restore_status(root)["ok"]


@pytest.mark.parametrize("stats", [
    {}, {"files": 0, "uploads": 0, "tables": 0, "bytes": 1},
    {"files": 1, "uploads": 0, "tables": 1, "bytes": -1},
])
def test_unverified_results_do_not_generate_receipts(tmp_path, stats):
    archive, root, _ = sample(tmp_path)
    with pytest.raises(ValueError):
        record_restore(archive, stats, root)
    assert not (root / RECEIPT_NAME).exists()


def test_archive_outside_backup_dir_is_refused(tmp_path):
    archive, root, _ = sample(tmp_path)
    with pytest.raises(ValueError):
        record_restore(archive, proof(), tmp_path / "wrong-backups")
