"""Release 506: prove loadfile sharding preserves every original test body.

Fingerprints use the original Release 504 function/decorator source text and
include the original security assertions. They guard against accidental loss
of content during the test-only split, not against future intentional edits.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SUPPLY_MODULES = (
    "tests/test_secondary_supply_use439.py",
    "tests/test_secondary_supply_use_security439.py",
)

RECONCILIATION_MODULES = (
    "tests/test_secondary_reconciliation437.py",
    "tests/test_secondary_reconciliation_security437.py",
    "tests/test_secondary_reconciliation_conflicts437.py",
)

EXPECTED_SUPPLY_BODIES = {
    "test_needle_use_links_exact_dose_updates_stock_and_audit": "377b9699",
    "test_bac_water_linked_to_preparation_and_volume_cap": "ad86f302",
    "test_invalid_links_and_overdraw_cannot_mutate_stock": "2596c0c0",
    "test_replay_and_same_supply_reference_link_are_rejected": "2f33531b",
    "test_concurrent_supply_requests_cannot_overdraw": "dbe1e647",
    "test_accounts_have_independent_stock_and_escaped_labels": "17acadf3",
    "test_csrf_fetch_site_unauthenticated_and_flags": "fb570455",
    "test_worker_rejects_unknown_actions_and_paths": "2e1fd1a6",
    "test_parent_rejects_administrator_and_generic_operations": "c4490aa7",
    "test_source_middleware_is_narrow_and_gated": "e2844f42",
}

EXPECTED_RECONCILIATION_BODIES = {
    "test_reconciliation_report_is_read_only_private_and_shows_stock": "d491e2e7",
    "test_audited_metadata_and_one_way_discard_are_atomic": "f34ce0e5",
    "test_lifecycle_transition_guards_and_no_change_are_rejected": "911c9410",
    "test_duplicate_token_payload_conflict_and_stale_form": "ac5d3456",
    "test_stale_form_rejected_if_dose_inventory_changes": "1bb5efe5",
    "test_concurrent_corrections_reject_stale_snapshot": "441be5f4",
    "test_account_switch_and_html_escaping_protect_private_audit": "d1f0c488",
    "test_forged_fields_invalid_values_and_csrf_are_rejected": "2292717b",
    "test_disabled_flag_keeps_reconciliation_read_only_and_prod_denied": "8de8bdd3",
    "test_unauthenticated_and_admin_worker_identity_are_denied": "af740842",
    "test_private_worker_rejects_forged_operations": "5f29a48e",
    "test_middleware_exempts_only_the_gated_correction_form": "b76f893b",
}


def _fingerprint(source):
    """Stable FNV-1a over UTF-16LE source, matching Release 504 snapshot."""
    value = 2166136261
    for byte in source.encode("utf-16le"):
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return format(value, "08x")


def _test_bodies(path):
    source = (ROOT / path).read_text(encoding="utf-8")
    lines = source.splitlines()
    found = {}
    for node in ast.parse(source).body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        start = min(
            [node.lineno]
            + [decorator.lineno for decorator in node.decorator_list]
        )
        body = "\n".join(lines[start - 1:node.end_lineno]).rstrip()
        assert node.name not in found
        found[node.name] = _fingerprint(body)
    return found


def _combine(files):
    combined = {}
    for path in files:
        found = _test_bodies(path)
        assert not (combined.keys() & found.keys()), "Duplicate test name"
        combined.update(found)
    return combined


def test_506_all_439_and_437_test_bodies_remain_byte_identical():
    assert _combine(SUPPLY_MODULES) == EXPECTED_SUPPLY_BODIES
    assert _combine(RECONCILIATION_MODULES) == EXPECTED_RECONCILIATION_BODIES


def test_506_original_security_fixtures_are_isolated_and_unmodified():
    for module, number, flag in (
        ("scripts/secondary_supply_use439_support.py", "439",
         "TRACKER_SECONDARY_SUPPLY_USE439"),
        ("scripts/secondary_reconciliation437_support.py", "437",
         "TRACKER_SECONDARY_VIAL_CORRECTIONS437"),
    ):
        source = (ROOT / module).read_text(encoding="utf-8")
        for required in (
            "@pytest.fixture",
            'monkeypatch.setattr(config, "DATA_DIR", tmp_path)',
            'monkeypatch.setattr(config, "instance_label", lambda: "DEV")',
            'monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")',
            f'monkeypatch.setenv("{flag}", "1")',
            f'auth.bootstrap("operator", "administrator-secure-password-{number}")',
            'initialize_staged_workspace426(uid, tmp_path)',
            "stage_secondary_account427(",
            "for uid in (2, 3):",
            'host.mount("/secondary", preview_app)',
            'with TestClient(host, base_url="https://tracker.test") as client:',
            "yield client, tmp_path",
        ):
            assert required in source, (module, required)
    for path in (*SUPPLY_MODULES, *RECONCILIATION_MODULES):
        source = (ROOT / path).read_text(encoding="utf-8")
        assert " import browser, " in source, path
        assert not source.count("def browser("), path


def test_506_full_backend_collection_retains_loadfile_and_no_ignores():
    release = (ROOT / "scripts/tracker-release.sh").read_text(
        encoding="utf-8"
    )
    assert 'TEST_PYTEST_EXTRA=(-n "$WORKERS" --dist=loadfile)' in release
    for path in (*SUPPLY_MODULES, *RECONCILIATION_MODULES):
        assert f"--ignore={path}" not in release
    test_gate = (ROOT / "scripts/tracker-test-gate475.sh").read_text(
        encoding="utf-8"
    )
    assert "non-browser)" in test_gate
    assert "--ignore=tests/browser" in test_gate
    assert "tests/test_secondary_supply_use_security439.py" not in (
        "\n".join(
            line for line in release.splitlines()
            if "--ignore=" in line
        )
    )
