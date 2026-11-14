"""Release 623: prioritized offline CSRF evidence review."""
import json
import subprocess
import sys
from pathlib import Path

from scripts.tracker_csrf_review_queue623 import prioritized_report

ROOT = Path(__file__).resolve().parents[1]


def test_623_queue_is_stable_and_never_security_verdict():
    report = prioritized_report(ROOT)
    assert report["runtime_csrf_verification"] is False
    assert report["vulnerability_assessment"] is False
    totals = report["totals"]
    assert totals["unsafe_handler_declarations"] >= 15
    assert totals["template_write_controls"] >= 10
    assert totals["javascript_request_candidates"] >= 0
    assert totals["review_items"] == len(report["findings"])
    assert totals["review_items"] == sum(totals["by_priority"].values())
    order = {"P1": 0, "P2": 1, "P3": 2}
    assert [order[r["priority"]] for r in report["findings"]] == sorted(
        order[r["priority"]] for r in report["findings"]
    )
    assert all(r["review_status"] == "MANUAL_REVIEW_REQUIRED"
               for r in report["findings"])
    assert any(r["category"] == "template-write-control"
               for r in report["findings"])
    assert any(r["category"] == "declared-route-without-static-template-match"
               for r in report["findings"])


def test_623_offline_cli_and_bounded_display():
    script = ROOT / "scripts" / "tracker_csrf_review_queue623.py"
    result = subprocess.run(
        [sys.executable, str(script), "--limit", "3"],
        cwd="/tmp", capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    assert data["runtime_csrf_verification"] is False
    assert data["vulnerability_assessment"] is False
    assert len(data["findings"]) == 3
    assert data["shown_items"] == 3
    assert data["totals"]["review_items"] >= 3
    bad = subprocess.run(
        [sys.executable, str(script), "--limit", "-1"],
        cwd="/tmp", capture_output=True, text=True,
    )
    assert bad.returncode != 0


def test_623_no_policy_change_and_existing_audit_sources_available():
    assert 'os.environ.get("TRACKER_CSRF_ENFORCE", "0")' in (
        ROOT / "app/main.py"
    ).read_text(encoding="utf-8")
    for name in ("tracker_csrf_route_inventory620.py",
                 "tracker_csrf_form_crosswalk621.py",
                 "tracker_csrf_js_inventory622.py"):
        assert (ROOT / "scripts" / name).is_file()
