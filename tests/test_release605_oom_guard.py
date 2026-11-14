"""Release 605: source and isolated behavioral tests for memory-safe release gate.

Never invoke the live deployment CLI or alter runtime files.
"""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "scripts/tracker-release.sh").read_text(encoding="utf-8")
HELPER = (ROOT / "scripts/tracker-focused-regression604.sh").read_text(encoding="utf-8")


def test_605_parallel_release_preserves_full_gate_with_host_safe_limits():
    assert 'TEST_PYTEST_EXTRA=(-n 4 --dist=loadfile)' in SOURCE
    assert 'BACKEND_TEST_MODE=PARALLEL workers=4' in SOURCE
    assert 'MEMORY_PROPERTY="MemoryMax=2G"' in SOURCE
    assert 'MEMORY_PROPERTY="MemoryMax=1G"' in SOURCE
    assert "timeout 1200" in SOURCE
    assert '--durations=20 tests ' in SOURCE
    assert 'timeout 600 bash "$QA/scripts/tracker-browser-qualify.sh"' in SOURCE
    assert SOURCE.count('"$PY" -m pytest') == 1
    assert '--ignore=tests/browser' in SOURCE
    for filename in ("test_navigation_http_smoke.py",
                     "test_restore_verification.py",
                     "test_release605_oom_guard.py",
                     "test_release605_vendor_label_ux.py"):
        assert f"--ignore=tests/{filename}" not in SOURCE
    assert "tests/test_release605_vendor_label_ux.py" in HELPER
    assert "tests/test_release605_oom_guard.py" in HELPER
    assert "tests/test_test_benchmark.py" in HELPER
    assert "tests/test_prod_parallel_release508.py" in HELPER
    assert "tests/test_secondary440_shard_safety503.py" in HELPER
    assert "tests/test_release_workflow.py" in HELPER
    assert 'set -Eeuo pipefail' in HELPER
    for script in ("scripts/tracker-release.sh",
                   "scripts/tracker-focused-regression604.sh"):
        syntax = subprocess.run(["bash", "-n", str(ROOT / script)],
                                capture_output=True, text=True, timeout=15)
        assert syntax.returncode == 0, syntax.stderr


def _cleanup_status_guard():
    """Exact opening guard from the real cleanup; omit the separate FS operations."""
    start = SOURCE.index("cleanup() {")
    end = SOURCE.index(" # Release 577:", start)
    return SOURCE[start:end] + ' printf "FINAL_CODE=%s\\n" "$code"\n exit "$code"\n}\n'


def test_605_incomplete_normal_exit_is_a_failure_not_false_success():
    assert "QUALIFICATION_COMPLETE=0" in SOURCE
    assert "QUALIFICATION_COMPLETE=1" in SOURCE
    assert SOURCE.index('echo "Verified recovery archive: $ARCHIVE"') < (
        SOURCE.index("QUALIFICATION_COMPLETE=1")
    )
    assert "trap 'exit 143' TERM" in SOURCE
    assert "trap 'exit 130' INT" in SOURCE
    guard = _cleanup_status_guard()
    for complete, expected_status in ((0, 1), (1, 0)):
        program = (
            "set -uo pipefail\n"
            + f"QUALIFICATION_COMPLETE={complete}\n"
            + guard
            + "trap cleanup EXIT\nexit 0\n"
        )
        result = subprocess.run(["bash", "-c", program],
                                capture_output=True, text=True, timeout=15)
        assert result.returncode == expected_status, result.stderr
        assert f"FINAL_CODE={expected_status}" in result.stdout
        if complete == 0:
            assert "without completing qualification" in result.stderr
        else:
            assert "without completing qualification" not in result.stderr
