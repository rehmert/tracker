"""Release 508: parallel backend regression gates are available on PROD too.

These contracts cover the guarded release script without requiring a live
Tracker host, privileged systemd commands, or a production database.
"""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/tracker-release.sh"


def _source():
    return RUNNER.read_text(encoding="utf-8")


def test_508_release_script_remains_valid_bash():
    result = subprocess.run(
        ["bash", "-n", str(RUNNER)], capture_output=True, text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_508_prod_and_dev_share_parallel_eligibility():
    source = _source()

    assert 'TEST_PYTEST_EXTRA=(-n 16 --dist=loadfile)' in source
    assert 'BACKEND_TEST_MODE=PARALLEL workers=16' in source
    assert "import xdist" in source
    assert 'fail "pytest-xdist missing; serial fallback prohibited"' in source
    assert 'TEST_PYTEST_EXTRA=()' not in source
    assert 'BACKEND_TEST_MODE=SERIAL reason=' not in source

    assert '[[ "$INSTANCE" == DEV && "$SERIAL_TESTS" == 0 ]]' not in source
    assert '[[ "$INSTANCE" == PROD && "$SERIAL_TESTS" == 0 ]]' not in source
    assert 'verify_prod_approval' in source


def test_508_prod_parallel_has_bounded_memory_and_override_retains_serial():
    source = _source()
    assert '--serial-tests) fail "Serial testing prohibited"' in source
    assert '[[ "$SERIAL_TESTS" == 0 ]]' in source
    assert 'BACKEND_TEST_MODE=SERIAL reason=' not in source
    assert 'MEMORY_PROPERTY="MemoryMax=16G"' in source
    assert 'systemd-run --unit="$UNIT" --collect --property="$MEMORY_PROPERTY"' in source
    assert 'worker "$@"' in source
    assert 'if [[ "$INSTANCE" == PROD ]]; then' in source
    assert '[[ "$REF" == main && "$(g rev-parse origin/main)" == "$TARGET" ]]' in source
    assert '/usr/local/sbin/tracker-verify-dev-approval' in source


def test_508_full_suite_isolated_and_recovery_guards_unchanged():
    source = _source()
    assert source.count('"$PY" -m pytest') == 1
    assert 'timeout 1200 "$PY" -m pytest' in source
    assert '"${TEST_PYTEST_EXTRA[@]}" --durations=20 tests' in source
    assert 'export TRACKER_DATA_DIR="$RUN/test-data" PYTHONPATH="$QA"' in source
    assert 'g worktree add --detach "$QA" "$TARGET"' in source
    assert 'tracker-browser-qualify.sh' in source
    assert 'tracker-restore-verify.py' in source
    assert 'tracker-runtime-smoke.py' in source
    assert 'g merge --ff-only "$TARGET"' in source
    assert 'g reset --hard "$BASE"' in source
    assert 'systemctl is-active --quiet tracker' in source
    for marker in (
        '--ignore=tests/test_navigation_http_smoke.py',
        '--ignore=tests/test_restore_verification.py',
        '--ignore=tests/test_secondary_private_workflow440.py',
        '--ignore=tests/test_secondary_integration440.py',
    ):
        assert marker not in source
