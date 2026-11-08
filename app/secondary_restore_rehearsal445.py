"""Release 445: disposable recovery rehearsal with session invalidation.

Restores a verified Release 442 archive *only* into a private temporary
directory, provisions the required inactive secondary folder skeleton, clears
restored admin/secondary sessions and failure history, rotates the copied CSRF
signing key, checks every file checksum and workspace marker, and then deletes
the disposable tree. Does NOT restore into live data, enable accounts or start
a listener. Per-database backups remain non-atomic across accounts.
"""
import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import closing
import stat
import tempfile
import zipfile
from pathlib import Path

from . import config
from .secondary_backup442 import (
    AUTH_NAME, KEY_NAME, _no_links, _check_sqlite,
    verify_secondary_backup442, _safe_member,
)
from .secondary_encrypted_export444 import (
    _dev443, _private_file444, _run_age444, _digest444, MAX_ENCRYPTED,
)
from .user_bootstrap426 import verify_staged_workspace426

SANDBOX_PREFIX = "tracker-secondary-rehearsal445-"


def _sandbox_parent445(parent):
    live = _no_links(Path(config.DATA_DIR).absolute())
    parent = _no_links(Path(parent if parent is not None else "/var/tmp").absolute())
    if not parent.is_dir() or parent.is_symlink():
        raise ValueError("Rehearsal parent directory unavailable")
    # No rehearsal files may be created below the live data root.
    if parent == live or parent.is_relative_to(live):
        raise ValueError("Rehearsal must be outside live Tracker data")
    return parent


def _digest_stream445(source, destination, expected):
    if (type(expected) is not dict or set(expected) != {"sha256", "bytes"}
        or type(expected["bytes"]) is not int or expected["bytes"] < 0
        or type(expected["sha256"]) is not str):
        raise ValueError("Malformed recovered file metadata")
    h = hashlib.sha256()
    total = 0
    with destination.open("xb") as out:
        os.chmod(destination, 0o600)
        while True:
            block = source.read(1024 * 1024)
            if not block:
                break
            total += len(block)
            if total > expected["bytes"]:
                raise ValueError("Recovered file exceeds expected size")
            out.write(block)
            h.update(block)
    if total != expected["bytes"] or h.hexdigest() != expected["sha256"]:
        raise ValueError("Recovered file checksum mismatch")


def _read_manifest445(archive):
    with zipfile.ZipFile(archive) as z:
        raw = z.read("manifest.json")
    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate manifest key")
            result[key] = value
        return result
    manifest = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=no_duplicates)
    if type(manifest) is not dict or type(manifest.get("files")) is not dict:
        raise ValueError("Malformed recovery manifest")
    return manifest


def _restore_files445(archive, data_root, expected_files, ids, key_included):
    """All member names were validated by verify_secondary_backup442.

    A second checksum validation while extracting defeats archive substitution
    between verification and this disposable materialization.
    """
    with zipfile.ZipFile(archive) as z:
        members = {info.filename: info for info in z.infolist()}
        if set(members) != set(expected_files) | {"manifest.json"}:
            raise ValueError("Recovery archive changed since verification")
        for name, metadata in sorted(expected_files.items()):
            _safe_member(name, ids, key_included)
            info = members[name]
            # Duplicate entries or special file types are never extracted.
            if info.is_dir() or stat.S_IFMT(info.external_attr >> 16) not in (
                0, stat.S_IFREG,
            ):
                raise ValueError("Non-regular recovery member")
            target = data_root.joinpath(*name.split("/"))
            if not target.is_relative_to(data_root):
                raise ValueError("Unexpected recovery path")
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with z.open(info) as source:
                _digest_stream445(source, target, metadata)


def _invalidate445(auth_db, signing_key, original_key_included):
    """Only modifies the restored database and disposable signing key."""
    with closing(sqlite3.connect(auth_db)) as conn, conn as db:
        db.execute("PRAGMA foreign_keys=ON")
        tables = {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if not {"users", "sessions"} <= tables:
            raise ValueError("Restored authentication schema incomplete")
        db.execute("BEGIN IMMEDIATE")
        try:
            cleared_admin = db.execute("DELETE FROM sessions").rowcount
            cleared_secondary = 0
            if "tracker_secondary_sessions430" in tables:
                cleared_secondary = db.execute(
                    "DELETE FROM tracker_secondary_sessions430"
                ).rowcount
            if "failures" in tables:
                db.execute("DELETE FROM failures")
            if "tracker_secondary_failures430" in tables:
                db.execute("DELETE FROM tracker_secondary_failures430")
            db.commit()
        except BaseException:
            db.rollback()
            raise
        # Verify all sessions are gone and no secondary account was activated.
        if db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]:
            raise RuntimeError("Administrator sessions survived rehearsal")
        if ("tracker_secondary_sessions430" in tables and
            db.execute(
                "SELECT COUNT(*) FROM tracker_secondary_sessions430"
            ).fetchone()[0]):
            raise RuntimeError("Secondary sessions survived rehearsal")
        if db.execute(
            "SELECT 1 FROM users WHERE id>1 AND enabled<>0 LIMIT 1"
        ).fetchone():
            raise RuntimeError("Rehearsal activated a secondary account")

    original_key = (
        signing_key.read_bytes() if original_key_included else None
    )
    rotated = secrets.token_bytes(32)
    if original_key is not None and (len(original_key) != 32 or rotated == original_key):
        raise ValueError("Recovery signing-key rotation failed")
    # No original signing key is returned or copied out of the sandbox.
    with signing_key.open("wb") as f:
        f.write(rotated)
    os.chmod(signing_key, 0o600)
    return cleared_admin, cleared_secondary


