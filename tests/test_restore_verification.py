"""Verify synthetic SQLite+uploads backups restore in isolation."""
from pathlib import Path
import importlib.util
import sqlite3

import pytest
from app.backup import create_backup

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "tracker_restore_check", ROOT / "scripts/tracker-restore-verify.py"
)
restore = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(restore)


def synthetic_archive(tmp_path):
    data = tmp_path / "live-data"
    data.mkdir()
    with sqlite3.connect(data / "tracker.db") as db:
        db.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)")
        db.execute("INSERT INTO sample VALUES (1, 'unchanged')")
    upload = data / "uploads/coa/example.pdf"
    upload.parent.mkdir(parents=True)
    upload.write_bytes(b"%PDF-synthetic-test-only")
    archive = create_backup(data, tmp_path / "archives")
    return data, archive


def test_restore_checks_database_and_uploads_without_live_writes(tmp_path):
    data, archive = synthetic_archive(tmp_path)
    db_before = (data / "tracker.db").read_bytes()
    upload_before = (data / "uploads/coa/example.pdf").read_bytes()
    result = restore.restore_check(archive)
    assert (result["files"], result["uploads"], result["tables"]) == (2, 1, 1)
    assert (data / "tracker.db").read_bytes() == db_before
    assert (data / "uploads/coa/example.pdf").read_bytes() == upload_before
    assert not list(tmp_path.rglob("tracker-restore-check-*"))


@pytest.mark.parametrize("name", [
    "../etc/passwd", "/etc/passwd", "uploads/../../etc/passwd",
    "uploads\\bad.pdf", "C:/windows/system", "uploads/.",
    "uploads", "other.db", "uploads/foo/../bar.pdf", "uploads//file.pdf",
])
def test_unsafe_restore_names_rejected(name):
    with pytest.raises(ValueError):
        restore.validate_member(name)


def test_restore_size_limit_enforced(tmp_path):
    _, archive = synthetic_archive(tmp_path)
    with pytest.raises(ValueError, match="restore limit"):
        restore.restore_check(archive, max_bytes=10)


def test_symlinked_archive_rejected(tmp_path):
    _, archive = synthetic_archive(tmp_path)
    alias = tmp_path / "link.zip"
    alias.symlink_to(archive)
    with pytest.raises(ValueError, match="symlinked"):
        restore.restore_check(alias)


def test_restoration_never_calls_migrations():
    source = (ROOT / "scripts/tracker-restore-verify.py").read_text()
    assert "TemporaryDirectory" in source
    assert "migrate(" not in source
    assert "create_all(" not in source
