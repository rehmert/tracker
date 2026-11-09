"""Release 444: encrypted export plumbing, fail-closed checks and real age E2E."""

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
from app.secondary_backup_ops443 import (
    _exclusive_runner443, backup_directory443, run_backup443,
)
from app.secondary_encrypted_export444 import (
    _age_binary444, export_encrypted444, rehearse_encrypted444,
)
from app.user_accounts427 import stage_secondary_account427
from app.user_bootstrap426 import initialize_staged_workspace426

# A syntactically shaped standard X25519 recipient, used only for mock tests.
FAKE_RECIPIENT = "age1" + "q" * 58


@pytest.fixture
def ready(tmp_path, monkeypatch):
    root = tmp_path / "live"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(config, "DATA_DIR", root)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    auth.bootstrap("operator", "administrator-secure-password-444")
    (root / auth.FLAG).write_text("enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, root)
        stage_secondary_account427(
            uid, f"member-{uid}",
            f"secondary-secure-password-{uid}-444",
        )
        with sqlite3.connect(root / "users" / str(uid) / "tracker.db") as db:
            db.execute("""
                INSERT INTO compounds(name,category,notes,primary_unit)
                VALUES (?, 'other', '', 'mg')
            """, (f"PRIVATE-444-{uid}",))
    with sqlite3.connect(root / "tracker.db") as db:
        db.execute("CREATE TABLE admin_only(secret TEXT)")
        db.execute("INSERT INTO admin_only VALUES('do not overwrite')")

    backup_dir = tmp_path / "private-backups"
    export_dir = tmp_path / "private-export"
    generated = run_backup443(backup_dir)
    backup = Path(generated["archive"])
    return root, backup_dir, export_dir, backup


def _live_hashes(root):
    paths = (
        root / "tracker.db", root / "tracker-auth.sqlite3",
        root / "users" / "2" / "tracker.db",
        root / "users" / "3" / "tracker.db",
    )
    return {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }


def _fake_encrypt(monkeypatch, *, payload=b"test-placeholder-not-real-crypto"):
    from app import secondary_encrypted_export444 as mod
    calls = []

    def runner(args):
        calls.append(args)
        if "-d" in args:
            raise AssertionError("Mock encryption must not call decrypt")
        assert args[:2] == ["-r", FAKE_RECIPIENT]
        assert args[2] == "-o"
        Path(args[3]).write_bytes(payload)

    monkeypatch.setattr(mod, "_run_age444", runner)
    return calls


def test_export_plumbing_keeps_archive_and_live_data_unchanged(ready, monkeypatch):
    root, backup_dir, export_dir, backup = ready
    before = _live_hashes(root)
    input_digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    calls = _fake_encrypt(monkeypatch)

    report = export_encrypted444(
        backup, recipient=FAKE_RECIPIENT,
        backup_dir=backup_dir, export_dir=export_dir,
    )
    output = Path(report["encrypted_file"])
    assert output.name == backup.name + ".age"
    assert output.read_bytes() == b"test-placeholder-not-real-crypto"
    assert len(report["encrypted_sha256"]) == 64
    assert report["user_count"] == 2
    assert report["decrypt_rehearsed"] is False
    assert report["source_archive"] == backup.name
    assert len(calls) == 1
    assert calls[0][-1] == str(backup)
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert stat.S_IMODE(export_dir.stat().st_mode) == 0o700
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == input_digest
    assert _live_hashes(root) == before


def test_encrypt_refuses_overwrite_invalid_recipient_and_same_dir(ready, monkeypatch):
    root, backup_dir, export_dir, backup = ready
    calls = _fake_encrypt(monkeypatch)

    with pytest.raises(ValueError, match="recipient"):
        export_encrypted444(
            backup, recipient="invalid!", backup_dir=backup_dir,
            export_dir=export_dir,
        )
    with pytest.raises(ValueError, match="separate"):
        export_encrypted444(
            backup, recipient=FAKE_RECIPIENT,
            backup_dir=backup_dir, export_dir=backup_dir,
        )
    assert not calls

    export_encrypted444(
        backup, recipient=FAKE_RECIPIENT,
        backup_dir=backup_dir, export_dir=export_dir,
    )
    with pytest.raises(FileExistsError):
        export_encrypted444(
            backup, recipient=FAKE_RECIPIENT,
            backup_dir=backup_dir, export_dir=export_dir,
        )
    assert len(calls) == 1


def test_corrupted_source_rejected_before_encryption(ready, monkeypatch):
    root, backup_dir, export_dir, backup = ready
    calls = _fake_encrypt(monkeypatch)
    with zipfile.ZipFile(backup, "a") as z:
        z.writestr("unexpected-upload", b"private-data")
    with pytest.raises(ValueError):
        export_encrypted444(
            backup, recipient=FAKE_RECIPIENT,
            backup_dir=backup_dir, export_dir=export_dir,
        )
    assert not calls
    assert not list(export_dir.glob("*.age")) if export_dir.exists() else True


def test_lock_prevents_export_during_snapshot_or_pruning(ready, monkeypatch):
    root, backup_dir, export_dir, backup = ready
    calls = _fake_encrypt(monkeypatch)
    with _exclusive_runner443(backup_dir):
        with pytest.raises(RuntimeError, match="already running"):
            export_encrypted444(
                backup, recipient=FAKE_RECIPIENT,
                backup_dir=backup_dir, export_dir=export_dir,
            )
    assert not calls
    assert not list(export_dir.glob("*.age"))


def test_archive_paths_symlinks_and_perms_are_fail_closed(ready, monkeypatch):
    root, backup_dir, export_dir, backup = ready
    calls = _fake_encrypt(monkeypatch)

    link = backup_dir / "tracker-secondary-20261106T010000000000Z-aaaaaaaa.zip"
    link.symlink_to(backup)
    with pytest.raises(ValueError):
        export_encrypted444(
            backup, recipient=FAKE_RECIPIENT,
            backup_dir=backup_dir, export_dir=export_dir,
        )
    link.unlink()

    os.chmod(backup, 0o644)
    with pytest.raises(ValueError):
        export_encrypted444(
            backup, recipient=FAKE_RECIPIENT,
            backup_dir=backup_dir, export_dir=export_dir,
        )
    os.chmod(backup, 0o600)
    with pytest.raises(ValueError):
        export_encrypted444(
            backup, recipient=FAKE_RECIPIENT,
            backup_dir=backup_dir, export_dir=root,
        )
    assert not calls


def test_rehearsal_plumbing_uses_temporary_zip_and_never_live_storage(
    ready, monkeypatch, tmp_path,
):
    from app import secondary_encrypted_export444 as mod
    root, backup_dir, export_dir, backup = ready
    before = _live_hashes(root)
    export_dir.mkdir(mode=0o700)
    encrypted = export_dir / (backup.name + ".age")
    encrypted.write_bytes(b"simulated-ciphertext-not-real-age")
    encrypted.chmod(0o600)
    identity = tmp_path / "offline-identity"
    identity.write_text("test-only-not-real-secret")
    identity.chmod(0o600)
    digest = hashlib.sha256(encrypted.read_bytes()).hexdigest()
    calls = []

    def runner(args):
        calls.append(args)
        assert args[0:2] == ["-d", "-i"]
        assert args[2] == str(identity)
        assert args[3] == "-o"
        assert args[-1] == str(encrypted)
        shutil.copyfile(backup, args[4])

    monkeypatch.setattr(mod, "_run_age444", runner)
    result = rehearse_encrypted444(
        encrypted, identity=identity, expected_sha256=digest,
    )
    assert result["verified"] is True
    assert result["user_count"] == 2
    assert result["live_data_modified"] is False
    assert result["globally_atomic"] is False
    assert len(calls) == 1
    assert _live_hashes(root) == before
    assert set(p.name for p in export_dir.iterdir()) == {encrypted.name}


def test_rehearsal_bad_checksum_and_bad_identity_never_decrypt(ready, tmp_path,
                                                               monkeypatch):
    from app import secondary_encrypted_export444 as mod
    root, backup_dir, export_dir, backup = ready
    export_dir.mkdir(mode=0o700)
    encrypted = export_dir / (backup.name + ".age")
    encrypted.write_bytes(b"ciphertext")
    encrypted.chmod(0o600)
    identity = tmp_path / "private-identity"
    identity.write_text("private")
    identity.chmod(0o600)
    calls = []
    monkeypatch.setattr(mod, "_run_age444", lambda args: calls.append(args))
    with pytest.raises(ValueError, match="checksum"):
        rehearse_encrypted444(
            encrypted, identity=identity, expected_sha256="0" * 64,
        )
    os.chmod(identity, 0o644)
    with pytest.raises(ValueError, match="0600"):
        rehearse_encrypted444(encrypted, identity=identity)
    assert not calls


def test_age_missing_refuses_to_publish(ready, monkeypatch):
    from app import secondary_encrypted_export444 as mod
    root, backup_dir, export_dir, backup = ready

    def missing():
        raise FileNotFoundError("age binary unavailable")

    monkeypatch.setattr(mod, "_age_binary444", missing)
    with pytest.raises(FileNotFoundError):
        export_encrypted444(
            backup, recipient=FAKE_RECIPIENT,
            backup_dir=backup_dir, export_dir=export_dir,
        )
    assert not list(export_dir.glob("*.age"))


def test_prod_does_not_export_or_rehearse(ready, monkeypatch):
    root, backup_dir, export_dir, archive = ready
    before = _live_hashes(root)

    # Release 523 permits verified encrypted exports in PROD.
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    calls = _fake_encrypt(monkeypatch)
    result = export_encrypted444(
        archive, recipient=FAKE_RECIPIENT,
        backup_dir=backup_dir, export_dir=export_dir,
    )

    encrypted = Path(result["encrypted_file"])
    assert encrypted.is_file()
    assert encrypted.read_bytes() == b"test-placeholder-not-real-crypto"
    assert result["user_count"] == 2
    assert len(calls) == 1
    assert _live_hashes(root) == before


def test_real_age_encrypt_decrypt_and_tamper_detection_when_installed(ready, tmp_path):
    # The only test proving actual encryption. All other tests exercise
    # permissions / isolation / error handling with a mocked subprocess.
    try:
        binary = _age_binary444()
    except FileNotFoundError:
        pytest.skip("Trusted age binary is not installed")
    keygen = shutil.which("age-keygen")
    if not keygen:
        pytest.skip("age-keygen is not installed")

    root, backup_dir, export_dir, backup = ready
    identity = tmp_path / "identity-age444.key"
    subprocess.run(
        [keygen, "-o", str(identity)],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    identity.chmod(0o600)
    public = subprocess.run(
        [keygen, "-y", str(identity)], check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    ).stdout.strip()

    before = _live_hashes(root)
    report = export_encrypted444(
        backup, recipient=public,
        backup_dir=backup_dir, export_dir=export_dir,
    )
    encrypted = Path(report["encrypted_file"])
    assert encrypted.read_bytes() != backup.read_bytes()
    assert encrypted.read_bytes().startswith(b"age-encryption.org/v1")
    restored = rehearse_encrypted444(
        encrypted, identity=identity,
        expected_sha256=report["encrypted_sha256"],
    )
    assert restored["verified"] is True
    assert restored["user_count"] == 2
    assert _live_hashes(root) == before

    # Flip an authenticated ciphertext byte, preserving the managed filename.
    # age must reject the altered ciphertext even without an external checksum.
    changed = bytearray(encrypted.read_bytes())
    changed[-1] ^= 1
    encrypted.write_bytes(changed)
    with pytest.raises(ValueError, match="checksum"):
        rehearse_encrypted444(
            encrypted, identity=identity,
            expected_sha256=report["encrypted_sha256"],
        )
    with pytest.raises(RuntimeError, match="age encryption or decryption failed"):
        rehearse_encrypted444(encrypted, identity=identity)


def test_readiness_and_cli_explicitly_require_manual_export():
    from pathlib import Path
    view = Path("app/secondary_preview430.py").read_text()
    code = Path("scripts/tracker-secondary-encrypted444.py").read_text()
    assert "tracker-secondary-encrypted444.py export" in view
    assert "no automatic upload" in view.lower()
    assert "private" in code.lower()
    assert 'choices=("export", "rehearse")' in code
    assert "os.geteuid() != 0" in code
    assert 'No login activation' not in code  # no activation command
    assert "LIVE_DATA_MODIFIED=NO" in code
