"""Release 571 offline safety checks for preserving a completed fresh replay.

No live databases, package installation, service operations, downloads or
persistent archive creation are performed by these tests.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker_preserve571.py"


@pytest.fixture
def tool():
    spec = importlib.util.spec_from_file_location("preserve571", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_mode_must_not_create_archive(tool, monkeypatch, capsys):
    monkeypatch.setattr(tool, "preflight", lambda: "a" * 40)
    monkeypatch.setattr(tool, "replay_evidence", lambda *_: {"verified": True})
    monkeypatch.setattr(tool, "create_archive",
                        lambda *_: pytest.fail("Unapproved archive write"))
    assert tool.main(["--replay-root", "/tmp/tracker-freshenv570-test",
                      "--replay-log", "/tmp/mock.log"]) == 0
    assert "DRY_RUN=PASSED" in capsys.readouterr().out


def test_execute_requires_validation_and_checks_archive(tool, monkeypatch, capsys):
    phases = []
    sha = "b" * 40
    monkeypatch.setattr(tool, "preflight",
                        lambda: phases.append("preflight") or sha)
    monkeypatch.setattr(tool, "replay_evidence",
                        lambda _r, _l, commit:
                        phases.append(("evidence", commit)) or {"wheels": 44})
    monkeypatch.setattr(tool, "create_archive",
                        lambda *_: phases.append("archive") or Path("/tmp/fake-archive"))
    monkeypatch.setattr(tool, "verify_archive",
                        lambda *_: phases.append("verify"))
    assert tool.main(["--replay-root", "/tmp/tracker-freshenv570-test",
                      "--replay-log", "/tmp/mock.log", "--execute"]) == 0
    assert phases == ["preflight", ("evidence", sha), "archive", "verify"]
    assert "ARCHIVE_PRESERVATION=SUCCESS" in capsys.readouterr().out


def test_failed_preflight_refuses_all_changes(tool, monkeypatch, capsys):
    monkeypatch.setattr(
        tool, "preflight",
        lambda: (_ for _ in ()).throw(tool.ArchiveError("Denied")),
    )
    monkeypatch.setattr(tool, "replay_evidence",
                        lambda *_: pytest.fail("Unexpected input processing"))
    assert tool.main(["--replay-root", "/tmp/tracker-freshenv570-test",
                      "--replay-log", "/tmp/mock.log", "--execute"]) == 1
    assert "ARCHIVE_PRESERVATION=FAILED" in capsys.readouterr().err


def test_success_log_requires_exact_matching_commit_and_retained_root(tool, tmp_path,
                                                                       monkeypatch):
    monkeypatch.setattr(tool, "owner_checked", lambda *_args, **_kwargs: None)
    root = Path("/tmp/tracker-freshenv570-unittest")
    sha = "c" * 40
    log = tmp_path / "replay.log"
    lines = [*tool.MARKERS, f"DEV_SOURCE_COMMIT={sha}",
             f"ISOLATED_ROOT={root}", f"ISOLATED_ARTIFACTS_RETAINED={root}",
             "FRESHENV_REPLAY=SUCCESS"]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tool.validate_log(root, log, sha)
    log.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(tool.ArchiveError):
        tool.validate_log(root, log, sha)
    log.write_text("\n".join(lines).replace(sha, "d" * 40) + "\n",
                   encoding="utf-8")
    with pytest.raises(tool.ArchiveError):
        tool.validate_log(root, log, sha)


def test_verify_wheels_requires_matching_names_versions_and_sha256(tool,
                                                                    tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "owner_checked", lambda *_args, **_kwargs: None)
    root = tmp_path / "replay"
    wheels = root / "wheelhouse"
    wheels.mkdir(parents=True)
    packages = {"pip": "25.1.1"}
    packages.update({f"sample-{i:02d}": f"1.0.{i}" for i in range(43)})
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"package_versions": packages}),
                        encoding="utf-8")
    monkeypatch.setattr(tool, "BASELINE", baseline)
    hashes = {}
    for name, version in packages.items():
        filename = f"{name.replace('-', '_')}-{version}-py3-none-any.whl"
        path = wheels / filename
        path.write_bytes(filename.encode("utf-8"))
        hashes[filename] = hashlib.sha256(filename.encode("utf-8")).hexdigest()
    receipt = root / "wheel-sha256.txt"
    receipt.write_text("".join(f"{value}  {name}\n"
                               for name, value in sorted(hashes.items())),
                       encoding="utf-8")
    assert tool.verify_wheels(root) == hashes
    one = next(wheels.iterdir())
    one.write_bytes(b"changed")
    with pytest.raises(tool.ArchiveError, match="SHA-256"):
        tool.verify_wheels(root)


def test_browser_versions_must_match_fresh_playwright_metadata(tool, tmp_path,
                                                                monkeypatch):
    monkeypatch.setattr(tool, "owner_checked", lambda *_args, **_kwargs: None)
    root = tmp_path
    path = root / "venv/lib/python3.13/site-packages/playwright/driver/package"
    path.mkdir(parents=True)
    data = {"browsers": [
        {"name": "chromium", "revision": "1248", "browserVersion": "156.0"},
        {"name": "chromium-headless-shell", "revision": "1248"},
        {"name": "ffmpeg", "revision": "1013"},
    ]}
    (path / "browsers.json").write_text(json.dumps(data), encoding="utf-8")
    cache = root / "home/.cache/ms-playwright"
    for folder in ("chromium-1248", "chromium_headless_shell-1248",
                   "ffmpeg-1013"):
        directory = cache / folder
        directory.mkdir(parents=True)
        (directory / "asset").write_bytes(b"browser")
    browser_dirs, metadata = tool.browser_info(root)
    assert len(browser_dirs) == len(metadata) == 3
    assert metadata[0]["revision"] == "1248"
    (cache / "ffmpeg-1013/asset").unlink()
    with pytest.raises(tool.ArchiveError):
        tool.browser_info(root)


def test_tree_detects_change_and_rejects_external_symlinks(tool, tmp_path):
    root = tmp_path / "payload"
    root.mkdir()
    (root / "wheel.whl").write_bytes(b"original")
    before = tool.tree(root)
    (root / "wheel.whl").write_bytes(b"corrupted")
    assert tool.tree(root) != before
    (root / "external").symlink_to(tmp_path / "outside-file")
    (tmp_path / "outside-file").write_bytes(b"elsewhere")
    with pytest.raises(tool.ArchiveError):
        tool.tree(root)


def test_code_never_manages_services_or_live_dependencies():
    text = SCRIPT.read_text(encoding="utf-8")
    for forbidden in (
        '"systemctl"', '"restart"', '"pip", "install"',
        "tracker-release.sh", '"git", "push"',
        '"/etc/tracker.env"', "shutil.rmtree(APP)",
    ):
        assert forbidden not in text
    for required in (
        "ARCHIVE_PRESERVATION=SUCCESS",
        "REPLAY_EVIDENCE=VERIFIED",
        "RECOVERY_ARCHIVE_VERIFIED=PASS",
        "verify_archive(target)",
        "os.replace(staging, final)",
    ):
        assert required in text


def test_standalone_archive_verification_needs_no_dev_preflight(tool, monkeypatch):
    actions = []
    monkeypatch.setattr(tool, "preflight", lambda: pytest.fail("Unexpected DEV check"))
    monkeypatch.setattr(tool, "verify_archive",
                        lambda path: actions.append(path))
    path = "/var/lib/tracker-reproducibility/saved"
    assert tool.main(["--verify-archive", path]) == 0
    assert actions == [Path(path)]


def test_verified_archive_reports_corrupted_file(tool, tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "owner_checked", lambda *_args, **_kwargs: None)
    archive = tmp_path / "saved"
    payload = archive / "payload"
    payload.mkdir(parents=True)
    wheel = payload / "example.whl"
    wheel.write_bytes(b"preserved")
    manifest = {"schema_version": 1, "payload": tool.tree(payload)}
    (archive / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    tool.verify_archive(archive)
    wheel.write_bytes(b"altered")
    with pytest.raises(tool.ArchiveError, match="integrity"):
        tool.verify_archive(archive)


def test_verify_mode_cannot_mutate_archive(tool):
    with pytest.raises(SystemExit) as exc:
        tool.main(["--verify-archive", "/tmp/archive",
                   "--execute", "--replay-root", "/tmp/input"])
    assert exc.value.code == 2
