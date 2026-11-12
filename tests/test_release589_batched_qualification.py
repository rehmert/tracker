"""Release 589: one pinned targeted batch, without weakening full release gates."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
QUALIFIER = ROOT / "scripts/tracker-browser-qualify.sh"
PREFLIGHT = ROOT / "scripts/tracker-targeted-preflight584.sh"
RELEASE = ROOT / "scripts/tracker-release.sh"


def test_589_strict_batch_is_allowlisted_and_runs_both_modules_fail_closed():
    runner = QUALIFIER.read_text()
    source = PREFLIGHT.read_text()
    assert '"$TARGETED_MODULE" == csrf-batch589' in runner
    assert '"$MODULE" == csrf-batch589' in source
    assert "TARGETED_CSRF_BATCH589=PASSED" in runner
    assert "TARGETED_CSRF_BATCH589_SCOPE=BULK587_MULTIPART588_ONLY_NOT_FULL_QUALIFICATION" in runner
    batch = runner.split('# Release 589: one explicit fail-closed batch', 1)[1].split(
        '# Combined Release 587–588: isolate bulk inventory browser writes', 1
    )[0]
    assert batch.count('run_isolated_browser_module') == 2
    assert batch.count('tests/browser/test_csrf_bulk587.py') == 1
    assert batch.count('tests/browser/test_csrf_multipart588.py') == 1
    assert batch.index('tests/browser/test_csrf_bulk587.py') < batch.index(
        'tracker_csrf_runtime_report587.py'
    ) < batch.index('tests/browser/test_csrf_multipart588.py') < batch.index(
        'TARGETED_CSRF_BATCH589=PASSED'
    )
    assert 'exit 0' in batch
    assert 'ISOLATED_STRICT_CSRF_BROWSER=PASSED' not in batch
    assert 'DRY_RUN=PASSED' not in batch
    for name in (QUALIFIER, PREFLIGHT):
        check = subprocess.run(['bash', '-n', str(name)], capture_output=True)
        assert check.returncode == 0, (name, check.stderr)


def test_589_full_browser_and_release_gates_remain_unchanged():
    runner = QUALIFIER.read_text()
    full = RELEASE.read_text()
    assert runner.count('if [[ "$MODE" == full ]]; then') == 4
    assert runner.count('ISOLATED_STRICT_CSRF_BROWSER=PASSED') == 1
    assert "tests/browser/test_csrf_bulk587.py" in runner
    assert "tests/browser/test_csrf_multipart588.py" in runner
    assert 'timeout 600 bash "$QA/scripts/tracker-browser-qualify.sh"' in full
    assert "=== COMPLETE REGRESSION SUITE ===" in full
    assert "=== Verified source and data recovery backup ===" in full


def test_589_secondary_checks_do_not_use_installed_database():
    source = (ROOT / "tests/test_release589_secondary_strict_csrf.py").read_text()
    assert "secondary_integration440_support" in source
    assert "test_589_secondary_account_signed_https_mutation" in source
    assert 'monkeypatch.setenv("TRACKER_CSRF_ENFORCE", "1")' in source
    assert "Sec-Fetch-Site" in source
    assert '"cross-site"' in source
    assert "TestClient(https_client.app" in source
    assert "http://tracker.test" in source
    assert "/opt/tracker/data" not in source
    assert "PROD" not in source
