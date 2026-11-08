"""Release 503: guard the safe test-only xdist sharding of secondary gates.

The lengthy full private workflow is separate from readiness and fail-closed
security tests so xdist --dist=loadfile can schedule independent work. These
checks prevent an inadvertent loss of coverage in future reorganizations.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "tests/test_secondary_integration440.py"
WORKFLOW = ROOT / "tests/test_secondary_private_workflow440.py"
HELPERS = ROOT / "scripts/secondary_integration440_support.py"
ACCEPTANCE = ROOT / "scripts/tracker-test-gate475.sh"
RELEASE = ROOT / "scripts/tracker-release.sh"


def _test_names(source: Path) -> set[str]:
    tree = ast.parse(source.read_text(encoding="utf-8"))
    return {
        node.name for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


def test_503_secondary440_security_gates_stay_in_independent_test_files():
    assert _test_names(WORKFLOW) == {
        "test_full_private_browser_workflow_with_audits_and_no_cross_account_data",
    }
    assert _test_names(READINESS) == {
        "test_authenticated_readiness_matches_every_runtime_flag",
        "test_gateway_emergency_lockdown_denies_every_preview_route",
        "test_revoked_sessions_and_tampered_workspace_fail_closed",
        "test_prod_and_master_disable_all_readiness",
        "test_no_query_params_and_readiness_never_changes_private_records",
    }

    # The explicit security acceptance command is not a recursive pytest
    # discovery: it MUST name the separated workflow file.
    script = ACCEPTANCE.read_text(encoding="utf-8")
    assert "tests/test_secondary_integration440.py" in script
    assert "tests/test_secondary_private_workflow440.py" in script

    runner = RELEASE.read_text(encoding="utf-8")
    assert "TEST_PYTEST_EXTRA=(-n \"$WORKERS\" --dist=loadfile)" in runner
    assert "--ignore=tests/test_secondary_private_workflow440.py" not in runner
    assert "--ignore=tests/test_secondary_integration440.py" not in runner


def test_503_secondary440_shared_setup_remains_isolated_and_fail_closed():
    source = HELPERS.read_text(encoding="utf-8")
    assert '@pytest.fixture' in source
    for marker in (
        'monkeypatch.setattr(config, "DATA_DIR", tmp_path)',
        'monkeypatch.setattr(config, "instance_label", lambda: "DEV")',
        'auth.bootstrap("operator", "administrator-secure-password-440")',
        'initialize_staged_workspace426(uid, tmp_path)',
        'stage_secondary_account427(',
        'host.mount("/secondary", preview_app)',
        'with TestClient(host, base_url="https://tracker.test") as client:',
        'def _login(',
        'def _post_form(',
        'assert result.status_code == 303',
        'def _counts(',
    ):
        assert marker in source, marker

    workflow = WORKFLOW.read_text(encoding="utf-8")
    for marker in (
        'all(value == 0 for value in _counts(root, 3).values())',
        'assert not (root / "tracker.db").exists()',
        'SELECT action FROM change_audit ORDER BY id',
        'secret not in page.text',
        '"secondary_correction437"',
    ):
        assert marker in workflow, marker
