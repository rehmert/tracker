"""Release CLI contract and HTTP navigation parser checks (offline)."""
import importlib.util
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-release.sh"
SPEC = importlib.util.spec_from_file_location(
    "tracker_live_smoke", ROOT / "scripts/tracker-runtime-smoke.py"
)
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


def test_release_shell_syntax():
    result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[:500]


def test_release_rejects_unpinned_or_invalid_inputs():
    for args in (
        [],
        ["--instance", "DEV", "--base", "bad", "--target", "bad", "--ref", "main"],
        ["--instance", "PROD", "--base", "a" * 40, "--target", "b" * 40,
         "--ref", "release/unsafe"],
    ):
        result = subprocess.run(
            ["bash", str(SCRIPT), *args], capture_output=True, text=True
        )
        assert result.returncode != 0
        assert len(result.stderr) < 1000


def test_release_safety_stages_exist():
    source = SCRIPT.read_text(encoding="utf-8")
    for marker in (
        "systemd-run", "MemoryMax=1G", "merge --ff-only",
        "worktree add --detach", "umask 022", "umask 077",
        "tracker-deployment-guard.py", "tracker-runtime-smoke.py",
        "tracker-restore-verify.py", "create_backup(",
        "INSTALLED=0", "reset --hard", "EXIT_STATUS=$code",
    ):
        assert marker in source


def test_critical_safety_tests_remain_in_full_suite():
    """All critical tests are collected by the complete suite.

    The optimized deployer executes the entire tests directory,
    not an independent, duplicate critical-test subset.
    """
    source = SCRIPT.read_text(encoding="utf-8")

    assert ' -m pytest -q ' in source
    assert '--durations=20 tests ' in source
    assert source.count('"$PY" -m pytest') == 1

    # Neither critical file may be excluded from collection.
    critical = (
        "test_navigation_http_smoke.py",
        "test_restore_verification.py",
    )
    for filename in critical:
        assert (ROOT / "tests" / filename).is_file()
        assert f"--ignore=tests/{filename}" not in source

    # Preserve the existing exclusions for browser-only tests.
    assert "--ignore=tests/browser" in source, marker


def test_live_sidebar_parser_does_not_follow_unrelated_links():
    document = (
        '<nav id="app-sidebar"><a href="/">Home</a>'
        '<a href="/vials?q=1">Vials</a></nav>'
        '<nav id="footer"><a href="/external">Other</a></nav>'
    )
    parser = runtime.Links()
    parser.feed(document)
    assert parser.paths == ["/", "/vials"]


def test_runtime_credentials_from_local_file(tmp_path):
    path = tmp_path / "tracker.env"
    path.write_text(
        "TRACKER_INSTANCE=PROD\nTRACKER_USER=operator\n"
        "TRACKER_PASS='two words'\n"
    )
    values = runtime.read_env(path)
    assert values == {
        "TRACKER_INSTANCE": "PROD",
        "TRACKER_USER": "operator",
        "TRACKER_PASS": "two words",
    }


def test_release_streams_logs_by_default_and_supports_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "FOLLOW=1" in source
    assert "--detach) FOLLOW=0" in source
    assert 'touch "$RUN/deployment.log"' in source
    assert 'tail -n +1 --follow=descriptor --pid="$pid" "$log"' in source
    assert 'follow_deployment_log "$UNIT" "$RUN/deployment.log"' in source
    assert "=== DEPLOYMENT FAILED" in source
