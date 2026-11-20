"""Release 705: read-only exact-pins and wheel-archive readiness regressions."""
import base64
import csv
import hashlib
import io
import os
from pathlib import Path
import zipfile

import pytest

from scripts import tracker_dependency_readiness705 as readiness


def wheel(path: Path, *, name="alpha", version="1.2", requires=(),
          bad_record=False, bad_metadata=False, python=">=3.8"):
    directory = f"{name}-{version}.dist-info"
    payload = {
        f"{name}/__init__.py": b"x = 2\n",
        f"{directory}/METADATA": (
            f"Metadata-Version: 2.4\nName: {'wrong' if bad_metadata else name}\n"
            f"Version: {version}\nRequires-Python: {python}\n"
            + "".join(f"Requires-Dist: {entry}\n" for entry in requires)
            + "\n"
        ).encode(),
        f"{directory}/WHEEL": (
            "Wheel-Version: 1.0\nGenerator: release-705-test\n"
            "Root-Is-Purelib: true\nTag: py3-none-any\n\n"
        ).encode(),
    }
    record = f"{directory}/RECORD"
    rows = [
        (filename, "sha256=" + base64.urlsafe_b64encode(
            hashlib.sha256(data).digest()).rstrip(b"=").decode(),
         str(len(data)))
        for filename, data in sorted(payload.items())
    ]
    if bad_record:
        rows[0] = (rows[0][0], "sha256=invalid", rows[0][2])
    rows.append((record, "", ""))
    content = io.StringIO()
    writer = csv.writer(content, lineterminator="\n")
    writer.writerows(rows)
    payload[record] = content.getvalue().encode()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename, data in payload.items():
            archive.writestr(filename, data)


def test_705_archived_wheel_metadata_record_and_abi_validate(tmp_path):
    target = tmp_path / "alpha-1.2-py3-none-any.whl"
    wheel(target)
    readiness.audit_wheel(target, {"alpha": "1.2"}, set(readiness.sys_tags()))


@pytest.mark.parametrize("failure", ("record", "metadata", "missing", "python", "dependency"))
def test_705_wheel_audit_rejects_tamper_or_incompatible_dependency(tmp_path, failure):
    target = tmp_path / "alpha-1.2-py3-none-any.whl"
    flags = {
        "bad_record": failure == "record",
        "bad_metadata": failure == "metadata",
        "python": ">=99" if failure == "python" else ">=3.8",
        "requires": ["missing-dep>=1"] if failure == "dependency" else [],
    }
    wheel(target, **flags)
    if failure == "missing":
        with zipfile.ZipFile(target, "a") as archive:
            archive.writestr("unrecorded.txt", b"unrecorded")
    with pytest.raises(readiness.ReadinessError):
        readiness.audit_wheel(target, {"alpha": "1.2"}, set(readiness.sys_tags()))


def test_705_readiness_checks_private_complete_wheelhouse(tmp_path, monkeypatch):
    target = tmp_path / "private"
    target.mkdir(mode=0o700)
    wheel(target / "alpha-1.2-py3-none-any.whl")
    monkeypatch.setattr(readiness.lock, "all_pins", lambda: {"alpha": "1.2"})
    with pytest.raises(readiness.ReadinessError, match="private"):
        # The fixture's temp root can have private permissions; this catches
        # wheelhouses accidentally exposed by their own permissions.
        os.chmod(target, 0o755)
        readiness.wheelhouse_audit(target)
    os.chmod(target, 0o700)
    assert readiness.wheelhouse_audit(target) == 1
    wheel(target / "extra-1.0-py3-none-any.whl", name="extra", version="1.0")
    with pytest.raises(readiness.lock.LockError):
        readiness.wheelhouse_audit(target)


def test_705_nonwheel_and_symlink_wheelhouse_fail_closed(tmp_path, monkeypatch):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    (root / "extra.txt").write_text("bad")
    monkeypatch.setattr(readiness.lock, "all_pins", lambda: {"alpha": "1.2"})
    with pytest.raises(readiness.lock.LockError):
        readiness.wheelhouse_audit(root)
    (root / "extra.txt").unlink()
    (root / "alpha-1.2-py3-none-any.whl").symlink_to(tmp_path / "missing")
    with pytest.raises(readiness.lock.LockError):
        readiness.wheelhouse_audit(root)


