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


def test_guard_includes_unchanged_tracked_app_files(tmp_path):
    root = _mock_sources(tmp_path)
    unchanged = root / "app/routers/food.py"
    unchanged.write_text("source", encoding="utf-8")

    subprocess.run(
        ["git", "init", "-q", str(root)], check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "add", "--", "app/"], check=True,
    )

    tracked = guard.tracked_app_paths(root)
    assert "app/routers/food.py" in tracked

    count, errors = guard.validate(
        root, tracked, "tracker",
        probe=lambda path, user: path != unchanged,
    )
    assert count == len(tracked)
    assert any(
        "cannot read app/routers/food.py" in message
        for message in errors
    )


def test_guard_fails_closed_outside_git_repository(tmp_path):
    with pytest.raises(ValueError, match="Cannot list tracked"):
        guard.tracked_app_paths(tmp_path)
