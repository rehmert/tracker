"""Release 445: actual disposable offline restoration and session invalidation."""

import hashlib
import os
import shutil
import sqlite3
import stat
import subprocess
import zipfile
from pathlib import Path

import pytest

from app import config, session_auth385 as auth
from app.secondary_backup442 import create_secondary_backup442
from app.secondary_restore_rehearsal445 import (
    rehearse_archive445, rehearse_encrypted_archive445,
)
from app.user_accounts427 import stage_secondary_account427
from app.user_bootstrap426 import initialize_staged_workspace426


@pytest.fixture
def backup(tmp_path, monkeypatch):
    root = tmp_path / "live-data"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(config, "DATA_DIR", root)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    auth.bootstrap("operator", "administrator-secure-password-445")
    (root / auth.FLAG).write_text("enabled")
    (root / ".tracker-csrf-signing-key-v1").write_bytes(b"K" * 32)
    (root / ".tracker-csrf-signing-key-v1").chmod(0o600)

    for uid in (2, 3):
        initialize_staged_workspace426(uid, root)
        stage_secondary_account427(
            uid, f"member-{uid}", f"secondary-secure-password-{uid}-445",
        )
        with sqlite3.connect(root / "users" / str(uid) / "tracker.db") as db:
            db.execute("""
                INSERT INTO compounds(name,category,notes,primary_unit)
                VALUES (?, 'other', '', 'mg')
            """, (f"PRIVATE-445-{uid}",))
        upload = (
            root / "users" / str(uid) / "uploads" / "labs"
            / f"private-lab-{uid}.txt"
        )
        upload.write_text(f"TEST-ONLY-PRIVATE-RECORD-{uid}")

    from app.secondary_preview430 import _tables
    with auth.connect() as db:
        _tables(db)
        db.execute("""
            INSERT INTO sessions(token_hash,user_id,expires_at)
            VALUES (?,1,4102444800)
        """, ("a" * 64,))
        for uid, token in ((2, "b" * 64), (3, "c" * 64)):
            db.execute("""
                INSERT INTO tracker_secondary_sessions430
                    (token_hash,user_id,expires_at)
                VALUES (?,?,4102444800)
            """, (token, uid))
        db.execute(
            "INSERT INTO failures(username,occurred_at) VALUES('operator',1)"
        )
        db.execute("""
            INSERT INTO tracker_secondary_failures430(username,occurred_at)
            VALUES ('bad',1)
        """)
        db.commit()

    with sqlite3.connect(root / "tracker.db") as db:
        db.execute("CREATE TABLE admin_only(secret TEXT)")
        db.execute("INSERT INTO admin_only VALUES ('NO-RESTORE')")

    backup_dir = tmp_path / "archives"
    archive = create_secondary_backup442(root, backup_dir)
    scratch = tmp_path / "sandbox-parent"
    scratch.mkdir(mode=0o700)
    return root, archive, scratch


def _live_hashes(root):
    files = (
        "tracker.db", "tracker-auth.sqlite3",
        ".tracker-csrf-signing-key-v1",
        "users/2/tracker.db", "users/3/tracker.db",
        "users/2/uploads/labs/private-lab-2.txt",
        "users/3/uploads/labs/private-lab-3.txt",
    )
    return {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in files
    }


def test_rehearsal_restores_both_accounts_revokes_sessions_and_rotates_key(
    backup, monkeypatch,
):
    from app import secondary_restore_rehearsal445 as mod
    root, archive, scratch = backup
    before = _live_hashes(root)
    encrypted_before = hashlib.sha256(archive.read_bytes()).hexdigest()
    seen = {}
    original = mod._check_recovered445

    def observe(isolated, ids, manifest):
        seen["sandbox"] = isolated.parent
        assert ids == [2, 3]
        assert isolated != root
        assert not isolated.is_relative_to(root)
        assert not (isolated / "tracker.db").exists()
        assert (isolated / ".tracker-csrf-signing-key-v1").read_bytes() != b"K" * 32
        assert stat.S_IMODE(
            (isolated / ".tracker-csrf-signing-key-v1").stat().st_mode
        ) == 0o600
        with sqlite3.connect(isolated / "tracker-auth.sqlite3") as db:
            assert db.execute(
                "SELECT COUNT(*) FROM sessions"
            ).fetchone()[0] == 0
            assert db.execute(
                "SELECT COUNT(*) FROM tracker_secondary_sessions430"
            ).fetchone()[0] == 0
            assert db.execute(
                "SELECT COUNT(*) FROM failures"
            ).fetchone()[0] == 0
            assert db.execute(
                "SELECT COUNT(*) FROM tracker_secondary_failures430"
            ).fetchone()[0] == 0
            assert db.execute(
                "SELECT id,enabled FROM users ORDER BY id"
            ).fetchall() == [(1, 1), (2, 0), (3, 0)]
        for uid in (2, 3):
            with sqlite3.connect(
                isolated / "users" / str(uid) / "tracker.db"
            ) as db:
                assert db.execute(
                    "SELECT name FROM compounds"
                ).fetchall() == [(f"PRIVATE-445-{uid}",)]
        return original(isolated, ids, manifest)

    monkeypatch.setattr(mod, "_check_recovered445", observe)
    result = rehearse_archive445(archive, scratch_parent=scratch)

    assert result["rehearsal_passed"] is True
    assert result["user_count"] == 2
    assert result["private_databases_verified"] == 2
    assert result["private_uploads_verified"] == 2
    assert result["admin_sessions_invalidated"] == 1
    assert result["secondary_sessions_invalidated"] == 2
    assert result["signing_key_rotated"] is True
    assert result["normal_login_enabled"] is False
    assert result["listener_started"] is False
    assert result["live_data_modified"] is False
    assert result["globally_atomic"] is False
    assert result["sandbox_destroyed"] is True
    assert not seen["sandbox"].exists()
    assert list(scratch.iterdir()) == []
    assert _live_hashes(root) == before
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == encrypted_before


