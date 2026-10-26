import sqlite3
import zipfile
from pathlib import Path
import pytest
from app.backup import create_backup, verify_backup, prune_backups


def test_backup_includes_database_and_uploads(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    db = data / 'tracker.db'
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE sample (value TEXT)')
        conn.execute("INSERT INTO sample VALUES ('saved')")
    upload = data / 'uploads' / 'coa' / 'example.pdf'
    upload.parent.mkdir(parents=True)
    upload.write_bytes(b'%PDF-test')
    archive = create_backup(data, tmp_path / 'backups')
    manifest = verify_backup(archive)
    assert set(manifest['files']) == {'tracker.db', 'uploads/coa/example.pdf'}
    with zipfile.ZipFile(archive) as z:
        assert z.read('uploads/coa/example.pdf') == b'%PDF-test'


def test_tampering_is_detected(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    with sqlite3.connect(data / 'tracker.db') as conn:
        conn.execute('CREATE TABLE t (id INTEGER)')
    archive = create_backup(data, tmp_path / 'backups')
    with zipfile.ZipFile(archive, 'a') as z:
        z.writestr('unexpected.txt', 'oops')
    with pytest.raises(ValueError):
        verify_backup(archive)


def test_prune_retains_recent(tmp_path):
    for day in ('20261021', '20261022', '20261023'):
        (tmp_path / f'tracker-{day}T010000000000Z.zip').write_bytes(b'x')
    prune_backups(tmp_path, keep=1)
    assert len(list(tmp_path.glob('*.zip'))) == 1
