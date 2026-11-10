"""Release 539: independent working-directory resolution."""

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-runtime-smoke.py"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "tracker_smoke539", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_systemd_working_directory539(
    smoke, monkeypatch, tmp_path
):
    class Result:
        stdout = str(tmp_path) + "\n"

    monkeypatch.setattr(
        smoke.subprocess,
        "run",
        lambda *args, **kwargs: Result(),
    )

    assert smoke.service_working_directory() == tmp_path


def test_systemd_working_directory_missing539(
    smoke, monkeypatch
):
    class Result:
        stdout = ""

    monkeypatch.setattr(
        smoke.subprocess,
        "run",
        lambda *args, **kwargs: Result(),
    )

    with pytest.raises(ValueError, match="unset"):
        smoke.service_working_directory()


def test_systemd_working_directory_relative539(
    smoke, monkeypatch
):
    class Result:
        stdout = "./data\n"

    monkeypatch.setattr(
        smoke.subprocess,
        "run",
        lambda *args, **kwargs: Result(),
    )

    with pytest.raises(ValueError, match="not absolute"):
        smoke.service_working_directory()


def test_relative_path_independent_of_shell_cwd539(
    smoke, monkeypatch, tmp_path
):
    service_root = tmp_path / "service"
    service_root.mkdir()

    expected = service_root / "data"
    expected.mkdir()

    monkeypatch.setattr(
        smoke,
        "service_working_directory",
        lambda: service_root,
    )

    settings = {
        "TRACKER_INSTANCE": "PROD",
        "TRACKER_DATA_DIR": "./data",
    }

    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()

    monkeypatch.chdir(unrelated)

    # No session flag means the function must still
    # resolve the path correctly without creating data.
    original_is_file = Path.is_file
    observed = []

    def inspect_flag(path):
        if path.name == ".tracker-session-auth-dev":
            observed.append(path.parent)
            return False
        return original_is_file(path)

    monkeypatch.setattr(Path, "is_file", inspect_flag)

    with smoke.release_auth_headers("PROD", settings):
        pass

    assert observed == [expected]
    assert Path.cwd() == unrelated


def test_absolute_path_ignores_service_cwd539(
    smoke, monkeypatch, tmp_path
):
    absolute = tmp_path / "data"
    absolute.mkdir()

    def unexpected_lookup():
        raise AssertionError(
            "Absolute path must not query service working directory"
        )

    monkeypatch.setattr(
        smoke, "service_working_directory",
        unexpected_lookup
    )

    original_is_file = Path.is_file
    observed = []

    def inspect_flag(path):
        if path.name == ".tracker-session-auth-dev":
            observed.append(path.parent)
            return False
        return original_is_file(path)

    monkeypatch.setattr(Path, "is_file", inspect_flag)

    with smoke.release_auth_headers(
        "DEV",
        {
            "TRACKER_INSTANCE": "DEV",
            "TRACKER_DATA_DIR": str(absolute),
        },
    ):
        pass

    assert observed == [absolute]


def test_no_shell_cwd_dependency539():
    source = SCRIPT.read_text()

    assert "service_working_directory()" in source
    assert "WorkingDirectory" in source
    assert "directory = directory.resolve()" in source
    assert "Path.cwd()" not in source