def _check_recovered445(data_root, ids, manifest):
    expected = manifest["files"]
    from .secondary_backup442 import _digest_file
    from .user_storage388 import planned_storage

    if (data_root / "tracker.db").exists():
        raise ValueError("Administrator workspace must not be restored here")
    recovered_ids = _check_sqlite(data_root / AUTH_NAME)
    if recovered_ids != ids:
        raise ValueError("Restored secondary account inventory differs")
    for uid in ids:
        paths = planned_storage(uid, data_root)
        for folder in (paths.root / "uploads", paths.coa, paths.labs, paths.backups):
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        verify_staged_workspace426(uid, data_root)
        # Each tenant database must be byte-for-byte the archived snapshot.
        db_member = f"users/{uid}/tracker.db"
        if _digest_file(paths.database) != expected[db_member]:
            raise ValueError("Restored private database differs from backup")

    uploads_verified = 0
    for name, meta in expected.items():
        if "/uploads/" in name:
            if _digest_file(data_root.joinpath(*name.split("/"))) != meta:
                raise ValueError("Restored private upload checksum mismatch")
            uploads_verified += 1
    with closing(sqlite3.connect(data_root / AUTH_NAME)) as conn, conn as db:
        if db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] != 0:
            raise ValueError("Administrator sessions were not invalidated")
        tables = {x[0] for x in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if "tracker_secondary_sessions430" in tables and db.execute(
            "SELECT COUNT(*) FROM tracker_secondary_sessions430"
        ).fetchone()[0] != 0:
            raise ValueError("Secondary sessions were not invalidated")
    return uploads_verified


def rehearse_archive445(archive, *, scratch_parent=None):
    """Validate and stage a recovery into auto-destroyed temporary storage."""
    _dev443()
    archive = _private_file444(archive, expected_suffix=".zip")
    scratch = _sandbox_parent445(scratch_parent)
    before_digest = _digest444(archive)
    report = verify_secondary_backup442(archive)
    manifest = _read_manifest445(archive)
    if report["user_ids"] != manifest.get("user_ids"):
        raise ValueError("Recovered account identity inconsistent")

    with tempfile.TemporaryDirectory(prefix=SANDBOX_PREFIX, dir=scratch) as temporary:
        isolated = Path(temporary)
        data_root = isolated / "data"
        data_root.mkdir(mode=0o700)
        _restore_files445(
            archive, data_root, manifest["files"],
            report["user_ids"], manifest["key_included"],
        )
        admin_revoked, secondary_revoked = _invalidate445(
            data_root / AUTH_NAME, data_root / KEY_NAME,
            manifest["key_included"],
        )
        uploads = _check_recovered445(data_root, report["user_ids"], manifest)
        if _digest444(archive) != before_digest:
            raise RuntimeError("Backup changed during disposable rehearsal")

    return {
        "rehearsal_passed": True,
        "user_count": report["user_count"],
        "private_databases_verified": report["user_count"],
        "private_uploads_verified": uploads,
        "admin_sessions_invalidated": admin_revoked,
        "secondary_sessions_invalidated": secondary_revoked,
        "signing_key_rotated": True,
        "normal_login_enabled": False,
        "listener_started": False,
        "live_data_modified": False,
        "globally_atomic": False,
        "sandbox_destroyed": True,
    }


def rehearse_encrypted_archive445(encrypted, *, identity,
                                 expected_sha256=None, scratch_parent=None):
    """Decrypt externally supplied archive only into disposable storage."""
    _dev443()
    encrypted = _private_file444(encrypted, expected_suffix=".zip.age")
    identity = _private_file444(identity)
    if not 0 < encrypted.stat().st_size <= MAX_ENCRYPTED:
        raise ValueError("Encrypted recovery archive exceeds size limit")
    import re
    if (expected_sha256 is not None and
        (type(expected_sha256) is not str or
         not re.fullmatch(r"[a-f0-9]{64}", expected_sha256))):
        raise ValueError("Invalid encrypted checksum")
    before_digest = _digest444(encrypted)
    if expected_sha256 is not None and before_digest != expected_sha256:
        raise ValueError("Encrypted archive checksum mismatch")
    scratch = _sandbox_parent445(scratch_parent)
    with tempfile.TemporaryDirectory(prefix=SANDBOX_PREFIX, dir=scratch) as temporary:
        plaintext = Path(temporary) / "decrypted.zip"
        _run_age444([
            "-d", "-i", str(identity), "-o", str(plaintext), str(encrypted),
        ])
        if not plaintext.is_file():
            raise ValueError("Decryption did not create an archive")
        os.chmod(plaintext, 0o600)
        report = rehearse_archive445(
            plaintext, scratch_parent=scratch,
        )
    if _digest444(encrypted) != before_digest:
        raise RuntimeError("Encrypted recovery archive changed")
    return {**report, "decryption_verified": True}
