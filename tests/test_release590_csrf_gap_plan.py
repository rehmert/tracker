"""Release 590: accurate route evidence and actionable unqualified workstreams."""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

from scripts import tracker_csrf_gap_plan590 as gap
from scripts import tracker_csrf_readiness588 as readiness

ROOT = Path(__file__).resolve().parents[1]


def test_590_coa_native_upload_is_source_candidate_not_global_clearance():
    result = readiness.report()
    rows = [r for r in result["routes"]
            if (r["method"], r["path"]) == ("POST", "/coas/new")]
    assert len(rows) == 1
    assert rows[0]["evidence_scope"] == "candidate_strict_browser_witness"
    assert rows[0]["runtime_verified_in_this_report"] is False
    assert result["global_enable_authorized"] is False
    assert result["strict_csrf_enforce_installed"] is False
    assert result["remaining_unqualified_route_count"] > 0
    assert result["status"] == "BLOCKED_INCOMPLETE_RUNTIME_CLEARANCE"


def test_590_gap_counts_are_complete_disjoint_and_deterministic():
    plan = gap.build()
    repeat = gap.build()
    assert plan == repeat
    assert plan["status"] == "BLOCKED_SOURCE_ONLY_NOT_GLOBAL_CLEARANCE"
    assert plan["strict_csrf_enforcement_change_authorized"] is False
    assert plan["runtime_verified_by_this_report"] is False
    assert (plan["source_witness_candidates"]
            + plan["remaining_without_source_witness"]
            == plan["total_unsafe_routes"])
    assert sum(b["unqualified_routes"] for b in plan["remaining_route_workstreams"]) == plan[
        "remaining_without_source_witness"
    ]
    assert plan["remaining_without_source_witness"] > 0
    assert plan["manual_review_queue_size"] >= 0
    assert all(row["global_enforcement_cleared"] is False
               for row in plan["unqualified_routes"] + plan["candidate_routes"])
    keys1 = {(row["method"], row["path"]) for row in plan["unqualified_routes"]}
    keys2 = {(row["method"], row["path"]) for row in plan["candidate_routes"]}
    assert not keys1.intersection(keys2)
    assert len(keys1) + len(keys2) == plan["total_unsafe_routes"]
    assert [(-batch["unqualified_routes"], batch["workstream"])
            for batch in plan["remaining_route_workstreams"]] == sorted(
        (-batch["unqualified_routes"], batch["workstream"])
        for batch in plan["remaining_route_workstreams"]
    )


def test_590_evidence_manifest_is_exact_and_excludes_unqualified_routes():
    plan = gap.build()
    manifest = plan["source_witness_manifest"]
    assert len(manifest) == 6
    assert {(r["method"], r["path"]) for r in manifest} == set(gap.EVIDENCE_MODULES)
    assert all(r["runtime_verified_by_this_report"] is False for r in manifest)
    assert {r["module"] for r in manifest} == {
        "tests/browser/test_csrf_bulk587.py",
        "tests/browser/test_csrf_multipart588.py",
    }
    routes = {(r["method"], r["path"]) for r in plan["candidate_routes"]}
    assert set(gap.EVIDENCE_MODULES) <= routes


def test_590_missing_full_gate_fails_closed(monkeypatch):
    original = gap.EVIDENCE_MODULES
    monkeypatch.setattr(gap, "EVIDENCE_MODULES", {
        **original, ("POST", "/coas/new"): "tests/browser/not-a-full-gate.py"
    })
    try:
        gap.build()
    except ValueError as error:
        assert "Missing browser witness" in str(error)
    else:
        raise AssertionError("Nonexistent witness cannot be accepted")


def test_590_cli_emits_parseable_json_without_clearance():
    script = ROOT / "scripts/tracker_csrf_gap_plan590.py"
    ast.parse(script.read_text())
    run = subprocess.run([sys.executable, str(script), "--json"],
                         cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stdout + run.stderr
    payload = json.loads(run.stdout)
    assert payload["strict_csrf_enforcement_change_authorized"] is False
    assert payload["status"] == "BLOCKED_SOURCE_ONLY_NOT_GLOBAL_CLEARANCE"


def test_590_production_policy_and_full_release_unchanged():
    source = (ROOT / "app/csrf_enforcement520.py").read_text()
    release = (ROOT / "scripts/tracker-release.sh").read_text()
    assert 'os.environ.get("TRACKER_CSRF_ENFORCE", "0") == "1"' in source
    assert 'timeout 600 bash "$QA/scripts/tracker-browser-qualify.sh"' in release
    assert "=== COMPLETE REGRESSION SUITE ===" in release
