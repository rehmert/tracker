"""Release 570: offline safety tests for a disposable fresh dependency replay.

These tests never download wheels/Chromium, alter the installed venv or launch
the real full backend/browser suite.
"""
import hashlib
import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/tracker_freshenv570.py"


@pytest.fixture
def tool():
    spec = importlib.util.spec_from_file_location("freshenv570", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_dry_run_never_downloads_or_mutates(monkeypatch, tool, capsys):
    monkeypatch.setattr(tool, "preflight", lambda: "a" * 40)
    monkeypatch.setattr(
        tool, "execute", lambda *_args, **_kwargs: pytest.fail("Executed without opt-in")
    )
    assert tool.main([]) == 0
    captured = capsys.readouterr().out
    assert "DRY_RUN=PASSED" in captured
    assert "--execute required" in captured


def test_explicit_execute_passes_pinned_sha_and_retain_flag(tool, monkeypatch):
    phases = []
    monkeypatch.setattr(tool, "preflight", lambda: phases.append("preflight") or "b" * 40)
    monkeypatch.setattr(
        tool, "execute",
        lambda sha, *, retain: phases.append(("execute", sha, retain))
    )
    assert tool.main(["--execute", "--retain-artifacts"]) == 0
    assert phases == ["preflight", ("execute", "b" * 40, True)]


def test_retain_requires_explicit_execute(tool):
    with pytest.raises(SystemExit) as err:
        tool.main(["--retain-artifacts"])
    assert err.value.code == 2


def test_sandbox_env_never_propagates_root_secrets(tool, tmp_path):
    env = tool.env_for_sandbox(
        tmp_path / "home", tmp_path / "source", tmp_path / "data"
    )
    assert env["HOME"] == str(tmp_path / "home")
    assert env["TRACKER_DATA_DIR"] == str(tmp_path / "data")
    assert env["PYTHONPATH"] == str(tmp_path / "source")
    assert env["TRACKER_INSTANCE"] == "DEV"
    for unsafe in ("TRACKER_PASS", "PIP_INDEX_URL", "GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY"):
        assert unsafe not in env
    assert env["PYTHONNOUSERSITE"] == "1"


def test_browser_runner_only_changes_temporary_copy(tool, tmp_path):
    source = tmp_path / "source"
    scripts = source / "scripts"
    scripts.mkdir(parents=True)
    original = scripts / "tracker-browser-qualify.sh"
    original.write_text(
        "env -i HOME=/root bash first\n"
        "env -i HOME=/root bash second\n"
        "env -i HOME=/root bash third\n"
        "env -i HOME=/root bash fourth\n"
        'echo "ISOLATED_STRICT_CSRF_BROWSER=PASSED"\n',
        encoding="utf-8",
    )
    home = tmp_path / "sandbox-home"
    output = tmp_path / "temporary.sh"
    before = original.read_bytes()
    tool.temporary_browser_runner(source, home, output)
    assert original.read_bytes() == before
    assert "HOME=/root" not in output.read_text(encoding="utf-8")
    assert output.read_text(encoding="utf-8").count(f"HOME={home}") == 4


def test_browser_runner_refuses_changed_security_contract(tool, tmp_path):
    source = tmp_path / "source"
    scripts = source / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "tracker-browser-qualify.sh").write_text(
        "env -i HOME=/root echo hello\n", encoding="utf-8"
    )
    with pytest.raises(tool.ReplayError):
        tool.temporary_browser_runner(source, tmp_path / "home", tmp_path / "out.sh")


def test_wheel_receipt_records_actual_sha256_without_install(tool, tmp_path):
    wheels = tmp_path / "wheelhouse"
    wheels.mkdir()
    for i in range(44):
        (wheels / f"test{i:02d}-1.0-py3-none-any.whl").write_bytes(
            f"wheel-{i}".encode()
        )
    assert tool.wheel_receipt(wheels) == 44
    lines = (tmp_path / "wheel-sha256.txt").read_text().splitlines()
    assert len(lines) == 44
    expected = hashlib.sha256(b"wheel-0").hexdigest()
    assert any(line == f"{expected}  test00-1.0-py3-none-any.whl" for line in lines)


def test_wheel_receipt_requires_complete_inventory(tool, tmp_path):
    wheels = tmp_path / "wheelhouse"
    wheels.mkdir()
    (wheels / "one-1.0-py3-none-any.whl").write_bytes(b"not enough")
    with pytest.raises(tool.ReplayError):
        tool.wheel_receipt(wheels)


def test_script_keeps_live_environment_and_release_runner_unchanged():
    source = SCRIPT.read_text(encoding="utf-8")
    for present in (
        "--execute", "DRY_RUN=PASSED", "worktree", "venv",
        '"download"', '"--no-index"', '"--only-binary=:all:"',
        "FRESHENV_PACKAGE_BASELINE=PASSED", "tracker_dependency_baseline569.py",
        "playwright", "install", "chromium",
        "FRESHENV_CHROMIUM_LAUNCH=PASSED",
        "FRESHENV_BACKEND_SUITE=PASSED",
        "FRESHENV_BROWSER_SUITE=PASSED",
        "BROWSER_QA_HOME_OVERRIDE=TEMP_COPY_ONLY",
    ):
        assert present in source
    for forbidden in (
        '"/etc/tracker.env"', '"systemctl", "restart"',
        '"pip", "install", "--upgrade"',
        '"tracker-release.sh", "--instance"',
        '"git", "push"',
    ):
        assert forbidden not in source
