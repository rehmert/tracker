"""Release 442: DEV-only private rolling backup and isolated restore tests."""

import hashlib
import json
import os
import sqlite3
import stat
import zipfile
from pathlib import Path

import pytest

from app import config, session_auth385 as auth
from app.user_accounts427 import stage_secondary_account427
from app.user_bootstrap426 import initialize_staged_workspace426
from app.secondary_backup442 import (
    AUTH_NAME, KEY_NAME, create_secondary_backup442,
    verify_secondary_backup442,
)


@pytest.fixture
def staged(tmp_path, monkeypatch):
    root = tmp_path / "data"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(config, "DATA_DIR", root)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    auth.bootstrap("operator", "administrator-secure-password-442")
    (root / auth.FLAG).write_text("DEV enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, root)
        stage_secondary_account427(
            uid, f"member-{uid}", f"secondary-secure-password-{uid}-442",
        )
        with sqlite3.connect(root / "users" / str(uid) / "tracker.db") as db:
            db.execute("""
                INSERT INTO compounds(name,category,notes,primary_unit)
                VALUES (?, 'other', '', 'mg')
            """, (f"PRIVATE-442-{uid}",))
        upload = root / "users" / str(uid) / "uploads" / "coa" / f"coa-{uid}.pdf"
        upload.write_bytes(b"%PDF-private-user-" + str(uid).encode())
        if uid == 2:
            lab = root / "users" / "2" / "uploads" / "labs" / "private-lab.txt"
            lab.write_text("PRIVATE-LAB-USER-2")

    # Recovery of an existing session requires the same CSRF signing key.
    key = root / KEY_NAME
    key.write_bytes(b"4" * 32)
    key.chmod(0o600)

    # An unrelated administrator database must never appear in this archive.
    with sqlite3.connect(root / "tracker.db") as db:
        db.execute("CREATE TABLE administrator_secret (value TEXT)")
        db.execute("INSERT INTO administrator_secret VALUES ('ADMIN-ONLY')")
    target = tmp_path / "recovery-archives"
    return root, target


def _created(staged):
    root, directory = staged
    path = create_secondary_backup442(root, directory)
    return path, verify_secondary_backup442(path)


def _entries(archive):
    with zipfile.ZipFile(archive) as z:
        return {x.filename: z.read(x.filename) for x in z.infolist()}


def _repack(source, destination, changes):
    files = _entries(source)
    files.update(changes)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)


def test_snapshot_covers_two_private_databases_auth_key_and_uploads(staged):
    root, directory = staged
    before = {
        name: (root / name).read_bytes()
        for name in (
            AUTH_NAME, KEY_NAME, "tracker.db",
            "users/2/tracker.db", "users/3/tracker.db",
            "users/2/uploads/coa/coa-2.pdf",
            "users/3/uploads/coa/coa-3.pdf",
        )
    }
    archive, report = _created(staged)
    assert report["user_ids"] == [2, 3]
    assert report["user_count"] == 2
    assert report["restore_verified"] is True
    assert report["consistency"] == "per_database_snapshot_not_globally_atomic"
    names = set(_entries(archive))
    assert names == {
        "manifest.json",
        AUTH_NAME, KEY_NAME,
        "users/2/tracker.db", "users/3/tracker.db",
        "users/2/uploads/coa/coa-2.pdf",
        "users/2/uploads/labs/private-lab.txt",
        "users/3/uploads/coa/coa-3.pdf",
    }
    assert "tracker.db" not in names
    assert "ADMIN-ONLY" not in str(_entries(archive))
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(archive.stat().st_mode) == 0o600
    assert all((root / name).read_bytes() == original
               for name, original in before.items())
    assert (root / "users" / "2" / "uploads" / "labs" / "private-lab.txt").read_text() == "PRIVATE-LAB-USER-2"


def test_private_user_database_restore_finds_correct_identity_and_content(staged, tmp_path):
    _, _ = staged
    archive, _ = _created(staged)
    # DB files are themselves consistent SQLite snapshots inside the archive.
    with zipfile.ZipFile(archive) as z:
        for uid in (2, 3):
            dest = tmp_path / f"isolated-{uid}.sqlite3"
            dest.write_bytes(z.read(f"users/{uid}/tracker.db"))
            with sqlite3.connect(dest) as db:
                marker = db.execute("""
                    SELECT user_id,status,schema_version
                    FROM tracker_staged_workspace426
                """).fetchall()
                names = db.execute(
                    "SELECT name FROM compounds"
                ).fetchall()
                assert marker == [(uid, "inactive", 426)]
                assert names == [(f"PRIVATE-442-{uid}",)]
                assert db.execute(
                    "PRAGMA integrity_check"
                ).fetchone() == ("ok",)
        assert z.read("users/2/uploads/labs/private-lab.txt") == b"PRIVATE-LAB-USER-2"
        auth_copy = tmp_path / "auth-snapshot.sqlite3"
        auth_copy.write_bytes(z.read(AUTH_NAME))
        with sqlite3.connect(auth_copy) as db:
            users = db.execute(
                "SELECT id,enabled FROM users ORDER BY id"
            ).fetchall()
            assert users == [(1, 1), (2, 0), (3, 0)]
        assert z.read(KEY_NAME) == b"4" * 32