def test_rehearsal_removes_disposable_tree_on_validation_failure(
    backup, monkeypatch,
):
    from app import secondary_restore_rehearsal445 as mod
    root, archive, scratch = backup
    before = _live_hashes(root)
    captured = []

    def broken(path, ids, manifest):
        captured.append(path.parent)
        raise ValueError("Synthetic integrity failure")

    monkeypatch.setattr(mod, "_check_recovered445", broken)
    with pytest.raises(ValueError, match="Synthetic"):
        rehearse_archive445(archive, scratch_parent=scratch)
    assert captured and not captured[0].exists()
    assert list(scratch.iterdir()) == []
    assert _live_hashes(root) == before


def test_live_data_dir_never_accepted_as_rehearsal_parent(backup):
    root, archive, scratch = backup
    with pytest.raises(ValueError, match="outside live"):
        rehearse_archive445(archive, scratch_parent=root)
    with pytest.raises(ValueError, match="outside live"):
        rehearse_archive445(
            archive, scratch_parent=root / "users" / "2",
        )
    assert not list(scratch.iterdir())


def test_corrupt_archive_refused_before_materializing(backup, tmp_path):
    root, archive, scratch = backup
    before = _live_hashes(root)
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(archive) as zin, zipfile.ZipFile(
        tampered, "w", compression=zipfile.ZIP_DEFLATED,
    ) as zout:
        for item in zin.infolist():
            data = zin.read(item)
            if item.filename == "users/2/uploads/labs/private-lab-2.txt":
                data = b"REPLACED-PRIVATE-CONTENT"
            zout.writestr(item.filename, data)
    tampered.chmod(0o600)
    with pytest.raises(ValueError):
        rehearse_archive445(tampered, scratch_parent=scratch)
    assert list(scratch.iterdir()) == []
    assert _live_hashes(root) == before


def test_symlinked_archive_and_unsafe_permissions_rejected(backup):
    root, archive, scratch = backup
    alias = archive.parent / "symlink.zip"
    alias.symlink_to(archive)
    with pytest.raises(ValueError, match="Symlinked"):
        rehearse_archive445(alias, scratch_parent=scratch)
    alias.unlink()

    archive.chmod(0o644)
    with pytest.raises(ValueError, match="0600"):
        rehearse_archive445(archive, scratch_parent=scratch)
    archive.chmod(0o600)


def test_prod_protection_and_no_workspace_activation(backup, monkeypatch):
    root, archive, scratch = backup
    before = _live_hashes(root)

    monkeypatch.setattr(config, "instance_label", lambda: "PROD")

    # Rehearsal must work in PROD without restoring live data.
    report = rehearse_archive445(archive, scratch_parent=scratch)

    assert report["rehearsal_passed"] is True
    assert report["live_data_modified"] is False
    assert report["listener_started"] is False
    assert report["sandbox_destroyed"] is True
    assert _live_hashes(root) == before
    assert list(scratch.iterdir()) == []

    with sqlite3.connect(root / "tracker-auth.sqlite3") as db:
        assert db.execute(
            "SELECT id,enabled FROM users WHERE id>1 ORDER BY id"
        ).fetchall() == [(2, 0), (3, 0)]


