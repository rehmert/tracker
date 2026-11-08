"""Verified, consistent backups of Tracker's SQLite DB and uploads."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .backup_consistency309 import upload_inventory
from .upload_coordination325 import upload_guard
from .backup_references341 import assert_complete

BACKUP_DIR = Path(os.getenv('TRACKER_BACKUP_DIR', str(config.DATA_DIR.parent / 'backups'))).resolve()

# Bound verification work even when inspecting malformed or hostile archives.
# These ceilings are well above ordinary per-vial uploads and database sizes.
MAX_BACKUP_ENTRIES = 50_000
MAX_RESTORED_BYTES = 64 * 1024 * 1024 * 1024


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _verify_db(path: Path) -> None:
    with closing(sqlite3.connect(f'file:{path}?mode=ro', uri=True)) as conn:
        if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite integrity check failed')


def create_backup(data_dir: Path | None = None, backup_dir: Path | None = None) -> Path:
    data = Path(data_dir or config.DATA_DIR).resolve()
    target = Path(backup_dir or BACKUP_DIR).resolve()
    if not (data / 'tracker.db').is_file():
        raise FileNotFoundError(f'Missing database: {data / "tracker.db"}')
    target.mkdir(parents=True, exist_ok=True)
    with upload_guard(data):
        uploads = data / 'uploads'
        upload_before = upload_inventory(uploads)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        final = target / f'tracker-{stamp}.zip'
        with tempfile.TemporaryDirectory(prefix='.tracker-backup-', dir=target) as temp:
            work = Path(temp)
            snapshot = work / 'tracker.db'
            with closing(sqlite3.connect(f'file:{data / "tracker.db"}?mode=ro', uri=True)) as source:
                with closing(sqlite3.connect(snapshot)) as dest:
                    source.backup(dest)
            _verify_db(snapshot)
            entries = [snapshot]
            uploads = data / 'uploads'
            if uploads.exists():
                if uploads.is_symlink():
                    raise ValueError('Uploads directory must not be a symlink')
                for path in sorted(uploads.rglob('*')):
                    if path.is_symlink():
                        raise ValueError(f'Uploads must not contain symlinks: {path}')
                    if path.is_file():
                        entries.append(path)
            names = {'tracker.db'} | {
                path.relative_to(data).as_posix()
                for path in entries if path != snapshot
            }
            assert_complete(snapshot, names)
            manifest = {'version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(), 'files': {}}
            partial = work / 'backup.zip'
            with zipfile.ZipFile(partial, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                for path in entries:
                    name = 'tracker.db' if path == snapshot else path.relative_to(data).as_posix()
                    manifest['files'][name] = {'sha256': _digest(path), 'bytes': path.stat().st_size}
                    z.write(path, name)
                z.writestr('manifest.json', json.dumps(manifest, indent=2))
            verify_backup(partial)
            if upload_inventory(uploads) != upload_before:
                raise ValueError(
                    'Uploads changed during backup; archive withheld'
                )
            os.replace(partial, final)
        return final


def verify_backup(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        entries = z.infolist()
        if len(entries) > MAX_BACKUP_ENTRIES:
            raise ValueError('Backup contains too many files')
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate backup archive entry')
        if sum(entry.file_size for entry in entries) > MAX_RESTORED_BYTES:
            raise ValueError('Backup uncompressed size exceeds safety limit')
        manifest = json.loads(z.read('manifest.json'))
        if not isinstance(manifest, dict):
            raise ValueError('Invalid backup manifest')
        files = manifest.get('files')
        if (
            manifest.get('version') != 1
            or not isinstance(files, dict)
            or 'tracker.db' not in files
        ):
            raise ValueError('Invalid backup manifest')
        expected = set(files) | {'manifest.json'}
        if set(names) != expected:
            raise ValueError('Unexpected or missing archive entries')
        entry_by_name = {entry.filename: entry for entry in entries}
        for name, info in files.items():
            if (
                not isinstance(name, str)
                or name.startswith('/')
                or '..' in Path(name).parts
                or '\\' in name
                or name in ('.', '..', 'manifest.json')
                or not (name == 'tracker.db' or name.startswith('uploads/'))
                or name.endswith('/')
            ):
                raise ValueError('Unsafe archive path')
            if (
                not isinstance(info, dict)
                or type(info.get('bytes')) is not int
                or info['bytes'] < 0
                or entry_by_name[name].file_size != info['bytes']
                or not isinstance(info.get('sha256'), str)
                or len(info['sha256']) != 64
            ):
                raise ValueError(f'Invalid backup file metadata: {name}')
            h = hashlib.sha256()
            count = 0
            with z.open(name) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    h.update(chunk)
                    count += len(chunk)
            if h.hexdigest() != info['sha256'] or count != info['bytes']:
                raise ValueError(f'Checksum mismatch: {name}')
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'tracker.db'
            with z.open('tracker.db') as source, db.open('wb') as dest:
                shutil.copyfileobj(source, dest)
            _verify_db(db)
            assert_complete(db, manifest['files'])
    return manifest


def prune_backups(
    backup_dir: Path | None = None,
    keep: int | None = None
) -> list[Path]:
    """Retain the newest N backup archives."""
    root = Path(backup_dir or BACKUP_DIR)

    if keep is None:
        keep = int(os.getenv("TRACKER_BACKUP_KEEP", "90"))

    if keep < 1:
        raise ValueError("TRACKER_BACKUP_KEEP must be at least 1")

    if not root.exists():
        return []

    archives = sorted(
        root.glob("tracker-*.zip"),
        key=lambda p: p.name,
        reverse=True
    )

    removed = []

    for archive in archives[keep:]:
        archive.unlink()
        removed.append(archive)

    return removed


def list_backups(backup_dir: Path | None = None) -> list[dict]:
    root = Path(backup_dir or BACKUP_DIR)
    return [{'name': p.name, 'size': p.stat().st_size, 'modified': datetime.fromtimestamp(p.stat().st_mtime, timezone.utc)}
            for p in sorted(root.glob('tracker-*.zip'), reverse=True)] if root.exists() else []


def verify_named_backup(name: str, backup_dir: Path | None = None) -> dict:
    """Verify an existing archive selected from the configured backup directory."""
    root = Path(backup_dir or BACKUP_DIR).resolve()
    # Do not allow arbitrary filesystem paths or non-Tracker archives.
    if not name.startswith('tracker-') or not name.endswith('.zip') or Path(name).name != name or '\\' in name:
        raise ValueError('Invalid backup filename')
    archive = root / name
    if archive.is_symlink() or not archive.is_file():
        raise ValueError('Backup archive not found')
    return verify_backup(archive)
