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
