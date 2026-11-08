"""Release 516: bounded archive verification and deterministic SQLite disposal.

All databases and backup archives here are created inside pytest tmp_path.
No live DEV/PROD database or real backup directory is accessed.
"""
import hashlib
import json
import sqlite3
import warnings
import zipfile
from pathlib import Path

import pytest

from app import backup, session_auth385 as session_auth, secondary_request_db467


def _database_file(path):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE demo (value TEXT NOT NULL)")
        db.execute("INSERT INTO demo(value) VALUES ('safe')")
    return path.read_bytes()


def _archive(tmp_path, *, duplicate=False, metadata_bytes=None, uploads=False):
    db_bytes = _database_file(tmp_path / "test.db")
    entries = {
        "tracker.db": db_bytes,
    }
    if uploads:
        entries["uploads/coas/demo.png"] = b"plain test data"
    manifest = {
        "version": 1,
        "files": {
            name: {
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": (
                    metadata_bytes if name == "tracker.db" and metadata_bytes is not None
                    else len(payload)
                ),
            }
            for name, payload in entries.items()
        },
    }
    archive = tmp_path / "test.zip"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for name, payload in entries.items():
                z.writestr(name, payload)
                if duplicate and name == "tracker.db":
                    z.writestr(name, payload)
            z.writestr("manifest.json", json.dumps(manifest))
    return archive


def test_516_valid_archive_remains_recoverable(tmp_path):
    archive = _archive(tmp_path)
    result = backup.verify_backup(archive)
    assert result["files"]["tracker.db"]["bytes"] > 0


def test_516_rejects_duplicate_archive_members(tmp_path):
    archive = _archive(tmp_path, duplicate=True)
    with pytest.raises(ValueError, match="Duplicate"):
        backup.verify_backup(archive)


def test_516_rejects_excess_uncompressed_bytes(tmp_path, monkeypatch):
    archive = _archive(tmp_path)
    monkeypatch.setattr(backup, "MAX_RESTORED_BYTES", 1024)
    with pytest.raises(ValueError, match="uncompressed size"):
        backup.verify_backup(archive)


def test_516_rejects_excess_archive_entries(tmp_path, monkeypatch):
    archive = _archive(tmp_path, uploads=True)
    monkeypatch.setattr(backup, "MAX_BACKUP_ENTRIES", 2)
    with pytest.raises(ValueError, match="too many files"):
        backup.verify_backup(archive)


def test_516_rejects_declared_vs_actual_file_size_mismatch(tmp_path):
    archive = _archive(tmp_path, metadata_bytes=1)
    with pytest.raises(ValueError, match="metadata"):
        backup.verify_backup(archive)


def test_516_standard_backup_creation_and_restore_verification(tmp_path):
    data = tmp_path / "instance"
    data.mkdir()
    _database_file(data / "tracker.db")
    (data / "uploads").mkdir()
    saved = backup.create_backup(data_dir=data, backup_dir=tmp_path / "archives")
    assert saved.exists()
    assert backup.verify_backup(saved)["version"] == 1


def test_516_session_connection_setup_failure_closes_descriptor(
    tmp_path, monkeypatch
):
    store = tmp_path / "auth.sqlite3"
    store.touch()
    monkeypatch.setattr(session_auth, "database_path", lambda: store)

    class Failed:
        closed = False

        def execute(self, sql):
            raise sqlite3.OperationalError("PRAGMA failed")

        def close(self):
            self.closed = True

    failure = Failed()
    monkeypatch.setattr(
        session_auth.sqlite3, "connect",
        lambda *args, **kwargs: failure,
    )
    with pytest.raises(sqlite3.OperationalError):
        session_auth.connect()
    assert failure.closed


def test_516_session_ops_close_connections_after_success(
    tmp_path, monkeypatch
):
    store = tmp_path / "auth.sqlite3"
    monkeypatch.setattr(session_auth, "database_path", lambda: store)
    session_auth.bootstrap("admin514", "test password only")

    opened = []
    real_connect = session_auth.connect

    def watch_connect():
        connection = real_connect()
        opened.append(connection)
        return connection

    monkeypatch.setattr(session_auth, "connect", watch_connect)
    assert session_auth.verify_admin("admin514", "test password only")
    token, lifetime = session_auth.create_session(False)
    assert lifetime > 0
    assert session_auth.session_user(token) == 1
    session_auth.revoke(token)

    assert len(opened) >= 4
    for connection in opened:
        with pytest.raises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")


def test_516_secondary_readonly_context_closes_connection(tmp_path, monkeypatch):
    store = tmp_path / "user2.sqlite3"
    with sqlite3.connect(store) as db:
        db.execute(
            "CREATE TABLE tracker_staged_workspace426("
            "user_id INTEGER, status TEXT, schema_version INTEGER)"
        )
        db.execute(
            "INSERT INTO tracker_staged_workspace426 VALUES (2,'inactive',426)"
        )

    scope = secondary_request_db467.PrivateScope467(
        user_id=2, database=store, mode="secondary-read-only",
    )
    monkeypatch.setattr(
        secondary_request_db467,
        "verified_private_scope467",
        lambda request: scope,
    )
    with secondary_request_db467.readonly_private_db467(None) as (seen, db):
        assert seen.user_id == 2
        assert db.execute("SELECT 1").fetchone()[0] == 1

    with pytest.raises(sqlite3.ProgrammingError):
        db.execute("SELECT 1")
