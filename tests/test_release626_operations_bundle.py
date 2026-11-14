"""Release 626 combined phases 2–4: offline operations visibility and diagnostics."""
import json
import subprocess
import sys
from pathlib import Path

from scripts.tracker_release_diagnostics626 import summarize
from scripts.tracker_operations_review626 import dashboard

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40


def test_626_release_log_strips_paths_addresses_and_secrets():
    raw = (
        "TRACKER RELEASE DEPLOYMENT SUCCESS\n"
        "EXIT_STATUS=0\n"
        "DEV_QUALIFICATION_EVIDENCE_PRESERVED=/etc/tracker-release/secrets.log\n"
        "Connection to private-host.example closed\n"
        "USER_PASSWORD=super-secret\n"
        f"PROD_DEPLOY_VERIFIED={SHA}\n"
        "REMOTE_DEPLOY_EXIT_STATUS=0\n"
        f"PROD_INSTALLED_COMMIT={SHA}\n"
        "DEV_CONTROLLED_RELEASE=SUCCESS\n"
    )
    result = summarize(raw)
    assert result["dev_receipt_markers_complete"] is True
    assert result["prod_promotion_markers_complete"] is True
    assert result["ssh_disconnect_cause"] == "NOT_DETERMINABLE_FROM_RELEASE_LOG"
    serialized = json.dumps(result)
    for secret in ("super-secret", "private-host.example", "/etc/tracker-release"):
        assert secret not in serialized


def test_626_release_log_rejects_incomplete_or_mismatched_markers():
    report = summarize(
        f"REMOTE_DEPLOY_EXIT_STATUS=1\nPROD_DEPLOY_VERIFIED={SHA}\n"
        f"PROD_INSTALLED_COMMIT={'b' * 40}\n"
        "DEV_CONTROLLED_RELEASE=SUCCESS\n"
    )
    assert report["prod_promotion_markers_complete"] is False
    assert report["dev_receipt_markers_complete"] is False


def test_626_dashboard_reports_limits_and_static_counts():
    result = dashboard(ROOT)
    assert result["read_only"] is True
    assert result["live_host_status"] == "NOT_CHECKED"
    assert result["csrf"]["runtime_verified"] is False
    assert result["csrf"]["review_items"] >= 10
    assert result["dependencies"]["fresh_environment_reproduced"] is False
    assert result["dependencies"]["historical_observed_packages"] == 44
    assert result["release"]["evidence"] == "NOT_PROVIDED"


def test_626_operations_cli_absolute_path_and_supplied_log(tmp_path):
    log = tmp_path / "release.log"
    log.write_text("EXIT_STATUS=2\nSECRET=do-not-echo\n", encoding="utf-8")
    command = subprocess.run(
        [sys.executable, str(ROOT / "scripts/tracker_operations_review626.py"),
         "--release-log", str(log)],
        cwd="/tmp", text=True, capture_output=True, check=True,
    )
    result = json.loads(command.stdout)
    assert result["release"]["markers"]["EXIT_STATUS"] == "2"
    assert "do-not-echo" not in command.stdout
    assert result["release"]["prod_promotion_markers_complete"] is False
