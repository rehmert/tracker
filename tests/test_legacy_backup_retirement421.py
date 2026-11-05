"""Release 421: retired backup and consistent background audit contracts."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "scripts/backup.sh"
UPDATER = ROOT / "scripts/update.sh"


def audit_module(relative, name):
    source = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_legacy_backup_refuses_and_preserves_files(tmp_path):
    data = tmp_path / "data"
    data.mkdir()

    database = data / "tracker.db"
    database.write_bytes(b"PRESERVE-DATABASE")

    uploads = data / "uploads"
    uploads.mkdir()
    document = uploads / "coa.pdf"
    document.write_bytes(b"PRESERVE-UPLOAD")

    output = tmp_path / "new-backups"

    result = subprocess.run(
        ["sh", str(LEGACY), str(output)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 2
    assert "retired" in result.stderr
    assert "scripts.tracker_backup create" in result.stderr
    assert not output.exists()
    assert database.read_bytes() == b"PRESERVE-DATABASE"
    assert document.read_bytes() == b"PRESERVE-UPLOAD"


def test_legacy_backup_has_no_direct_write_commands():
    source = LEGACY.read_text()

    for forbidden in (
        "sqlite3 ",
        "tar -czf",
        "mkdir -p",
        "git pull",
        "systemctl restart",
    ):
        assert forbidden not in source

    assert source.endswith("exit 2\n")


def test_old_update_entrypoint_remains_blocked(tmp_path):
    result = subprocess.run(
        ["sh", str(UPDATER)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 2


def test_verified_backup_service_remains_in_use():
    source = (ROOT / "deploy/tracker-backup.service").read_text()
    assert "-m scripts.tracker_backup create" in source
    assert "scripts/backup.sh" not in source


def test_409_audit_recognizes_retired_backup():
    audit = audit_module(
        "scripts/tracker-background-storage-audit409.py",
        "audit409_421",
    )
    report = audit.build_report()
    audit.validate(report)

    legacy = report["shell_targets"]["legacy_shell_backup"]
    assert legacy["retired_entrypoint"]
    assert not legacy["calls_sqlite3_cli"]
    assert not legacy["calls_archive_cli"]


def test_409_audit_rejects_unretirement():
    audit = audit_module(
        "scripts/tracker-background-storage-audit409.py",
        "audit409_negative421",
    )
    report = audit.build_report()

    report["shell_targets"]["legacy_shell_backup"][
        "retired_entrypoint"
    ] = False

    with pytest.raises(RuntimeError, match="remain retired"):
        audit.validate(report)


def test_418_audit_recognizes_retirement_and_validates_queue():
    audit = audit_module(
        "scripts/tracker-background-entrypoints-audit418.py",
        "audit418_421",
    )
    report = audit.build_report()
    audit.validate(report)

    legacy = report["entrypoints"]["legacy_shell_backup"]
    assert legacy["classification"] == "retired_fail_closed"
    assert legacy["requires_review"] is False
    assert "legacy_shell_backup" not in report["review_queue"]
    assert "database_health_sweep" in report["review_queue"]


def test_418_audit_rejects_restoring_old_review_requirement():
    audit = audit_module(
        "scripts/tracker-background-entrypoints-audit418.py",
        "audit418_negative421",
    )
    report = audit.build_report()

    report["entrypoints"]["legacy_shell_backup"][
        "requires_review"
    ] = True
    report["review_queue"] = sorted(
        set(report["review_queue"]) | {"legacy_shell_backup"}
    )

    with pytest.raises(RuntimeError, match="Retired"):
        audit.validate(report)


def test_419_scheduler_source_audit_still_works():
    audit = audit_module(
        "scripts/tracker-legacy-backup-schedule-audit419.py",
        "audit419_421",
    )
    report = audit.build_report(runtime=False)

    assert report["legacy_references"] == []
    assert report["coverage_complete"] is False


def test_secondary_accounts_still_disabled():
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)
