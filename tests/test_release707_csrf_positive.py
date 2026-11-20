"""Release 707: route reconciliation and real-browser qualification wiring.

These source-only checks cannot authorize global strict-CSRF enforcement.
They pin twelve previously unqualified write routes to a separate real
Chromium HTTP/HTTPS positive lifecycle with DB state and forgery witnesses.
"""
import ast
from pathlib import Path

from scripts.tracker_csrf_reconcile627 import build

ROOT = Path(__file__).resolve().parents[1]
BROWSER = ROOT / "tests/browser/test_csrf_regimen_catalog707.py"
RUNNER = ROOT / "scripts/tracker-browser-qualify.sh"
WORKER = ROOT / "scripts/tracker-csrf-positive707.sh"


def declared_routes(name: str):
    tree = ast.parse(BROWSER.read_text(encoding="utf-8"))
    matching = [
        item for item in tree.body if isinstance(item, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == name for t in item.targets)
    ]
    assert len(matching) == 1
    node = matching[0].value
    assert isinstance(node, ast.Call)
    assert isinstance(node.func, ast.Name) and node.func.id == "frozenset"
    assert len(node.args) == 1
    return set(ast.literal_eval(node.args[0]))


def test_707_twelve_exact_unqualified_routes_have_real_positive_witnesses():
    report = build()
    remaining = {(r["method"], r["path"]) for r in report["remaining_routes"]}
    regimen = declared_routes("REGIMEN_ROUTES")
    catalog = declared_routes("CATALOG_ROUTES")
    assert len(regimen) == 9
    assert len(catalog) == 3
    assert len(regimen | catalog) == 12
    assert regimen.isdisjoint(catalog)
    assert regimen | catalog <= remaining
    assert report["remaining_without_positive_source_witness"] == 92
    assert not report["global_enforcement_authorized"]


def test_707_real_browser_tests_verify_403_no_mutation_and_signed_db_effect():
    source = BROWSER.read_text(encoding="utf-8")
    for marker in (
        'TRACKER_TEST_ISOLATED") == "1"',
        'TRACKER_TEST_STRICT_CSRF") == "1"',
        'DATA.parent.parent == Path("/tmp").resolve()',
        'tracker-browser-qa[.][A-Za-z0-9_]{8}',
        'window.trackerCsrfToken?.()',
        'cookie["value"] == token',
        'denial.status == 403',
        'forgery.status == 403',
        'assert state() == before',
        'accepted.status == 303',
        'accepted.headers.get("x-tracker-csrf-report") == "valid"',
        'assert seen == REGIMEN_ROUTES',
        'assert seen == CATALOG_ROUTES',
        '@pytest.mark.parametrize("scheme", ("http", "https"))',
        'FROM regimen_items635',
        'FROM regimen_schedules635',
        'FROM regimen_entries635',
        'FROM coa_test_type_catalog652',
    ):
        assert marker in source, marker
    for unsafe in (
        '/opt/tracker/data/tracker.db', 'DROP TABLE', 'TRACKER_CSRF_ENFORCE=0',
        'status in (200, 303)', 'return True  # no write',
    ):
        assert unsafe not in source


def test_707_qualifier_runs_exact_module_in_full_gate_once_and_targeted_mode():
    runner = RUNNER.read_text(encoding="utf-8")
    module = "tests/browser/test_csrf_regimen_catalog707.py"
    full_start = runner.index('echo "=== STRICT CSRF CORE TESTS PASSED ==="')
    full_end = runner.index(
        'if [[ "$MODE" == targeted && "$TARGETED_MODULE" == csrf-positive707 ]]'
    )
    assert runner[full_start:full_end].count(module) == 1
    assert "STRICT_CSRF_707_TWELVE_POSITIVE_LIFECYCLES=PASSED" in runner[
        full_start:full_end
    ]
    assert runner.count(module) == 2
    assert 'TARGETED_MODULE" == csrf-positive707' in runner
    assert "TARGETED_CSRF_707_TWELVE_SIGNED_LIFECYCLES=PASSED" in runner
    assert "TARGETED_CSRF_707_SCOPE=TWELVE_REAL_WRITES_NOT_FULL_CSRF_CLEARANCE" in runner
    assert 'ISOLATED_STRICT_CSRF_BROWSER=PASSED' in runner


def test_707_dev_worker_requires_exact_sha_disposable_source_and_no_prod():
    worker = WORKER.read_text(encoding="utf-8")
    for marker in (
        'BASE=4c084ade9063b3b01c2de0a4a055d2e23470b2a3',
        'REF=release/707-csrf-positive-lifecycles',
        'git merge-base --is-ancestor "$BASE" "$TARGET"',
        'git worktree add --detach "$QA" "$TARGET"',
        'git -C "$APP" worktree remove --force "$QA"',
        'tests/test_release707_csrf_positive.py',
        'scripts/tracker-browser-qualify.sh "$QA" "$PY" --targeted-strict csrf-positive707',
        'RELEASE_707_TARGETED_POSITIVE=PASSED_NOT_GLOBAL_CLEARANCE',
    ):
        assert marker in worker, marker
    assert 'git push' not in worker
    assert 'systemctl restart tracker' not in worker
    assert '/etc/tracker.env' not in worker
    assert 'TRACKER_CSRF_ENFORCE=1' not in worker
