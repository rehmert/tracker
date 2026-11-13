"""Release 593: all PK source candidates tied to signed full Chromium tests."""
from __future__ import annotations

import ast
import re
from pathlib import Path

from scripts import tracker_csrf_gap_plan590 as gap
from scripts import tracker_csrf_readiness588 as readiness

ROOT = Path(__file__).resolve().parents[1]
BROWSER = ROOT / "tests/browser/test_strict_csrf521.py"
ROUTER = ROOT / "app/routers/pk.py"
NEW_593 = frozenset({
    ("POST", "/pk/scenarios/{sid}/doses/create-batch-checked"),
    ("POST", "/pk/workspace/{sid}/edit-dose"),
    ("POST", "/pk/workspace/{sid}/revisions/{audit_id}/restore"),
    ("POST", "/pk/what-if/preview"),
    ("POST", "/pk/what-if/multi-preview"),
    ("POST", "/pk/what-if/save"),
    ("POST", "/pk/workbench/{pid}"),
    ("POST", "/pk/library/{pid}"),
    ("PUT", "/pk/library/{pid}/{experiment_id}"),
    ("POST", "/pk/library/{pid}/compare"),
    ("DELETE", "/pk/library/{pid}/{experiment_id}"),
})


def test_593_full_pk_route_inventory_is_source_candidate_not_runtime_clearance():
    source = ROUTER.read_text()
    declarations = re.findall(
        r'@router[.](post|put|patch|delete)[(]\s*"([^"]+)"', source
    )
    actual = {(method.upper(), "/pk" + path) for method, path in declarations}
    candidates = {key for key in readiness.BROWSER_WITNESS_CANDIDATES
                  if key[1].startswith("/pk/")}
    mapped = {key for key in gap.EVIDENCE_MODULES
              if key[1].startswith("/pk/")}
    assert len(actual) == len(candidates) == len(mapped) == 31
    assert actual == candidates == mapped
    assert NEW_593 <= actual
    report = readiness.report()
    assert report["missing_witness_source_routes"] == []
    assert report["global_enable_authorized"] is False
    assert report["strict_csrf_enforce_installed"] is False
    assert report["status"] == "BLOCKED_INCOMPLETE_RUNTIME_CLEARANCE"
    plan = gap.build()
    assert plan["source_witness_candidates"] == 50
    assert plan["remaining_without_source_witness"] == 94
    assert len(plan["source_witness_manifest"]) == 37
    assert not any(r["workstream"] == "pk" for r in plan["unqualified_routes"])
    assert plan["strict_csrf_enforcement_change_authorized"] is False
    assert plan["runtime_verified_by_this_report"] is False


def test_593_three_positive_browser_workflows_cover_new_routes_and_fail_closed():
    source = BROWSER.read_text()
    ast.parse(source)
    tests = (
        "test_593_pk_checked_batch_guarded_edit_and_revision_restore",
        "test_593_pk_what_if_preview_multi_and_save",
        "test_593_pk_workbench_and_experiment_library_signed",
    )
    for test in tests:
        assert source.count("def " + test + "(") == 1
    assert source.count('@pytest.mark.parametrize("scheme", ("http", "https"))') >= 3
    for operation in (
        'create-batch-checked', 'edit-dose', '/restore',
        '/pk/what-if/preview', '/pk/what-if/multi-preview',
        '/pk/what-if/save', '/pk/workbench/', '/pk/library/',
        '/compare',
    ):
        assert operation in source, operation
    for evidence in (
        'assert result["csrf"] == "valid"',
        'assert response.status == 403',
        'pending.value.request.all_headers().get("x-tracker-csrf") == token',
        'assert len(saved()["doses"]) == 2',
        'assert restored["audit_source"] == audit_id',
        'assert not any(d["amount_mg"] == 5.0',
        'assert multi["series"][0]["dose_count"] > 0',
        'assert len(saved["revisions"]) == 1',
        'assert len(result["experiments"]) == 2',
        'assert listing() == []',
    ):
        assert evidence in source, evidence
    assert 'DATA.parent.parent == Path("/tmp").resolve()' in source
    assert 'TRACKER_TEST_ISOLATED' in source
    assert 'TRACKER_TEST_STRICT_CSRF' in source


def test_593_no_runtime_csrf_policy_or_full_browser_gate_modification():
    policy = (ROOT / "app/csrf_enforcement520.py").read_text()
    assert 'os.environ.get("TRACKER_CSRF_ENFORCE", "0") == "1"' in policy
    runner = (ROOT / "scripts/tracker-browser-qualify.sh").read_text()
    _, strict = runner.split("# Release 521: a second browser gate", 1)
    assert strict.count("tests/browser/test_strict_csrf521.py") == 1
    assert runner.count("ISOLATED_STRICT_CSRF_BROWSER=PASSED") == 1
    assert "csrf-batch589" in runner
