"""Release 705: no-install PyPI acquisition and digest-matching guardrails."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import tracker_dependency_acquire705 as acquisition


def test_705_acquisition_is_opt_in_no_network_without_explicit_execute(capsys):
    assert acquisition.main([]) == 0
    captured = capsys.readouterr().out
    assert "DEPENDENCY_705_DOWNLOAD=NOT_EXECUTED_REQUIRE_EXPLICIT_FLAG" in captured


def test_705_every_download_is_exact_pinned_binary_only_and_no_cache(tmp_path):
    root = tmp_path / "receipt"
    command = acquisition.pip_download_args(
        "/opt/tracker/.venv/bin/python",
        root / "approved-pins705.txt", root / "wheelhouse",
    )
    assert command[:5] == [
        "/opt/tracker/.venv/bin/python", "-B", "-m", "pip", "--isolated"
    ]
    assert command[5] == "download"
    for required in (
        "--no-cache-dir", "--no-input", "--only-binary=:all:",
        "--no-deps", "--index-url", "--dest", "--requirement",
        "--disable-pip-version-check",
    ):
        assert required in command
    assert command[command.index("--index-url") + 1] == acquisition.PYPI_INDEX
    assert "--extra-index-url" not in command
    assert "--find-links" not in command
    assert "--trusted-host" not in command
    assert "install" not in command
    assert "wheel" not in command


def test_705_download_subprocess_uses_clean_environment(monkeypatch, tmp_path):
    observed = {}
    class Process:
        def wait(self, timeout):
            observed["timeout"] = timeout
            return 0
    def fake_popen(cmd, **kwargs):
        observed["args"] = cmd
        observed["kwargs"] = kwargs
        return Process()
    monkeypatch.setattr(acquisition.subprocess, "Popen", fake_popen)
    acquisition.run_pip_download(["python", "-m", "pip", "download"], tmp_path)
    env = observed["kwargs"]["env"]
    assert set(env) == {
        "HOME", "PATH", "LANG", "PYTHONNOUSERSITE", "PYTHONDONTWRITEBYTECODE"
    }
    assert "PIP_INDEX_URL" not in env
    assert "GITHUB_TOKEN" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert observed["kwargs"]["start_new_session"] is True
    assert observed["timeout"] == acquisition.MAX_DOWNLOAD_SECONDS


def test_705_pypi_metadata_sha256_and_yank_must_match(monkeypatch):
    wheel = {
        "name": "alpha", "version": "1.2", "filename": "alpha-1.2-py3-none-any.whl",
        "sha256": "a" * 64, "bytes": 24,
    }
    release = {
        "info": {"name": "alpha", "version": "1.2"},
        "urls": [{
            "filename": wheel["filename"],
            "packagetype": "bdist_wheel",
            "url": "https://files.pythonhosted.org/packages/abc/alpha.whl",
            "size": 24,
            "digests": {"sha256": "a" * 64},
            "yanked": False,
        }],
    }
    class Response:
        def __init__(self, record, url):
            self.record, self.url = record, url
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def geturl(self):
            return self.url
        def read(self, _max_bytes):
            return json.dumps(self.record).encode()
    def fake_open(request, timeout):
        assert request.full_url == "https://pypi.org/pypi/alpha/1.2/json"
        assert timeout <= 30
        return Response(release, request.full_url)
    monkeypatch.setattr(acquisition, "urlopen", fake_open)
    record = acquisition.pypi_digest_record(wheel)
    assert record["sha256"] == "a" * 64
    assert record["pypi_yanked"] is False
    assert record["name"] == "alpha"

    release["urls"][0]["digests"]["sha256"] = "b" * 64
    with pytest.raises(acquisition.AcquisitionError, match="SHA256"):
        acquisition.pypi_digest_record(wheel)
    release["urls"][0]["digests"]["sha256"] = "a" * 64
    release["urls"][0]["yanked"] = True
    with pytest.raises(acquisition.AcquisitionError, match="yanked"):
        acquisition.pypi_digest_record(wheel)
    release["urls"][0]["yanked"] = False
    release["urls"][0]["url"] = "https://untrusted.invalid/wheel.whl"
    with pytest.raises(acquisition.AcquisitionError, match="host"):
        acquisition.pypi_digest_record(wheel)


def test_705_private_receipt_is_exclusive_and_mode_0600(tmp_path):
    path = tmp_path / "receipt.json"
    acquisition.write_private(path, b"test\n")
    assert path.read_bytes() == b"test\n"
    assert path.stat().st_mode & 0o077 == 0
    with pytest.raises(FileExistsError):
        acquisition.write_private(path, b"overwrite")


def test_705_wrong_host_or_nonroot_cannot_create_downloads(monkeypatch):
    monkeypatch.setattr(acquisition.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(acquisition.socket, "gethostname", lambda: "tracker-dev")
    with pytest.raises(acquisition.AcquisitionError, match="tracker-dev"):
        acquisition.acquire()
    monkeypatch.setattr(acquisition.os, "geteuid", lambda: 0)
    monkeypatch.setattr(acquisition.socket, "gethostname", lambda: "tracker-prod")
    with pytest.raises(acquisition.AcquisitionError, match="tracker-dev"):
        acquisition.acquire()


def test_705_require_44_pins_exact_python_and_linux(monkeypatch):
    monkeypatch.setattr(acquisition.lock, "all_pins", lambda: {"pip": "25.1.1"})
    with pytest.raises(acquisition.AcquisitionError):
        acquisition.checked_pins()


def test_705_acquisition_never_calls_install_or_modifies_prod():
    root = Path(__file__).resolve().parents[1]
    python = (root / "scripts/tracker_dependency_acquire705.py").read_text()
    bash = (root / "scripts/tracker-dependency-acquire705.sh").read_text()
    assert 'run_pip_download(command, root)' in python
    assert 'readiness.wheelhouse_audit(wheels)' in python
    assert 'lock.create(wheels, receipts)' in python
    assert 'lock.verify(wheels, receipts)' in python
    assert 'pypi_digest_record(row)' in python
    assert 'DEPENDENCY_705_REPLAY=NOT_EXECUTED' in python
    assert 'DEPENDENCY_705_ACQUISITION=PASSED_DOWNLOAD_ONLY' in python
    assert 'DEPENDENCY_705_INSTALLED_SOURCE_UNCHANGED=VERIFIED' in bash
    assert 'bash scripts/tracker-release-scoped705.sh "$PY"' in bash
    assert 'scripts/tracker_dependency_readiness705.py' in bash
    assert '--execute-download' in bash
    assert 'git worktree add --detach' in bash
    for forbidden in (
        'pip install', 'pip download', 'systemctl restart', 'systemctl stop',
        'git reset', 'git push', 'TRACKER_CSRF_ENFORCE=1',
        '/etc/tracker.env', 'tracker-release.sh',
    ):
        assert forbidden not in bash
    for forbidden in (
        '"install"', '"uninstall"', '"upgrade"', '"systemctl"',
        'TRACKER_CSRF_ENFORCE=1', '/etc/tracker.env',
        '"tracker-release.sh"',
    ):
        assert forbidden not in python
