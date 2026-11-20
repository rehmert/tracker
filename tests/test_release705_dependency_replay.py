"""Release 705: no-network, independently isolated two-pass Python replays."""
from pathlib import Path

import pytest

from scripts import tracker_dependency_replay705 as replay


def test_705_offline_replay_requires_opt_in_without_touching_host(capsys):
    assert replay.main([]) == 0
    assert "DRY_RUN_ONLY_EXPLICIT_OPT_IN_REQUIRED" in capsys.readouterr().out
    with pytest.raises(SystemExit) as exc:
        replay.main(["--execute-disposable"])
    assert exc.value.code == 2


def test_705_pip_install_is_hash_locked_and_strictly_offline(tmp_path):
    command = replay.offline_install_args(
        tmp_path / "venv/bin/python",
        tmp_path / "wheelhouse", tmp_path / "requirements-hashes705.txt",
    )
    assert command[:6] == [
        str(tmp_path / "venv/bin/python"), "-B", "-m", "pip", "--isolated", "install"
    ]
    for flag in (
        "--no-index", "--no-input", "--no-cache-dir",
        "--only-binary=:all:", "--require-hashes", "--find-links",
        "--requirement",
    ):
        assert command.count(flag) == 1, flag
    assert command[command.index("--find-links") + 1] == str(tmp_path / "wheelhouse")
    assert command[command.index("--requirement") + 1] == str(
        tmp_path / "requirements-hashes705.txt"
    )
    for forbidden in (
        "download", "--index-url", "--extra-index-url", "--trusted-host",
        "--pre", "--upgrade", "--user", "--target",
    ):
        assert forbidden not in command


def test_705_replay_sandbox_env_excludes_credentials_and_all_indexes(tmp_path):
    env = replay.sandbox_env(
        tmp_path / "home", tmp_path / "data", tmp_path / "tmp", tmp_path / "source"
    )
    assert set(env) == {
        "HOME", "TMPDIR", "PATH", "LANG", "PYTHONNOUSERSITE",
        "PYTHONDONTWRITEBYTECODE", "PYTHONPATH", "TRACKER_DATA_DIR",
        "TRACKER_INSTANCE", "PIP_CONFIG_FILE", "PIP_NO_INDEX",
        "PIP_DISABLE_PIP_VERSION_CHECK", "PIP_NO_CACHE_DIR",
    }
    assert env["PIP_CONFIG_FILE"] == "/dev/null"
    assert env["PIP_NO_INDEX"] == "1"
    assert env["PYTHONNOUSERSITE"] == "1"
    assert env["TRACKER_INSTANCE"] == "DEV"
    assert env["TRACKER_DATA_DIR"] == str(tmp_path / "data")
    for key in ("PIP_INDEX_URL", "GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY",
                "TRACKER_PASS", "TRACKER_SECRET"):
        assert key not in env


def test_705_replay_rejects_shared_network_namespace(monkeypatch):
    monkeypatch.setattr(replay.os, "readlink", lambda _path: "net:[123]")
    with pytest.raises(replay.ReplayError, match="PrivateNetwork"):
        replay.assert_network_isolated()


def test_705_replay_accepts_separate_network_namespace(monkeypatch):
    monkeypatch.setattr(
        replay.os, "readlink",
        lambda path: "net:[123]" if path == "/proc/self/ns/net" else "net:[456]"
    )
    replay.assert_network_isolated()


def test_705_replay_refuses_unsafe_wheel_source_before_any_install(tmp_path):
    with pytest.raises(replay.ReplayError, match="exact private retained"):
        replay.verify_approved_wheels(tmp_path)


def test_705_double_install_is_independent_backend_and_no_download_by_source():
    root = Path(__file__).resolve().parents[1]
    src = (root / "scripts/tracker_dependency_replay705.py").read_text()
    shell = (root / "scripts/tracker-dependency-replay705.sh").read_text()
    assert 'for number in (1, 2):' in src
    assert 'venv = runroot / f"{name}-venv"' in src
    assert 'for part in ("home", "data", "tmp")' in src
    assert '[str(base_python), "-B", "-m", "venv", str(venv)]' in src
    assert 'offline_install_args(python, wheelhouse, requirements)' in src
    assert 'tracker_dependency_baseline569.py' in src
    assert '"--instance", "DEV"' in src
    assert '"pip", "--isolated", "check"' in src
    assert 'tests/test_csrf_all_registered_negative705.py' in src
    assert 'tests/test_release705_combined.py' in src
    assert 'tests/test_release627_csrf_reconciliation.py' in src
    assert 'DEPENDENCY_705_TWO_OFFLINE_REPLAYS=PASSED' in src
    assert 'lock.verify(wheels_root / "wheelhouse", wheels_root / "receipts")' in src
    assert 'DEPENDENCY_705_ISSUE10=BLOCKED_BROWSER_OS_ROLLBACK' in src
    assert 'DEPENDENCY_705_REPLAY_DISPOSABLE_ENVS_REMOVED=YES' in shell
    assert 'DEPENDENCY_705_REPLAY_SOURCE_GATE=PASSED' in shell
    assert 'DEPENDENCY_705_REPLAY_INSTALLED_BASELINE_PREFLIGHT=PASSED' in shell
    assert 'readlink /proc/self/ns/net' in shell
    assert 'readlink /proc/1/ns/net' in shell
    assert 'git worktree add --detach' in shell
    assert 'git -C "$APP" worktree remove --force' in shell
    assert 'rm -rf -- "$RUN"' in shell
    assert 'flock -n 9' in shell
    assert '--execute-disposable' in shell
    assert '--execute-disposable' in src
    assert 'git fetch' not in shell
    executable = "\n".join(
        line for line in shell.splitlines()
        if not line.lstrip().startswith("#")
    )
    for forbidden in (
        'pip download', 'pip install', 'systemctl restart',
        'TRACKER_CSRF_ENFORCE=1', 'git reset', '/etc/tracker.env',
        'tracker-release.sh', 'git push',
    ):
        assert forbidden not in executable
    for forbidden in (
        '"download"', '"urlopen"', '"requests"', '"playwright", "install"',
        '"systemctl"', '"restart"', 'TRACKER_CSRF_ENFORCE=1',
        '/etc/tracker.env', '"tracker-release.sh"',
    ):
        assert forbidden not in src


def test_705_replay_fixed_backend_module_inventory():
    assert replay.TEST_MODULES == (
        "tests/test_csrf_all_registered_negative705.py",
        "tests/test_release705_combined.py",
        "tests/test_release627_csrf_reconciliation.py",
        "tests/test_release569_dependency_baseline.py",
    )
    assert len(replay.TEST_MODULES) == len(set(replay.TEST_MODULES))
