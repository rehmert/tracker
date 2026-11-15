"""Release 629 focused-gate scope: keep routine deployments focused.

Full backend and historical CSRF suites remain in the five-release
qualification path; this test protects against accidental reintroduction
of the historical security campaign into ordinary UI deployments.
"""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FOCUSED = ROOT / "scripts/tracker-focused-regression604.sh"
RELEASE = ROOT / "scripts/tracker-release.sh"


def _focused_modules():
    source = FOCUSED.read_text()
    return re.findall(r"^\s+(tests/[^ \n]+[.]py)\s*\\?$", source, re.M)


def test_629_routine_focused_gate_is_small_and_relevant():
    modules = _focused_modules()
    assert len(modules) == 20
    assert len(modules) == len(set(modules))
    assert all((ROOT / module).is_file() for module in modules)
    for required in (
        "tests/test_release_workflow.py",
        "tests/test_release604_preflight.py",
        "tests/test_release605_oom_guard.py",
        "tests/test_release627_inventory_health_filter.py",
        "tests/test_release628_pk_simplified.py",
        "tests/test_release629_qa_cadence.py",
        "tests/test_release629_focused_gate.py",
        "tests/test_pk_278_281.py",
    ):
        assert required in modules
    assert not any(
        "csrf" in module.lower() or "browser_qualification511" in module
        for module in modules
    )
    assert "tests/test_release595_food_vendor_lifecycle.py" not in modules
    assert "tests/test_release596_vendor_multipart_csv.py" not in modules


def test_629_full_security_and_rollback_gates_are_still_available():
    release = RELEASE.read_text()
    focus = FOCUSED.read_text()
    assert '10#$RELEASE_SEQUENCE % 5 == 0' in release
    assert 'QA_CADENCE_REASON="security-sensitive source or route changed"' in release
    assert 'timeout 600 bash "$QA/scripts/tracker-browser-qualify.sh" "$QA" "$PY"' in release
    assert 'timeout 1200 "$PY" -m pytest' in release
    assert 'MEMORY_PROPERTY="MemoryMax=16G"' in release
    assert 'create_backup(' in release
    assert 'tracker-restore-verify.py' in release
    assert 'tracker-runtime-smoke.py' in release
    assert 'TEST_PYTEST_EXTRA=(-n 16 --dist=loadfile)' in release
    assert '"$PY" -m pytest -n 16 --dist=loadfile' in focus
    assert "RELEASE_604_FOCUSED_PREFLIGHT=PASSED" in focus


def test_629_focused_shell_parses():
    result = subprocess.run(
        ["bash", "-n", str(FOCUSED)],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
