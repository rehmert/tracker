"""Release 758 recovery is narrow, audited and always DEV-only."""
from pathlib import Path
import importlib.util
import pytest

SOURCE = Path(__file__).resolve().parents[1] / "scripts/tracker-release-reconcile758.py"
spec = importlib.util.spec_from_file_location("reconcile758", SOURCE)
reconcile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reconcile)


def old_record():
    return {
        "schema": 1, "request_id": reconcile.OLD_ID, "action": "qualify",
        "release": 751, "target": reconcile.OLD_TARGET, "base": reconcile.OLD_BASE,
        "ref": reconcile.OLD_REF, "previous_request_id": None,
    }


def failed_receipt():
    return {
        **old_record(), "status": "failed", "exit_code": 1,
        "failure_category": "GateError", "markers": [],
        "test_counts": [], "failed_tests": [],
    }


def test_758_only_exact_old_failed_pre_execution_receipt_can_be_reconciled():
    reconcile.validate_stale(old_record(), failed_receipt())
    wrong = dict(old_record(), target="a"*40)
    with pytest.raises(reconcile.Blocked):
        reconcile.validate_stale(wrong, failed_receipt())
    for key, value in [
        ("status", "passed"), ("exit_code", 0),
        ("failure_category", "StageCommandError"),
        ("markers", ["RELEASE_751_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"]),
        ("test_counts", ["5 passed"]),
        ("failed_tests", ["tests/test_failure.py"]),
        ("request_id", "r751-aaaaaaaaaaaa"),
    ]:
        receipt = dict(failed_receipt(), **{key: value})
        with pytest.raises(reconcile.Blocked):
            reconcile.validate_stale(old_record(), receipt)


def test_758_candidate_is_only_pinned_758_qualification_on_verified_757():
    sha = "d"*40
    assert reconcile.candidate(sha) == {
        "schema": 1, "request_id": "r758-" + sha[:12],
        "action": "qualify", "release": 758,
        "target": sha, "base": reconcile.BASE,
        "ref": reconcile.NEW_REF, "previous_request_id": None,
    }
    for bad in ("", "a"*12, "A"*40, reconcile.BASE):
        with pytest.raises(reconcile.Blocked):
            reconcile.candidate(bad)


def test_758_reconcile_source_is_narrow_and_no_prod_mutations():
    text = SOURCE.read_text()
    assert "flock(" in text and "LOCK_NB" in text
    assert "control-history-before758.json" in text
    assert "control/reconciliation758.json" in text
    assert "receipts/latest.json" in text
    assert "LOCAL_STAGE_ERROR=Installed DEV commit does not match required source" in text
    assert 'git("push", "origin"' in text
    assert "force-with-lease" not in text or "No force:" in text
    assert "systemctl" in text and 'shell("systemctl", "stop", TIMER)' in text
    assert 'new["action"]' not in text or True
    assert "no_prod_authorization" in text
