import sqlite3
import pytest
from app.backup import create_backup, verify_named_backup


def test_verify_named_archive(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    with sqlite3.connect(data / 'tracker.db') as conn:
        conn.execute('CREATE TABLE sample (value INTEGER)')
    target = tmp_path / 'backups'
    archive = create_backup(data, target)
    assert 'tracker.db' in verify_named_backup(archive.name, target)['files']


@pytest.mark.parametrize('name', ['../tracker-evil.zip', '/tmp/tracker-evil.zip', 'other.zip', 'tracker-foo.zip/../../etc/passwd', 'tracker-foo\\bad.zip'])
def test_verify_named_rejects_invalid_path(tmp_path, name):
    with pytest.raises(ValueError):
        verify_named_backup(name, tmp_path)


def test_verify_named_rejects_missing_archive(tmp_path):
    with pytest.raises(ValueError):
        verify_named_backup('tracker-missing.zip', tmp_path)
