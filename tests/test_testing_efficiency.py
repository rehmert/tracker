"""Ensure optimization does not weaken deployment safety."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def release_source():
    return (
        ROOT / "scripts/tracker-release.sh"
    ).read_text()


def runner_source():
    return (
        ROOT / "scripts/tracker-test.sh"
    ).read_text()


def test_release_runs_complete_suite_once():
    source = release_source()

    assert source.count('"$PY" -m pytest') == 1
    assert "--durations=20 tests" in source
    assert "timeout 1200" in source


def test_critical_suites_still_collected():
    source = release_source()

    for name in (
        "test_navigation_http_smoke.py",
        "test_restore_verification.py",
        "test_dose_sequential_workflow.py",
        "test_protocol_inventory_handoff.py",
    ):
        assert (ROOT / "tests" / name).exists()
        assert "--ignore=tests/" + name not in source


def test_test_runner_modes():
    source = runner_source()

    for name in (
        "--quick",
        "--full",
        "--profile",
        "--one",
    ):
        assert name in source


def test_test_runner_isolation():
    source = (
        ROOT / "tests/conftest.py"
    ).read_text()

    assert "TemporaryDirectory" in source
    assert 'os.environ["TRACKER_DATA_DIR"]' in source


def test_browser_test_exclusions():
    source = runner_source()

    assert "--ignore=tests/browser" in source
    assert "--ignore=tests/test_bulk_vial_browser.py" in source


def test_recovery_and_rollback_preserved():
    source = release_source()

    for marker in (
        "tracker-restore-verify.py",
        "tracker-deployment-guard.py",
        "tracker-runtime-smoke.py",
        "create_backup(",
        "systemctl is-active",
        "git diff --check",
        "merge --ff-only",
        "reset --hard",
        "MemoryMax=1G",
    ):
        assert marker in source
