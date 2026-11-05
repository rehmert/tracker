"""Release 418: source-only inventory regression tests."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AUDIT = (
    ROOT
    / "scripts"
    / "tracker-background-entrypoints-audit418.py"
)


def load_audit():
    spec = importlib.util.spec_from_file_location(
        "entrypoints418",
        AUDIT,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_inventory_is_explicit_and_incomplete():
    audit = load_audit()
    report = audit.build_report()
    audit.validate(report)

    assert report["release"] == 418
    assert report["scope"].startswith("curated source-only")
    assert len(report["entrypoints"]) == 12
    assert not report["multi_user_enabled"]
    assert not report["background_job_isolation_complete"]
    assert not report["additional_accounts_allowed"]


def test_legacy_bypass_paths_are_not_classified_as_protected():
    report = load_audit().build_report()
    items = report["entrypoints"]

    assert (
        items["legacy_shell_backup"]["classification"]
        == "retired_fail_closed"
    )

    assert (
        items["database_health_sweep"]["classification"]
        == "broad_discovery_read_only"
    )

    assert (
        items["database_upgrade"]["classification"]
        == "unscoped_migration_write"
    )

    assert items["maintenance_cli"]["requires_review"]
    assert items["replication_cli"]["requires_review"]

    assert "database_health_sweep" in report["review_queue"]
    assert "legacy_shell_backup" not in report["review_queue"]
    assert not items["legacy_shell_backup"]["requires_review"]


def test_validated_default_and_opt_in_paths_are_distinguished():
    items = load_audit().build_report()["entrypoints"]

    assert (
        items["scheduled_backup"]["classification"]
        == "admin_context_default"
    )

    assert (
        items["backup_timer_unit"]["classification"]
        == "configured_backup_entrypoint"
    )

    assert (
        items["maintenance_cli"]["classification"]
        == "opt_in_scoped_legacy_available"
    )

    assert (
        items["replication_cli"]["classification"]
        == "validated_default_manual_override"
    )


def test_evidence_lines_point_to_real_source():
    report = load_audit().build_report()

    for item in report["entrypoints"].values():
        content = (
            ROOT / item["path"]
        ).read_text().splitlines()

        for marker, line in item["evidence_lines"].items():
            assert marker in content[line - 1]

        assert len(item["sha256"]) == 64


def test_source_scan_does_not_modify_target_files():
    audit = load_audit()

    before = {
        target[0]: (ROOT / target[0]).read_bytes()
        for target in audit.TARGETS.values()
    }

    audit.build_report()

    assert before == {
        target[0]: (ROOT / target[0]).read_bytes()
        for target in audit.TARGETS.values()
    }


def test_source_drift_fails_closed(tmp_path):
    audit = load_audit()

    for relative, _, _ in audit.TARGETS.values():
        destination = tmp_path / relative
        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        destination.write_bytes(
            (ROOT / relative).read_bytes()
        )

    legacy = tmp_path / "scripts/backup.sh"
    before = legacy.read_text()

    assert "exit 2" in before

    legacy.write_text(
        before.replace(
            "exit 2",
            "exit 0",
            1,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="review classification",
    ):
        audit.build_report(tmp_path)


def test_missing_scanned_file_fails_closed(tmp_path):
    audit = load_audit()

    with pytest.raises(FileNotFoundError):
        audit.build_report(tmp_path)


def test_false_isolation_claim_is_rejected():
    audit = load_audit()
    report = audit.build_report()

    report["additional_accounts_allowed"] = True

    with pytest.raises(
        RuntimeError,
        match="isolation-complete",
    ):
        audit.validate(report)


def test_json_cli_without_app_import_or_pythonpath():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            str(AUDIT),
            "--json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr

    data = json.loads(result.stdout)

    assert data["release"] == 418
    assert data["review_queue"]
    assert data["additional_accounts_allowed"] is False


def test_secondary_accounts_remain_disabled():
    from app.user_storage388 import live_storage_for

    for uid in (2, 3):
        with pytest.raises(PermissionError):
            live_storage_for(uid)
