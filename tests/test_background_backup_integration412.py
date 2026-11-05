"""Release 412: real SQLite backup and restore isolation tests.

All archives and data are temporary pytest fixtures; no live backup is run.
"""
import importlib.util
import sqlite3
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import backup, config
from scripts import tracker_backup


ROOT = Path(__file__).resolve().parents[1]


def restore_check(archive):
    source = ROOT / 'scripts' / 'tracker-restore-verify.py'
    spec = importlib.util.spec_from_file_location('restore_check_412', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.restore_check(archive)


def workspace(folder, marker):
    folder.mkdir()
    data = folder / 'data'
    data.mkdir()
    database = data / 'tracker.db'
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE sample(label TEXT NOT NULL)')
        db.execute('INSERT INTO sample VALUES (?)', (marker,))
    upload = data / 'uploads' / 'coa' / 'sample.pdf'
    upload.parent.mkdir(parents=True)
    upload.write_bytes(('%PDF-' + marker).encode())
    archives = folder / 'archives'
    archives.mkdir()
    return SimpleNamespace(
        user_id=1, scope='legacy-admin-instance', data_dir=data,
        database=database, backup_dir=archives,
    )


@pytest.fixture
def spaces(tmp_path):
    return (
        workspace(tmp_path / 'admin', 'ADMIN_ONLY_412'),
        workspace(tmp_path / 'other', 'OTHER_ONLY_412'),
    )


def configure(monkeypatch, admin):
    monkeypatch.setattr(config, 'DATA_DIR', admin.data_dir)
    monkeypatch.setattr(config, 'DB_PATH', admin.database)
    monkeypatch.setattr(config, 'DB_URL', f'sqlite:///{admin.database}')
    monkeypatch.setattr(backup, 'BACKUP_DIR', admin.backup_dir)


def create(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['tracker_backup', 'create'])
    tracker_backup.main()


def test_real_restore_contains_only_authorized_workspace(
    spaces, tmp_path, monkeypatch,
):
    admin, other = spaces
    configure(monkeypatch, admin)
    actions = []

    def verify(archive):
        stats = restore_check(archive)
        assert stats['files'] == 2
        assert stats['uploads'] == 1
        actions.append('restore')

    def prune(*, backup_dir):
        assert backup_dir == admin.backup_dir
        actions.append('prune')
        return backup.prune_backups(backup_dir=backup_dir, keep=90)

    monkeypatch.setattr(tracker_backup, 'verify_restorable', verify)
    monkeypatch.setattr(tracker_backup, 'prune_backups', prune)
    create(monkeypatch)

    files = list(admin.backup_dir.glob('tracker-*.zip'))
    assert len(files) == 1
    assert list(other.backup_dir.iterdir()) == []
    assert actions == ['restore', 'prune']
    assert set(backup.verify_backup(files[0])['files']) == {
        'tracker.db', 'uploads/coa/sample.pdf',
    }

    with zipfile.ZipFile(files[0]) as archive:
        assert archive.read('uploads/coa/sample.pdf') == b'%PDF-ADMIN_ONLY_412'
        snapshot = tmp_path / 'inspect.db'
        snapshot.write_bytes(archive.read('tracker.db'))
    with sqlite3.connect(snapshot) as db:
        assert db.execute('SELECT label FROM sample').fetchall() == [
            ('ADMIN_ONLY_412',)
        ]


def test_restore_failure_preserves_previous_archive(spaces, monkeypatch):
    admin, other = spaces
    old = backup.create_backup(admin.data_dir, admin.backup_dir)
    old_bytes = old.read_bytes()
    configure(monkeypatch, admin)

    def fail(_archive):
        raise RuntimeError('simulated restore failure')

    def forbidden_prune(**_kwargs):
        raise AssertionError('Prune ran after restore failure')

    monkeypatch.setattr(tracker_backup, 'verify_restorable', fail)
    monkeypatch.setattr(tracker_backup, 'prune_backups', forbidden_prune)
    with pytest.raises(RuntimeError, match='simulated restore failure'):
        create(monkeypatch)
    assert old.read_bytes() == old_bytes
    assert len(list(admin.backup_dir.glob('tracker-*.zip'))) == 2
    assert list(other.backup_dir.iterdir()) == []


def test_tampered_archive_is_rejected_without_pruning(spaces, monkeypatch):
    admin, _other = spaces
    old = backup.create_backup(admin.data_dir, admin.backup_dir)
    old_bytes = old.read_bytes()
    configure(monkeypatch, admin)

    def create_tampered(*, data_dir, backup_dir):
        archive = backup.create_backup(data_dir, backup_dir)
        with zipfile.ZipFile(archive, 'a') as contents:
            contents.writestr('unexpected.txt', 'invalid member')
        return archive

    def forbidden_prune(**_kwargs):
        raise AssertionError('Prune ran after tampered restore')

    monkeypatch.setattr(tracker_backup, 'create_backup', create_tampered)
    monkeypatch.setattr(tracker_backup, 'verify_restorable', restore_check)
    monkeypatch.setattr(tracker_backup, 'prune_backups', forbidden_prune)

    # Both an unsafe member rejection and a manifest rejection are valid.
    # Assert the security outcome, not the precise wording of the error.
    with pytest.raises(ValueError):
        create(monkeypatch)
    assert old.read_bytes() == old_bytes
    assert len(list(admin.backup_dir.glob('tracker-*.zip'))) == 2


def test_denied_context_prevents_backup_writes(spaces, monkeypatch):
    admin, other = spaces

    def deny():
        raise PermissionError('Secondary user denied')

    monkeypatch.setattr(tracker_backup, 'administrator_context410', deny)
    with pytest.raises(PermissionError):
        create(monkeypatch)
    assert list(admin.backup_dir.iterdir()) == []
    assert list(other.backup_dir.iterdir()) == []


def test_cross_workspace_url_mismatch_blocks_backup(spaces, monkeypatch):
    admin, other = spaces
    configure(monkeypatch, admin)
    monkeypatch.setattr(config, 'DB_URL', f'sqlite:///{other.database}')
    with pytest.raises(ValueError, match='does not match'):
        create(monkeypatch)
    assert list(admin.backup_dir.iterdir()) == []
    assert list(other.backup_dir.iterdir()) == []


def test_secondary_users_stay_disabled():
    from app.user_storage388 import live_storage_for
    for user_id in (2, 3):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)