def test_705_readiness_no_wheelhouse_does_not_claim_replay(monkeypatch, capsys):
    monkeypatch.setattr(readiness, "runtime_audit", lambda: ([], True))
    assert readiness.main([]) == 0
    printed = capsys.readouterr().out
    assert "DEPENDENCY_705_WHEELHOUSE=NOT_SUPPLIED" in printed
    assert "DEPENDENCY_705_ISSUE10=BLOCKED" in printed
    assert "DEPENDENCY_705_REPLAY=NOT_EXECUTED" in printed


def test_705_runtime_drift_remains_blocked(monkeypatch):
    monkeypatch.setattr(readiness, "runtime_audit", lambda: (["PACKAGE pip drift"], False))
    assert readiness.main([]) == 2


def test_705_readiness_never_installs_or_downloads():
    source = (Path(__file__).resolve().parents[1] / "scripts"
              / "tracker_dependency_readiness705.py").read_text()
    forbidden = (
        '"install"', '"download"', '"uninstall"', '"upgrade"',
        '"systemctl"', '"pip", "wheel"', "TRACKER_CSRF_ENFORCE=1",
        '"/etc/tracker.env"', '"tracker-release.sh"',
    )
    for token in forbidden:
        assert token not in source
    assert '"pip", "check"' in source
    assert "filename_tags.intersection(supported)" in source
    assert "RECORD digest mismatch" in source
    assert "UNAPPROVED" in source


def test_705_offline_dependency_preview_has_exact_sha_and_no_install_contract():
    source = (Path(__file__).resolve().parents[1] / "scripts"
              / "tracker-dependency-preview705.sh").read_text()
    assert "tracker705-dependency-preview.lock" in source
    assert "git worktree add --detach" in source
    assert "--wheelhouse" in source
    assert "DEPENDENCY_705_AUDIT=COMPLETED_NO_INSTALL" in source
    assert "scripts/tracker_dependency_readiness705.py" in source
    assert "DEPENDENCY_705_INSTALLED_SOURCE_UNCHANGED=VERIFIED" in source
    for forbidden in ("pip install", "pip download", "systemctl restart",
                      "TRACKER_CSRF_ENFORCE=1", "tracker-release.sh"):
        assert forbidden not in source


def test_705_only_pypi_exact_playwright_1641_hash_can_bypass_wheel_tag_parity(
    tmp_path, monkeypatch, capsys
):
    target = tmp_path / readiness.PLAYWRIGHT_1641_WHEEL
    wheel(target, name="playwright", version="1.64.1")
    parsed = readiness.parse_tag("py3-none-manylinux1_x86_64")
    internal = readiness.parse_tag("py3-none-any")
    assert not readiness.documented_playwright_tag_exception(
        target, "playwright", "1.64.1", parsed, internal
    )
    # Mock only the trusted PyPI byte-hash comparison; no binary download
    # is required to regression-test the exact-name and exact-hash guard.
    monkeypatch.setattr(
        readiness.lock, "digest", lambda _: readiness.PLAYWRIGHT_1641_SHA256
    )
    assert readiness.documented_playwright_tag_exception(
        target, "playwright", "1.64.1", parsed, internal
    )
    readiness.audit_wheel(target, {"playwright": "1.64.1"}, set(readiness.sys_tags()))
    assert "DEPENDENCY_705_PLAYWRIGHT_1641_TAG_EXCEPTION=" in capsys.readouterr().out
    assert not readiness.documented_playwright_tag_exception(
        target, "playwright", "1.64.2", parsed, internal
    )
    assert not readiness.documented_playwright_tag_exception(
        target, "other", "1.64.1", parsed, internal
    )
    assert not readiness.documented_playwright_tag_exception(
        target, "playwright", "1.64.1", parsed,
        readiness.parse_tag("py3-none-manylinux1_x86_64")
    )
    monkeypatch.setattr(readiness.lock, "digest", lambda _: "0" * 64)
    assert not readiness.documented_playwright_tag_exception(
        target, "playwright", "1.64.1", parsed, internal
    )
    with pytest.raises(readiness.ReadinessError, match="Wheel WHEEL tags"):
        readiness.audit_wheel(target, {"playwright": "1.64.1"}, set(readiness.sys_tags()))
