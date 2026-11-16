"""Release 655+: DEV missing-file-tolerant backup and strict present-file integrity."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import sqlite3
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-workout-dev-backup655.py"
MISSING_A = "uploads/coa/b94356f52d964400b481e6c743484367.png"
MISSING_B = "uploads/coa/35ddd15d235246258cd8ed0b69fef3c6.png"
EXPECTED = [MISSING_B, MISSING_A]  # same lexicographic order as sorted()


def module655():
    spec = spec_from_file_location("workout_dev_backup655", SCRIPT)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_dev_data(root: Path, missing: list[str]) -> None:
    (root / "uploads").mkdir(parents=True)
    with sqlite3.connect(root / "tracker.db") as db:
        db.execute(
            "CREATE TABLE coa_attachments("
            "id INTEGER PRIMARY KEY, stored_name TEXT, original_name TEXT)"
        )
        for name in missing:
            db.execute(
                "INSERT INTO coa_attachments(stored_name, original_name) VALUES (?,?)",
                (Path(name).name, "missing-original.png"),
            )
        db.commit()


def invoke(mod, data, dest, monkeypatch):
    monkeypatch.setattr(mod, "verify_dev_instance", lambda: None)
    monkeypatch.setattr(mod.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        mod.os, "uname", lambda: SimpleNamespace(nodename="tracker-dev")
    )
    monkeypatch.setattr(mod, "attachment_gate", lambda args: 0)
    monkeypatch.setattr(
        mod.os.sys, "argv",
        ["tracker-workout-dev-backup655.py", "--data", str(data), "--dest", str(dest)],
    )
    return mod.main()


def test_655_archive_restores_known_two_missing_without_fabricating_files(
    tmp_path, monkeypatch, capsys,
):
    mod = module655()
    data = tmp_path / "data"
    create_dev_data(data, [MISSING_A, MISSING_B])
    extra = data / "uploads" / "coa" / "existing.png"
    extra.parent.mkdir(parents=True)
    extra.write_bytes(b"present and retained")
    dest = tmp_path / "archives"
    assert invoke(mod, data, dest, monkeypatch) == 0

    capture = capsys.readouterr()
    assert "MISSING_REFERENCE" not in capture.out
    assert "DEV_DATABASE_AND_PRESENT_UPLOADS_RESTORED=PASSED" in capture.err
    assert "DEV_MISSING_UPLOAD_REFERENCES_SKIPPED=2" in capture.err
    lines = capture.out.splitlines()
    assert len(lines) == 1
    archive = Path(lines[0])
    assert archive.parent == dest
    assert archive.name.startswith("tracker-dev655-")
    assert mod.verify_archive(archive, EXPECTED) == 2

    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist()) == {
            "manifest.json", "tracker.db", "uploads/coa/existing.png"
        }
        manifest = json.loads(z.read("manifest.json"))
        assert manifest["known_missing"] == EXPECTED
        assert z.read("uploads/coa/existing.png") == b"present and retained"

    # The source directory and original DB references remain untouched.
    assert extra.read_bytes() == b"present and retained"
    assert not (data / MISSING_A).exists()
    assert not (data / MISSING_B).exists()


@pytest.mark.parametrize("missing", [
    [MISSING_A],
    [MISSING_B],
    [],
])
def test_655_archive_accepts_any_missing_file_selection(
    tmp_path, monkeypatch, capsys, missing,
):
    mod = module655()
    data = tmp_path / "data"
    create_dev_data(data, missing)
    assert invoke(mod, data, tmp_path / "archives", monkeypatch) == 0
    archive = Path(capsys.readouterr().out.strip())
    assert mod.verify_archive(archive, sorted(missing)) == 1


def test_655_new_unexpected_missing_is_nonblocking(
    tmp_path, monkeypatch, capsys,
):
    """The third, fourth or hundredth missing DEV upload requires no new code."""
    mod = module655()
    data = tmp_path / "data"
    names = [
        MISSING_A, MISSING_B, "uploads/coa/unexpected.png",
        "uploads/coa/another-arbitrary-file.png",
    ]
    create_dev_data(data, names)
    dest = tmp_path / "archives"
    assert invoke(mod, data, dest, monkeypatch) == 0
    capture = capsys.readouterr()
    assert "DEV_MISSING_UPLOAD_REFERENCES_SKIPPED=4" in capture.err
    archive = Path(capture.out.strip())
    assert archive.is_file()
    assert mod.verify_archive(archive, sorted(names)) == 1


def test_655_dev_backup_succeeds_with_no_uploads_directory(
    tmp_path, monkeypatch, capsys,
):
    mod = module655()
    data = tmp_path / "data"
    create_dev_data(data, [MISSING_A, MISSING_B])
    (data / "uploads").rmdir()
    dest = tmp_path / "archives"
    assert invoke(mod, data, dest, monkeypatch) == 0
    captured = capsys.readouterr()
    assert "DEV_MISSING_UPLOAD_REFERENCES_SKIPPED=2" in captured.err
    archive = Path(captured.out.strip())
    assert archive.is_file()
    assert mod.verify_archive(archive, EXPECTED) == 1


def test_655_invalid_or_hash_mismatched_present_uploads_fail_closed(
    tmp_path, monkeypatch, capsys,
):
    """Keep the preexisting DEV integrity gate, but no filename whitelist."""
    mod = module655()
    data = tmp_path / "data"
    create_dev_data(data, [MISSING_A])
    dest = tmp_path / "archives"
    monkeypatch.setattr(mod, "verify_dev_instance", lambda: None)
    monkeypatch.setattr(mod.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        mod.os, "uname", lambda: SimpleNamespace(nodename="tracker-dev")
    )
    monkeypatch.setattr(mod, "attachment_gate", lambda args: 1)
    monkeypatch.setattr(
        mod.os.sys, "argv",
        ["tracker-workout-dev-backup655.py", "--data", str(data), "--dest", str(dest)],
    )
    with pytest.raises(ValueError, match="present attachment hashes or paths"):
        mod.main()
    assert capsys.readouterr().out == ""
    assert not list(dest.glob("tracker-dev655-*.zip"))


def test_655_wrong_manifest_or_corrupt_hash_is_fatal(tmp_path):
    mod = module655()
    data = tmp_path / "data"
    create_dev_data(data, [MISSING_A, MISSING_B])
    raw = (data / "tracker.db").read_bytes()
    manifest = {
        "kind": "DEV-655-INCOMPLETE-ATTACHMENT-REVIEW",
        "known_missing": EXPECTED,
        "files": {
            "tracker.db": {
                "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            }
        },
    }
    archive = tmp_path / "bad.zip"
    for mutation, match in (
        ("missing", "Missing-reference evidence mismatch"),
        ("digest", "Archive checksum mismatch"),
    ):
        edited = json.loads(json.dumps(manifest))
        if mutation == "missing":
            edited["known_missing"] = [MISSING_A]
        else:
            edited["files"]["tracker.db"]["sha256"] = "0" * 64
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("tracker.db", raw)
            z.writestr("manifest.json", json.dumps(edited))
        with pytest.raises(ValueError, match=match):
            mod.verify_archive(archive, EXPECTED)


def test_655_runner_dev_policy_applies_to_all_releases_without_affecting_prod():
    runner = (ROOT / "scripts/tracker-release.sh").read_text()
    preflight = runner.split("=== LIVE ATTACHMENT INTEGRITY BEFORE QUALIFICATION ===", 1)[1]
    preflight = preflight.split(' cd "$QA"', 1)[0]
    prebackup = runner.split("=== LIVE ATTACHMENT INTEGRITY BEFORE MIGRATION BACKUP ===", 1)[1]
    prebackup = prebackup.split(' echo "=== Verified database backup', 1)[0]
    backup = runner.split(' mkdir -m 700 "$SAVE/archives"', 1)[1]
    backup = backup.split(' echo "=== ISOLATED RESTORE VERIFICATION PASSED ==="', 1)[0]
    for section in (preflight, prebackup, backup):
        assert 'if [[ "$INSTANCE" == DEV ]]; then' in section
        assert 'REVIEWED_WORKOUT_655" == 1' not in section
        assert 'REVIEWED_COA_652" == 1' not in section
    assert '"$QA/scripts/tracker-workout-dev-backup655.py"' in backup
    assert 'tracker-dev655-*.zip' in backup
    assert 'DEV_MISSING_UPLOADS=NONBLOCKING' in backup
    assert 'from app.backup import create_backup' in backup
    assert 'tracker-attachment-integrity645.py" --data "$LIVE_DATA_DIR" --hashes' in preflight
    assert 'tracker-attachment-integrity645.py" --data "$LIVE_DATA_DIR" --hashes' in prebackup
    assert '"$QA/scripts/tracker-restore-verify.py" --archive "$ARCHIVE"' in backup
    assert (ROOT / "scripts/tracker-coa-dev-backup652.py").is_file()
