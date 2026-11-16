"""Release 652: DEV-only migration archive verifies the exact known missing file."""
import hashlib
import importlib.util
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "tracker-coa-dev-backup652.py"
MISSING = "uploads/coa/b94356f52d964400b481e6c743484367.png"


def module652():
    spec = importlib.util.spec_from_file_location("coa_dev_backup652", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def archive652(tmp_path, missing_name):
    db_path = tmp_path / "tracker.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TABLE coa_attachments (id INTEGER PRIMARY KEY,"
            "stored_name TEXT, original_name TEXT)"
        )
        connection.execute(
            "INSERT INTO coa_attachments(stored_name, original_name) VALUES (?,?)",
            (missing_name, "reported-original.png"),
        )
        connection.commit()
    raw = db_path.read_bytes()
    manifest = {
        "kind": "DEV-652-INCOMPLETE-ATTACHMENT-REVIEW",
        "known_missing": [MISSING],
        "files": {
            "tracker.db": {
                "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()
            }
        },
    }
    file = tmp_path / "backup652.zip"
    with zipfile.ZipFile(file, "w") as z:
        z.writestr("tracker.db", raw)
        z.writestr("manifest.json", json.dumps(manifest))
    return file


def test_652_dev_migration_archive_allows_only_identified_missing_reference(tmp_path):
    mod = module652()
    file = archive652(tmp_path, Path(MISSING).name)
    assert mod.verify_archive(file, [MISSING]) == 1


def test_652_dev_migration_archive_rejects_different_missing_file(tmp_path):
    mod = module652()
    file = archive652(tmp_path, "another-unverified-missing.pdf")
    with pytest.raises(ValueError, match="attachment references changed"):
        mod.verify_archive(file, [MISSING])


def test_652_dev_migration_archive_refuses_false_missing_evidence(tmp_path):
    mod = module652()
    file = archive652(tmp_path, Path(MISSING).name)
    with pytest.raises(ValueError, match="Missing-reference evidence"):
        mod.verify_archive(file, [])


def test_652_dev_backup_cli_stdout_contains_only_archive_path(
    tmp_path, monkeypatch, capsys
):
    """Regression: stdout must be safe for ARCHIVE="$(...)" in release worker."""
    from types import SimpleNamespace

    mod = module652()
    data = tmp_path / "data"
    (data / "uploads").mkdir(parents=True)
    archive_dir = tmp_path / "archives"

    with sqlite3.connect(data / "tracker.db") as db:
        db.execute(
            "CREATE TABLE coa_attachments "
            "(id INTEGER PRIMARY KEY, stored_name TEXT, original_name TEXT)"
        )
        db.execute(
            "INSERT INTO coa_attachments(stored_name, original_name) VALUES (?,?)",
            (Path(MISSING).name, "historical-upload.png"),
        )

    monkeypatch.setattr(mod, "verify_dev_instance", lambda: None)
    monkeypatch.setattr(mod.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        mod.os, "uname", lambda: SimpleNamespace(nodename="tracker-dev")
    )

    def diagnostics(_argv):
        print("MISSING_REFERENCE table=coa_attachments id=1")
        print("ATTACHMENT_FILES_MISSING=1")
        print("DEV_ATTACHMENT_GATE=DEV_MISSING_ALLOWED")
        return 0

    monkeypatch.setattr(mod, "attachment_gate", diagnostics)
    monkeypatch.setattr(
        mod.os.sys,
        "argv",
        ["tracker-coa-dev-backup652.py", "--data", str(data), "--dest", str(archive_dir)],
    )
    assert mod.main() == 0

    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert len(lines) == 1, "The shell runner must capture only one path"
    archive = Path(lines[0])
    assert archive.parent == archive_dir
    assert archive.is_file()
    assert "MISSING_REFERENCE" not in captured.out
    assert "ATTACHMENT_FILES_MISSING=1" in captured.err
    assert "DEV_652_DATABASE_AND_PRESENT_UPLOADS_RESTORED=PASSED" in captured.err
    assert mod.verify_archive(archive, [MISSING]) == 1


def test_652_dev_attachment_failure_never_returns_an_archive_path(
    tmp_path, monkeypatch, capsys
):
    mod = module652()

    def failing_gate(_args):
        print("HASH_MISMATCH table=coa_attachments id=1")
        return 1

    monkeypatch.setattr(mod, "attachment_gate", failing_gate)
    with pytest.raises(ValueError, match="failed integrity"):
        mod.verify_dev_attachment_gate(tmp_path)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "HASH_MISMATCH" in captured.err
