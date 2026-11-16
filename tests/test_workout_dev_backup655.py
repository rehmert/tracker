"""Release 655: DEV-only two-file backup, restore, and fail-closed regression."""
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
    assert mod.ALLOWED_MISSING == {MISSING_A, MISSING_B}
    data = tmp_path / "data"
    create_dev_data(data, [MISSING_A, MISSING_B])
    extra = data / "uploads" / "coa" / "existing.png"
    extra.parent.mkdir(parents=True)
    extra.write_bytes(b"present and retained")
    dest = tmp_path / "archives"
    assert invoke(mod, data, dest, monkeypatch) == 0

    capture = capsys.readouterr()
    assert "MISSING_REFERENCE" not in capture.out
    assert "DEV_655_DATABASE_AND_PRESENT_UPLOADS_RESTORED=PASSED" in capture.err
    assert "DEV_655_MISSING_REFERENCE_EXCEPTIONS=2" in capture.err
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
def test_655_archive_accepts_only_subsets_of_named_missing(
    tmp_path, monkeypatch, capsys, missing,
):
    mod = module655()
    data = tmp_path / "data"
    create_dev_data(data, missing)
    assert invoke(mod, data, tmp_path / "archives", monkeypatch) == 0
    archive = Path(capsys.readouterr().out.strip())
    assert mod.verify_archive(archive, sorted(missing)) == 1


def test_655_new_unexpected_missing_is_fatal_without_creating_archive(
    tmp_path, monkeypatch, capsys,
):
    mod = module655()
    data = tmp_path / "data"
    create_dev_data(data, [MISSING_A, MISSING_B, "uploads/coa/unexpected.png"])
    dest = tmp_path / "archives"
    with pytest.raises(ValueError, match="Unexpected missing DEV attachments"):
        invoke(mod, data, dest, monkeypatch)
    # No final archive is returned on failure.
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


def test_655_runner_uses_separate_dev_backup_without_affecting_prod():
    runner = (ROOT / "scripts/tracker-release.sh").read_text()
    assert 'if [[ "$INSTANCE" == DEV && "$REVIEWED_WORKOUT_655" == 1 ]]; then' in runner
    assert '"$QA/scripts/tracker-workout-dev-backup655.py"' in runner
    assert '"$QA/scripts/tracker-coa-dev-backup652.py"' in runner
    assert 'tracker-dev655-*.zip' in runner
    assert 'tracker-dev652-*.zip' in runner
    assert 'if [[ "$INSTANCE" != DEV || ( "$REVIEWED_COA_652" != 1' in runner
    assert 'tracker-attachment-integrity645.py" --data "$LIVE_DATA_DIR" --hashes' in runner
    assert (ROOT / "scripts/tracker-coa-dev-backup652.py").is_file()
