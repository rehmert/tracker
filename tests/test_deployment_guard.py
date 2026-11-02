"""Offline regression checks for the service-account source permission gate."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "tracker_deployment_guard",
    ROOT / "scripts/tracker-deployment-guard.py",
)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def _mock_sources(tmp_path):
    for name in guard.ALWAYS_CHECK:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("safe test source", encoding="utf-8")
    return tmp_path


def test_guard_checks_all_bootstrap_source_files(tmp_path):
    root = _mock_sources(tmp_path)
    count, errors = guard.validate(
        root, [], "tracker",
        probe=lambda path, user: True,
    )
    assert count == len(guard.ALWAYS_CHECK)
    assert errors == []


def test_guard_rejects_unreadable_release_file(tmp_path):
    root = _mock_sources(tmp_path)
    extra = root / "app/routers/new_feature.py"
    extra.write_text("print('ok')", encoding="utf-8")
    count, errors = guard.validate(
        root,
        ["app/routers/new_feature.py"],
        "tracker",
        probe=lambda path, user: path != extra,
    )
    assert count == len(guard.ALWAYS_CHECK) + 1
    assert any("cannot read app/routers/new_feature.py" in e for e in errors)


def test_guard_rejects_missing_or_symlinked_source(tmp_path):
    root = _mock_sources(tmp_path)
    unsafe = root / "app/routers/shortcut.py"
    unsafe.symlink_to(root / "app/main.py")
    _, errors = guard.validate(
        root, ["app/routers/shortcut.py", "app/not-present.py"],
        "tracker", probe=lambda path, user: True,
    )
    assert any("shortcut.py" in e for e in errors)
    assert any("not-present.py" in e for e in errors)


@pytest.mark.parametrize("name", [
    "../etc/passwd", "/etc/passwd", "scripts/update.sh",
    "app/../secrets.txt",
])
def test_guard_rejects_path_escape(tmp_path, name):
    root = _mock_sources(tmp_path)
    _, errors = guard.source_paths(root, [name])
    assert any("unsafe path" in e for e in errors)


def test_guard_cli_rejects_invalid_git_revision(tmp_path):
    _mock_sources(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/tracker-deployment-guard.py"),
            "--root", str(tmp_path),
            "--service-user", "root",
            "--base", "missing-base",
            "--target", "missing-target",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "FAIL:" in result.stderr
    assert len(result.stderr) < 500
