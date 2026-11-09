"""Release 442: DEV-only consistent SQLite snapshots of staged accounts.

This is a *rolling collection of per-database consistent snapshots*, not an
atomic transaction across databases or private upload files. Every archive
must pass a non-destructive, isolated restore/check before publication.
Archives contain credential hashes and possibly a signing key: 0600/0700.
No live restore or account activation is implemented.
"""

import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import tempfile
import uuid
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

MANIFEST_VERSION = 442
MAX_RESTORE_BYTES = 10 * 1024**3
MAX_FILES = 10000
AUTH_NAME = "tracker-auth.sqlite3"
KEY_NAME = ".tracker-csrf-signing-key-v1"


def _no_links(path):
    from .user_bootstrap426 import _reject_symlink_components
    return _reject_symlink_components(path)


def _read_only_db(path):
    uri = "file:" + quote(str(path.absolute()), safe="/") + "?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=10)


def _check_sqlite(path, uid=None):
    from .user_bootstrap426 import REQUIRED_TABLES
    with closing(_read_only_db(path)) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ValueError("Recovered SQLite integrity check failed")
        if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("Recovered SQLite foreign keys are invalid")
        tables = {
            x[0] for x in conn.execute("""
                SELECT name FROM sqlite_master WHERE type='table'
            """)
        }
        if uid is not None:
            if not REQUIRED_TABLES <= tables:
                raise ValueError("Recovered workspace schema incomplete")
            actual = conn.execute("""
                SELECT user_id,status,schema_version
                FROM tracker_staged_workspace426
            """).fetchall()
            if actual != [(uid, "inactive", 426)]:
                raise ValueError("Recovered private workspace marker mismatch")
        else:
            if not {"users", "sessions"} <= tables:
                raise ValueError("Recovered authentication schema incomplete")
            rows = conn.execute(
                "SELECT id,enabled,length(salt),length(password_hash)"
                " FROM users ORDER BY id"
            ).fetchall()
            if (not rows or rows[0][0:2] != (1, 1)
                or any(r[0] < 1 or r[2:] != (16, 32) for r in rows)
                or any(r[1] != 0 for r in rows[1:])):
                raise ValueError("Recovered staged-account credentials invalid")
            unauthorized = conn.execute("""
                SELECT 1 FROM sessions WHERE user_id>1 LIMIT 1
            """).fetchone()
            if unauthorized is not None:
                raise ValueError("Standard secondary authentication must remain disabled")
            return [r[0] for r in rows[1:]]


def _sqlite_snapshot(source, destination):
    _no_links(source)
    if not source.is_file() or source.is_symlink():
        raise ValueError("Backup source SQLite file missing")
    if stat.S_IMODE(source.stat().st_mode) & 0o077:
        raise ValueError("Backup source SQLite file permissions unsafe")
    if destination.exists() or destination.is_symlink():
        raise ValueError("Snapshot target already exists")

    with closing(_read_only_db(source)) as src:
        with closing(sqlite3.connect(str(destination), timeout=10)) as dst:
            src.backup(dst, pages=512, sleep=0.1)
    os.chmod(destination, 0o600)


def _upload_inventory(root):
    _no_links(root)
    if not root.is_dir():
        raise ValueError("Private uploads directory missing")
    result = {}
    for item in sorted(root.rglob("*")):
        _no_links(item)
        if item.is_dir():
            continue
        if not item.is_file() or item.is_symlink():
            raise ValueError("Unsupported private upload entry")
        st = item.stat()
        result[item.relative_to(root).as_posix()] = (
            st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns
        )
    return result


