"""Release 747: fail-closed objective completion ledger tests."""
from pathlib import Path
import json

from scripts.tracker_security_readiness743 import build as csrf_audit
from scripts.tracker_host_evidence746 import compare as host_compare
from tests.test_release746_hardening import evidence
from app.multiuser_audit474 import audit474

ROOT=Path(__file__).resolve().parents[1]


def test_747_csrf_unqualified_routes_are_not_silently_declared_complete():
    audit=csrf_audit(ROOT)
    assert audit["strict_http_https_runtime_qualified"] is False
    assert audit["session_account_manual_review_complete"] is False
    assert audit["global_strict_csrf_enforcement_authorized"] is False
    assert audit["installed_policy"] == "REPORT_ONLY_UNCHANGED"


def test_747_even_identical_browser_and_os_hashes_are_not_rollback(tmp_path):
    record=evidence(tmp_path)
    comparison=host_compare(record, record)
    assert comparison["host_evidence_matches"]
    assert comparison["library_count"]==1
    assert comparison["os_library_rollback_tested"] is False
    assert comparison["dependency_update_authorized"] is False


def test_747_secondary_user_cutover_remains_explicitly_blocked():
    report=audit474()
    assert report["runtime_security_proven"] is False
    assert report["full_main_app_cutover_ready"] is False
    names={row["id"] for row in report["blocking_items"]}
    assert {"ADMIN_ONLY_SCOPE","FOOD_GLOBAL_ENGINE"} <= names


def test_747_closeout_contract_does_not_claim_issues_fully_closed():
    doc=(ROOT/"docs/tracker-747-closeout.md").read_text()
    for text in ("#9", "#10", "#54", "#56",
                 "REAL_PHONE_ACCEPTANCE=OUTSTANDING",
                 "OS_BROWSER_ROLLBACK=OUTSTANDING",
                 "GLOBAL_STRICT_CSRF=NOT_ENABLED",
                 "MULTIUSER_PARITY=NOT_CERTIFIED",
                 "PROD_REQUIRES_EXPLICIT_AUTHORIZATION"):
        assert text in doc
    assert "READY_TO_CLOSE_ALL_ISSUES=YES" not in doc
