"""Release 706 guarded issue 9/10 runtime evidence, source-only tests.

All tests are offline, synthetic, and never run Chromium or mutate Tracker.
"""
from pathlib import Path

import pytest

from scripts import tracker_browser_os_replay706 as runtime
from scripts import tracker_csrf_survey706 as csrf

ROOT = Path(__file__).resolve().parents[1]


def test_706_browser_cli_is_opt_in(capsys):
    assert runtime.main([]) == 0
    assert "NO_ACTION_EXPLICIT_MODE_REQUIRED" in capsys.readouterr().out
    assert csrf.main([]) == 0
    assert "NO_ACTION_REQUIRE_EXPLICIT_EXECUTE" in capsys.readouterr().out


@pytest.mark.parametrize("path", (
    Path("/tmp/not-private/data"),
    Path("/opt/tracker/data"),
    Path("/tmp/tracker706-csrf-probe.bad/path"),
))
def test_706_csrf_rejects_any_non_private_test_data(path):
    with pytest.raises(csrf.SurveyError):
        csrf.private_data(path)


def test_706_never_accepts_arbitrary_unverified_chromium_binary(tmp_path):
    binary = tmp_path / "fake"
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o700)
    with pytest.raises(runtime.EvidenceError, match="trusted"):
        runtime.safe_binary(binary)


def test_706_browser_manifest_exact_binary_library_and_os_comparison():
    base = {
        "chromium_executable": "/root/.cache/ms-playwright/example/chrome",
        "chromium_sha256": "a" * 64,
        "chromium_version": "123.0.0",
        "os_release_sha256": "b" * 64,
        "libc": ("glibc", "2.40"),
        "kernel": "6.x",
        "machine": "x86_64",
        "shared_libraries": {
            "libc.so.6": {"resolved": "/lib/libc.so.6", "sha256": "c" * 64},
        },
        "url_scope": "data:text/html only",
    }
    runtime.compare_browser(base, dict(base))
    for field in (
        "chromium_executable", "chromium_sha256", "chromium_version",
        "os_release_sha256", "libc", "kernel", "machine",
        "shared_libraries", "url_scope",
    ):
        bad = dict(base)
        bad[field] = "unexpected"
        with pytest.raises(runtime.EvidenceError):
            runtime.compare_browser(base, bad)


def test_706_source_builds_exact_92_signed_csrf_survey_without_clearance():
    source = (ROOT / "scripts/tracker_csrf_survey706.py").read_text()
    for required in (
        "EXPECTED_UNMAPPED = 92",
        "EXPECTED_MANUAL = 155",
        "EXPECTED_SESSION = 6",
        "registered_writes, sample_path",
        "with TestClient(app, raise_server_exceptions=False) as client:",
        'headers={HEADER_NAME: token}',
        'report = signed.headers.get(REPORT_HEADER)',
        '"positive_signed_persisted_lifecycles_qualified_by_this_report": 0',
        '"global_strict_csrf_authorized": False',
        "CSRF_706_GLOBAL_ENFORCEMENT=BLOCKED",
        "CSRF_706_SIGNED_PERSISTED_WRITES_CERTIFIED=0",
    ):
        assert required in source, required
    for forbidden in (
        'subprocess.run(', 'os.system(', 'TRACKER_CSRF_ENFORCE=0',
        'status_code=200', 'global_strict_csrf_authorized": True',
    ):
        assert forbidden not in source


def test_706_binary_replay_has_two_fresh_envs_no_download_and_real_rollback():
    source = (ROOT / "scripts/tracker_browser_os_replay706.py").read_text()
    for expected in (
        "replay.assert_network_isolated()",
        "replay.verify_approved_wheels(wheels)",
        "replay.replay_pass(",
        "for number in (1, 2):",
        "browser = pw.chromium.launch(",
        'executable_path=str(binary)',
        'Path("/etc/os-release")',
        '["/usr/bin/ldd", str(binary)]',
        'shutil.copytree(venv, snapshot, symlinks=True)',
        '"uninstall",',
        '"--yes", "packaging"',
        "shutil.rmtree(venv)",
        "compare_browser(baseline, result)",
        'lock.verify(wheels / "wheelhouse", wheels / "receipts")',
        "DEPENDENCY_706_OFFLINE_CHROMIUM_PASS_",
        "DEPENDENCY_706_DISPOSABLE_ROLLBACK=PASSED",
        "DEPENDENCY_706_BROWSER_OS_LOCAL_REPRO=PASSED_SAME_HOST",
        "DEPENDENCY_706_ISSUE10=STILL_BLOCKED_INDEPENDENT_PROVENANCE_AND_LIVE_ROLLBACK",
    ):
        assert expected in source, expected
    for forbidden in (
        '"download"', '"urlopen"', 'chromium.install(', 'requests.get(',
        'subprocess.run(["pip", "install"',
        "TRACKER_CSRF_ENFORCE=1",
        "/etc/tracker.env",
    ):
        assert forbidden not in source


def test_706_guarded_worker_exact_branch_no_network_and_no_prod():
    shell = (ROOT / "scripts/tracker-issue-review706.sh").read_text()
    for expected in (
        "BASE=4c084ade9063b3b01c2de0a4a055d2e23470b2a3",
        "REF=release/706-csrf-runtime-and-browser-repro",
        'readlink /proc/self/ns/net',
        'readlink /proc/1/ns/net',
        'git merge-base --is-ancestor "$BASE" "$TARGET"',
        'git worktree add --detach "$QA" "$TARGET"',
        'git -C "$APP" worktree remove --force "$QA"',
        'tracker705-dependency-preview.lock',
        'tracker706-issue-review.lock',
        'bash scripts/tracker-release-scoped706.sh "$PY"',
        'TRACKER_CSRF_ENFORCE=1',
        'scripts/tracker_csrf_survey706.py',
        'scripts/tracker_browser_os_replay706.py',
        'RELEASE_706_ISSUE9=BLOCKED_PENDING_SIGNED_SUCCESSFUL_BROWSER_LIFECYCLES',
        'RELEASE_706_ISSUE10=BLOCKED_PENDING_INDEPENDENT_ORIGIN_OS_AND_LIVE_ROLLBACK',
    ):
        assert expected in shell, expected
    assert 'git fetch' not in shell
    assert 'git merge --ff-only' not in shell
    assert 'systemctl restart tracker' not in shell
    assert 'ssh ' not in shell
    assert 'rm -rf -- "$RUN" "$SURVEY"' in shell


def test_706_only_changed_paths_and_source_scoped_gate():
    gate = (ROOT / "scripts/tracker-release-scoped706.sh").read_text()
    shell = (ROOT / "scripts/tracker-issue-review706.sh").read_text()
    assert 'bash scripts/tracker-release-scoped705.sh "$PY"' in gate
    assert "tests/test_release706_gates.py" in gate
    assert "RELEASE_706_SOURCE_SCOPED=PASSED" in gate