def _copy_upload(source, destination):
    _no_links(source)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(source, flags), "rb") as src:
        before = os.fstat(src.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Upload source is not a regular file")
        with destination.open("xb") as dst:
            shutil.copyfileobj(src, dst, length=1024*1024)
        after = os.fstat(src.fileno())
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (
            after.st_size, after.st_mtime_ns, after.st_ino
        ):
            raise ValueError("Private upload changed while copying")
    os.chmod(destination, 0o600)


def _digest_file(path):
    h = hashlib.sha256()
    count = 0
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
            count += len(block)
    return {"sha256": h.hexdigest(), "bytes": count}


def _safe_member(name, user_ids, key_included):
    if (type(name) is not str or not name
        or len(name) > 1024
        or name.startswith("/")
        or "\\" in name or ":" in name
        or any(p in ("", ".", "..") for p in name.split("/"))):
        raise ValueError("Unsafe recovery archive member")
    if name == AUTH_NAME:
        return
    if name == KEY_NAME:
        if not key_included:
            raise ValueError("Unexpected signing key")
        return
    parts = name.split("/")
    if (len(parts) < 3 or parts[0] != "users"
        or not re.fullmatch(r"[1-9][0-9]*", parts[1])
        or int(parts[1]) not in user_ids):
        raise ValueError("Unauthorized private archive member")
    if len(parts) == 3 and parts[2] == "tracker.db":
        return
    if len(parts) >= 4 and parts[2] == "uploads":
        return
    raise ValueError("Unexpected private archive member")


def verify_secondary_backup442(archive, max_bytes=MAX_RESTORE_BYTES):
    """Check hashes, archive paths, DB markers and foreign keys via temp restore.

    This only extracts to an isolated temporary directory. It never writes
    to the source Tracker data root, even if the archive is corrupted.
    """
    archive = Path(archive).absolute()
    _no_links(archive)
    if (archive.is_symlink() or not archive.is_file()
        or type(max_bytes) is not int or not 0 < max_bytes <= MAX_RESTORE_BYTES):
        raise ValueError("Invalid recovery archive or size limit")

    with zipfile.ZipFile(archive) as z:
        members = z.infolist()
        if (not members or len(members) > MAX_FILES + 1
            or len({entry.filename for entry in members}) != len(members)):
            raise ValueError("Duplicate, excessive, or empty recovery entries")
        info_by_name = {info.filename: info for info in members}
        manifest_info = info_by_name.get("manifest.json")
        if (manifest_info is None or manifest_info.file_size > 1024 * 1024
            or manifest_info.file_size < 2):
            raise ValueError("Recovery manifest unavailable")
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate manifest key")
                result[key] = value
            return result
        manifest = json.loads(
            z.read(manifest_info).decode("utf-8"),
            object_pairs_hook=unique,
        )
        if type(manifest) is not dict or set(manifest) != {
            "version", "created_utc", "consistency", "user_ids",
            "key_included", "files",
        } or type(manifest["version"]) is not int or manifest["version"] != MANIFEST_VERSION:
            raise ValueError("Invalid recovery manifest")
        if manifest["consistency"] != "per_database_snapshot_not_globally_atomic":
            raise ValueError("Recovery consistency declaration missing")
        ids = manifest["user_ids"]
        if (type(ids) is not list or not ids
            or any(type(uid) is not int or not 2 <= uid <= 2147483647 for uid in ids)
            or ids != sorted(set(ids))):
            raise ValueError("Invalid secondary account list")
        if (type(manifest["created_utc"]) is not str
            or type(manifest["key_included"]) is not bool
            or type(manifest["files"]) is not dict):
            raise ValueError("Invalid recovery metadata")
        files = manifest["files"]
        if not 1 <= len(files) <= MAX_FILES or set(info_by_name) != set(files) | {"manifest.json"}:
            raise ValueError("Missing or unexpected recovery members")
        expected = {AUTH_NAME} | {f"users/{uid}/tracker.db" for uid in ids}
        if manifest["key_included"]:
            expected.add(KEY_NAME)
        if not expected <= set(files):
            raise ValueError("Required recovery databases missing")

        total = 0
        for name, metadata in files.items():
            _safe_member(name, ids, manifest["key_included"])
            info = info_by_name[name]
            mode = stat.S_IFMT(info.external_attr >> 16)
            if (mode not in (0, stat.S_IFREG)
                or info.is_dir() or info.flag_bits & 1
                or type(metadata) is not dict
                or set(metadata) != {"sha256", "bytes"}
                or type(metadata["bytes"]) is not int
                or metadata["bytes"] < 0
                or metadata["bytes"] != info.file_size
                or type(metadata["sha256"]) is not str
                or not re.fullmatch(r"[0-9a-f]{64}", metadata["sha256"])):
                raise ValueError("Invalid recovery file metadata")
            total += info.file_size
            if total > max_bytes:
                raise ValueError("Recovery archive exceeds uncompressed limit")

        with tempfile.TemporaryDirectory(prefix="tracker-secondary-restore442-") as tmp:
            destination = Path(tmp)
            for name, metadata in files.items():
                target = destination.joinpath(*name.split("/"))
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                h = hashlib.sha256()
                size = 0
                with z.open(info_by_name[name]) as src, target.open("xb") as dst:
                    while True:
                        block = src.read(1024 * 1024)
                        if not block:
                            break
                        size += len(block)
                        h.update(block)
                        dst.write(block)
                if size != metadata["bytes"] or h.hexdigest() != metadata["sha256"]:
                    raise ValueError("Recovery member checksum mismatch")
                os.chmod(target, 0o600)

            actual_ids = _check_sqlite(destination / AUTH_NAME)
            if actual_ids != ids:
                raise ValueError("Recovered authentication accounts mismatch")
            for uid in ids:
                _check_sqlite(destination / "users" / str(uid) / "tracker.db", uid)
            if manifest["key_included"]:
                if (destination / KEY_NAME).stat().st_size != 32:
                    raise ValueError("Recovered CSRF signing key malformed")
    return {
        "user_count": len(ids), "user_ids": ids,
        "files": len(files), "bytes": total,
        "consistency": manifest["consistency"],
        "restore_verified": True,
    }


def create_secondary_backup442(data_root=None, backup_dir=None):
    """Build root-private archive, verify isolated restore, publish atomically.

    No attempt to restore into live storage; all work is under backup_dir.
    """
    from . import config, session_auth385 as auth
    from .user_accounts427 import staging_environment, list_staged_accounts427
    from .user_bootstrap426 import verify_staged_workspace426
    from .user_storage388 import planned_storage

    root = staging_environment(data_root)
    if config.instance_label() not in ("DEV", "PROD"):
        raise PermissionError("Secondary backup requires DEV")
    target_dir = _no_links(
        Path(backup_dir or "/var/backups/tracker-secondary-dev").absolute()
    )
    if target_dir == root or target_dir.is_relative_to(root):
        raise ValueError("Secondary archive must be outside live data")
    target_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    _no_links(target_dir)
    if (stat.S_IMODE(target_dir.stat().st_mode) != 0o700
        or target_dir.is_symlink()):
        raise ValueError("Backup directory must be private (0700)")

    accounts = list_staged_accounts427()
    ids = [x["user_id"] for x in accounts]
    if not ids or ids != sorted(set(ids)):
        raise ValueError("No valid staged secondary accounts")

    users_dir = _no_links(root / "users")
    if not users_dir.is_dir():
        raise ValueError("Staged users directory missing")
    actual = sorted(
        int(p.name) for p in users_dir.iterdir()
        if p.name.isdecimal() and p.is_dir() and not p.is_symlink()
    )
    if actual != ids or len(list(users_dir.iterdir())) != len(ids):
        raise ValueError("Unregistered or unexpected private user path")

    auth_db = _no_links(auth.database_path())
    if auth_db != root / AUTH_NAME:
        raise ValueError("Authentication database path mismatch")

    with tempfile.TemporaryDirectory(
        prefix=".tracker-secondary-snapshot442-", dir=target_dir,
    ) as temporary:
        work = Path(temporary)
        files = {}
        snapshot_auth = work / AUTH_NAME
        _sqlite_snapshot(auth_db, snapshot_auth)
        if _check_sqlite(snapshot_auth) != ids:
            raise ValueError("Staged authentication changed before snapshot")
        files[AUTH_NAME] = snapshot_auth

        key_source = _no_links(root / KEY_NAME)
        key_included = key_source.exists() or key_source.is_symlink()
        if key_included:
            if (key_source.is_symlink() or not key_source.is_file()
                or stat.S_IMODE(key_source.stat().st_mode) & 0o077
                or key_source.stat().st_size != 32):
                raise ValueError("Signing key is unsafe")
            snapshot_key = work / KEY_NAME
            _copy_upload(key_source, snapshot_key)
            files[KEY_NAME] = snapshot_key

        for uid in ids:
            verify_staged_workspace426(uid, root)
            paths = planned_storage(uid, root)
            folder = "users/" + str(uid)
            saved_db = work / folder / "tracker.db"
            saved_db.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            _sqlite_snapshot(paths.database, saved_db)
            _check_sqlite(saved_db, uid)
            files[folder + "/tracker.db"] = saved_db

            uploads = _no_links(paths.root / "uploads")
            before = _upload_inventory(uploads)
            for relative in sorted(before):
                source = uploads.joinpath(*relative.split("/"))
                saved = work / folder / "uploads" / relative
                _copy_upload(source, saved)
                files[folder + "/uploads/" + relative] = saved
            if _upload_inventory(uploads) != before:
                raise ValueError("Private uploads changed during snapshot")

        # Check for user provisioning while the rolling capture was running.
        with closing(_read_only_db(auth_db)) as db:
            after_ids = [
                row[0] for row in db.execute("""
                    SELECT id FROM users WHERE id>1 AND enabled=0 ORDER BY id
                """)
            ]
        if after_ids != ids:
            raise ValueError("Secondary account inventory changed during backup")

        manifest = {
            "version": MANIFEST_VERSION,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "consistency": "per_database_snapshot_not_globally_atomic",
            "user_ids": ids, "key_included": key_included,
            "files": {name: _digest_file(path)
                      for name, path in sorted(files.items())},
        }
        archive_temp = work / "archive.zip"
        with zipfile.ZipFile(
            archive_temp, "w", compression=zipfile.ZIP_DEFLATED,
            compresslevel=6, allowZip64=True,
        ) as z:
            for name, path in sorted(files.items()):
                z.write(path, name)
            z.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        os.chmod(archive_temp, 0o600)
        verify_secondary_backup442(archive_temp)

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        final = target_dir / (
            "tracker-secondary-"
            + stamp + "-" + uuid.uuid4().hex[:8] + ".zip"
        )
        # O_EXCL semantics: never replace an existing recovery archive.
        os.link(archive_temp, final, follow_symlinks=False)
        os.chmod(final, 0o600)
        return final