def test_modified_hash_or_missing_member_is_rejected(staged, tmp_path):
    archive, _ = _created(staged)
    corrupted = tmp_path / "corrupted.zip"
    _repack(archive, corrupted, {
        "users/2/uploads/coa/coa-2.pdf": b"tampered upload bytes",
    })
    with pytest.raises(ValueError):
        verify_secondary_backup442(corrupted)

    missing = tmp_path / "missing.zip"
    content = _entries(archive)
    content.pop("users/3/tracker.db")
    with zipfile.ZipFile(missing, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in content.items():
            z.writestr(name, data)
    with pytest.raises(ValueError):
        verify_secondary_backup442(missing)


def test_swapped_private_databases_rejected_even_with_updated_hashes(staged, tmp_path):
    archive, _ = _created(staged)
    data = _entries(archive)
    a = "users/2/tracker.db"
    b = "users/3/tracker.db"
    data[a], data[b] = data[b], data[a]
    manifest = json.loads(data["manifest.json"])
    for name in (a, b):
        manifest["files"][name] = {
            "bytes": len(data[name]),
            "sha256": hashlib.sha256(data[name]).hexdigest(),
        }
    data["manifest.json"] = json.dumps(manifest).encode()
    swapped = tmp_path / "swapped.zip"
    with zipfile.ZipFile(swapped, "w", zipfile.ZIP_DEFLATED) as z:
        for name, contents in data.items():
            z.writestr(name, contents)
    with pytest.raises(ValueError, match="marker"):
        verify_secondary_backup442(swapped)


def test_archive_traversal_symlink_and_unexpected_members_rejected(staged, tmp_path):
    archive, _ = _created(staged)
    for filename in (
        "../outside.txt",
        "users/1/tracker.db",
        "users/3/backups/other.zip",
        "users/2/uploads/../secret",
        "unexpected-file",
    ):
        altered = tmp_path / ("bad-" + str(abs(hash(filename))) + ".zip")
        _repack(archive, altered, {filename: b"malicious"})
        with pytest.raises(ValueError):
            verify_secondary_backup442(altered)
        assert not (tmp_path / "outside.txt").exists()

    altered = tmp_path / "symlink.zip"
    with zipfile.ZipFile(altered, "w", zipfile.ZIP_DEFLATED) as z:
        for name, contents in _entries(archive).items():
            if name == "users/2/tracker.db":
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                z.writestr(info, contents)
            else:
                z.writestr(name, contents)
    with pytest.raises(ValueError):
        verify_secondary_backup442(altered)


def test_unregistered_private_workspace_or_symlink_denies_snapshot(staged, tmp_path):
    root, directory = staged
    users = root / "users"
    extra = users / "4"
    extra.mkdir()
    with pytest.raises(ValueError, match="Unregistered"):
        create_secondary_backup442(root, directory)
    extra.rmdir()

    malicious = root / "users" / "2" / "uploads" / "coa" / "alias.pdf"
    malicious.symlink_to(root / "users" / "3" / "uploads" / "coa" / "coa-3.pdf")
    with pytest.raises(ValueError, match="Symlinked"):
        create_secondary_backup442(root, directory)
    malicious.unlink()

    assert not list(directory.glob("tracker-secondary-*.zip"))


def test_upload_changed_during_snapshot_does_not_publish(staged, monkeypatch):
    root, directory = staged
    from app import secondary_backup442 as backup
    original = backup._copy_upload
    changed = False

    def meddle(source, target):
        nonlocal changed
        original(source, target)
        if not changed and source.name == "coa-2.pdf":
            source.write_bytes(b"altered-during-backup")
            changed = True

    monkeypatch.setattr(backup, "_copy_upload", meddle)
    with pytest.raises(ValueError, match="changed"):
        create_secondary_backup442(root, directory)
    assert not list(directory.glob("tracker-secondary-*.zip"))


def test_prod_and_missing_auth_gate_creation(staged, monkeypatch):
    root, directory = staged

    # Release 523 permits secondary backups in both environments.
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    archive = create_secondary_backup442(root, directory)
    assert archive.is_file()
    assert verify_secondary_backup442(archive)["restore_verified"] is True

    # Authentication must still be enabled.
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    (root / auth.FLAG).unlink()
    with pytest.raises(PermissionError):
        create_secondary_backup442(root, directory)

    # A denied operation must not publish another archive.
    assert len(list(directory.glob("tracker-secondary-*.zip"))) == 1


def test_recovery_size_bound_and_archive_symlink_are_rejected(staged, tmp_path):
    archive, _ = _created(staged)
    with pytest.raises(ValueError, match="limit"):
        verify_secondary_backup442(archive, max_bytes=1)
    link = tmp_path / "alias.zip"
    link.symlink_to(archive)
    with pytest.raises(ValueError, match="Symlinked"):
        verify_secondary_backup442(link)


def test_recovery_page_discloses_non_atomic_and_not_automated(staged):
    from app.secondary_preview430 import preview_app
    from pathlib import Path
    source = Path("app/secondary_preview430.py").read_text()
    assert "tracker-secondary-backup442.py create" in source
    assert "Automatic secondary" in source
    assert "atomic snapshot across users" in source
    assert "off-host encryption" in source
    assert "live restore function" in source
    assert "does not include staged secondary" in source


def test_script_explicitly_has_no_live_restore_or_production_mode():
    from pathlib import Path
    path = Path("scripts/tracker-secondary-backup442.py")
    src = path.read_text()
    assert 'choices=("create", "verify")' in src
    assert '"DEV"' in src
    assert "os.geteuid() != 0" in src
    assert "restore" in src
