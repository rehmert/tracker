"""Storage headroom and placement use synthetic paths, not live backup data."""
import os
from pathlib import Path
import sqlite3

import pytest

from app import backup
from app.storage_health import MIN_HEADROOM, backup_storage_status


def setup(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    with sqlite3.connect(data / "tracker.db") as db:
        db.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
    primary = tmp_path / "backup-dir"
    primary.mkdir()
    secondary = tmp_path / "secondary-dir"
    secondary.mkdir()
    return data, primary, secondary


def test_space_summary_of_empty_archive_dir(tmp_path, monkeypatch):
    _, primary, secondary = setup(tmp_path)
    monkeypatch.delenv("TRACKER_BACKUP_REPLICA_DIR", raising=False)
    report = backup_storage_status(primary, secondary)
    assert report["primary"]["count"] == 0
    assert report["primary"]["archive_bytes"] == 0
    assert "free" in report["primary"]["detail"]
    assert report["primary"]["headroom_bytes"] >= MIN_HEADROOM


def test_counts_only_existing_archive_files(tmp_path):
    data, primary, secondary = setup(tmp_path)
    archive = backup.create_backup(data, primary)
    (primary / "unrelated.txt").write_text("not a backup")
    report = backup_storage_status(primary, secondary)
    assert report["primary"]["count"] == 1
    assert report["primary"]["archive_bytes"] == archive.stat().st_size


def test_low_headroom_is_attention_not_a_crash(tmp_path, monkeypatch):
    _, primary, secondary = setup(tmp_path)
    import app.storage_health as module
    disk = os.statvfs(primary)
    class Usage:
        free = 100 * 1024 * 1024
        total = 1024 * 1024 * 1024
    monkeypatch.setattr(module.shutil, "disk_usage", lambda path: Usage())
    report = backup_storage_status(primary, secondary)
    assert not report["primary"]["ok"]
    assert report["primary"]["state"] == "low"
    assert "100.0 MiB free" in report["primary"]["detail"]


def test_missing_primary_directory_is_visible(tmp_path):
    _, primary, secondary = setup(tmp_path)
    primary.rmdir()
    report = backup_storage_status(primary, secondary)
    assert report["primary"]["state"] == "unavailable"
    assert "Primary backup storage unavailable" in report["primary"]["detail"]


def test_symlinked_primary_directory_refused(tmp_path):
    _, primary, secondary = setup(tmp_path)
    link = tmp_path / "linked-backups"
    link.symlink_to(primary, target_is_directory=True)
    report = backup_storage_status(link, secondary)
    assert not report["primary"]["ok"]
    assert "symlinked" in report["primary"]["detail"]


def test_same_filesystem_is_labeled_local_risk(tmp_path):
    _, primary, secondary = setup(tmp_path)
    report = backup_storage_status(primary, secondary)
    assert not report["secondary"]["ok"]
    assert report["secondary"]["state"] == "same_filesystem"
    assert "Same filesystem" in report["secondary"]["detail"]


def test_different_filesystems_are_labeled_but_not_offhost(tmp_path, monkeypatch):
    _, primary, secondary = setup(tmp_path)
    from app import storage_health as mod
    original = mod.Path.stat

    def distinct(path, *args, **kwargs):
        record = original(path, *args, **kwargs)
        if Path(path) == secondary:
            from types import SimpleNamespace
            return SimpleNamespace(st_dev=record.st_dev + 1)
        return record

    monkeypatch.setattr(mod.Path, "stat", distinct)
    report = backup_storage_status(primary, secondary)
    assert report["secondary"]["ok"]
    assert report["secondary"]["state"] == "different_filesystem"
    assert "off-host" in report["secondary"]["detail"]


def test_missing_secondary_directory_is_actionable_when_explicit(tmp_path):
    _, primary, secondary = setup(tmp_path)
    secondary.rmdir()
    report = backup_storage_status(primary, secondary)
    assert report["secondary"]["configured"]
    assert report["secondary"]["state"] == "unavailable"


def test_symlinked_archive_cannot_be_counted_as_protected(tmp_path):
    data, primary, secondary = setup(tmp_path)
    archive = backup.create_backup(data, primary)
    (primary / "tracker-20999999T000000000000Z.zip").symlink_to(archive)
    report = backup_storage_status(primary, secondary)
    assert not report["primary"]["ok"]
    assert report["primary"]["state"] == "unavailable"