def test_encrypted_rehearsal_uses_only_disposable_plaintext(
    backup, monkeypatch, tmp_path,
):
    from app import secondary_restore_rehearsal445 as mod
    root, archive, scratch = backup
    before = _live_hashes(root)
    encrypted = tmp_path / (archive.name + ".age")
    encrypted.write_bytes(b"test-ciphertext-not-real-age")
    encrypted.chmod(0o600)
    identity = tmp_path / "identity.agekey"
    identity.write_text("TEST IDENTITY NOT REAL")
    identity.chmod(0o600)
    digest = hashlib.sha256(encrypted.read_bytes()).hexdigest()
    seen = []

    def fake_age(args):
        seen.append(args)
        assert args[0:2] == ["-d", "-i"]
        assert args[2] == str(identity)
        assert args[3] == "-o"
        shutil.copyfile(archive, args[4])

    monkeypatch.setattr(mod, "_run_age444", fake_age)
    result = rehearse_encrypted_archive445(
        encrypted, identity=identity,
        expected_sha256=digest, scratch_parent=scratch,
    )
    assert result["rehearsal_passed"]
    assert result["decryption_verified"]
    assert result["admin_sessions_invalidated"] == 1
    assert result["secondary_sessions_invalidated"] == 2
    assert list(scratch.iterdir()) == []
    assert len(seen) == 1
    assert not Path(seen[0][4]).exists()
    assert _live_hashes(root) == before

    with pytest.raises(ValueError, match="checksum"):
        rehearse_encrypted_archive445(
            encrypted, identity=identity,
            expected_sha256="0" * 64, scratch_parent=scratch,
        )


def test_no_encrypted_rehearsal_with_wrong_identity_or_prod(
    backup, monkeypatch, tmp_path,
):
    from app import secondary_restore_rehearsal445 as mod

    root, archive, scratch = backup
    before = _live_hashes(root)

    encrypted = tmp_path / (archive.name + ".age")
    encrypted.write_bytes(b"test-ciphertext-not-real-age")
    encrypted.chmod(0o600)

    identity = tmp_path / "id.agekey"
    identity.write_text("test")
    identity.chmod(0o644)

    # Insecure private-key permissions are always rejected.
    with pytest.raises(ValueError, match="0600"):
        rehearse_encrypted_archive445(
            encrypted, identity=identity, scratch_parent=scratch,
        )

    identity.chmod(0o600)
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")

    calls = []

    def fake_decrypt(args):
        calls.append(args)
        assert args[:2] == ["-d", "-i"]
        assert args[2] == str(identity)
        assert args[3] == "-o"
        assert args[-1] == str(encrypted)
        shutil.copyfile(archive, args[4])

    monkeypatch.setattr(mod, "_run_age444", fake_decrypt)

    report = rehearse_encrypted_archive445(
        encrypted, identity=identity, scratch_parent=scratch,
    )

    assert report["rehearsal_passed"] is True
    assert report["decryption_verified"] is True
    assert report["live_data_modified"] is False
    assert report["sandbox_destroyed"] is True
    assert len(calls) == 1
    assert list(scratch.iterdir()) == []
    assert _live_hashes(root) == before


def test_restored_signing_key_generated_even_if_archive_missing_key(
    backup, tmp_path,
):
    root, archive, scratch = backup
    # A recovery archive without a key remains valid in 442.
    # Repacking the manifest accurately exercises the missing-key branch.
    members = {}
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            members[name] = z.read(name)
    members.pop(".tracker-csrf-signing-key-v1")
    import json
    manifest = json.loads(members["manifest.json"])
    manifest["key_included"] = False
    manifest["files"].pop(".tracker-csrf-signing-key-v1")
    members["manifest.json"] = json.dumps(manifest).encode()
    target = tmp_path / "no-key.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for name, blob in members.items():
            z.writestr(name, blob)
    target.chmod(0o600)
    result = rehearse_archive445(target, scratch_parent=scratch)
    assert result["signing_key_rotated"]
    assert result["user_count"] == 2
    assert list(scratch.iterdir()) == []


def test_readiness_and_cli_explicitly_disclaim_live_restore():
    from pathlib import Path
    cli = Path("scripts/tracker-secondary-rehearsal445.py").read_text()
    module = Path("app/secondary_restore_rehearsal445.py").read_text()
    assert 'choices=("zip", "encrypted")' in cli
    assert "os.geteuid() != 0" in cli
    assert "LIVE_DATA_MODIFIED=NO" in cli
    assert "NO live restore" in cli
    assert "DELETE FROM sessions" in module
    assert "DELETE FROM tracker_secondary_sessions430" in module
    assert "signing_key_rotated" in module
    assert "SANDBOX_PREFIX" in module
    assert "verify_staged_workspace426" in module
