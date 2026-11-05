import sqlite3
import pytest

from app.backup import create_backup,verify_backup
from app.backup_references341 import required_attachments


def setup_data(tmp_path):
    data=tmp_path/'data'
    data.mkdir()

    with sqlite3.connect(data/'tracker.db') as db:
        db.execute(
            'CREATE TABLE coas (stored_name TEXT,original_name TEXT)'
        )
        db.execute(
            'CREATE TABLE lab_reports (stored_name TEXT,original_name TEXT)'
        )
        db.execute(
            "INSERT INTO coas VALUES ('metadata-no-file','')"
        )
        db.execute(
            "INSERT INTO coas VALUES ('coa.pdf','original.pdf')"
        )
        db.execute(
            "INSERT INTO lab_reports VALUES ('lab.pdf','report.pdf')"
        )

    (data/'uploads'/'coa').mkdir(parents=True)
    (data/'uploads'/'labs').mkdir(parents=True)
    (data/'uploads'/'coa'/'coa.pdf').write_bytes(b'%PDF-COA')
    (data/'uploads'/'labs'/'lab.pdf').write_bytes(b'%PDF-LAB')
    return data


def test_references_and_metadata_only(tmp_path):
    data=setup_data(tmp_path)
    assert required_attachments(data/'tracker.db')=={
        'uploads/coa/coa.pdf','uploads/labs/lab.pdf'
    }

    archive=create_backup(data,tmp_path/'archives')
    assert 'uploads/labs/lab.pdf' in verify_backup(archive)['files']


def test_missing_reference_fails_closed(tmp_path):
    data=setup_data(tmp_path)
    (data/'uploads'/'labs'/'lab.pdf').unlink()

    with pytest.raises(ValueError,match='missing referenced attachment'):
        create_backup(data,tmp_path/'archives')

    assert list((tmp_path/'archives').glob('tracker-*.zip'))==[]


def test_unsafe_filename_is_rejected(tmp_path):
    data=setup_data(tmp_path)

    with sqlite3.connect(data/'tracker.db') as db:
        db.execute(
            "UPDATE coas SET stored_name='../escape' "
            "WHERE original_name='original.pdf'"
        )

    with pytest.raises(ValueError,match='Unsafe attachment reference'):
        create_backup(data,tmp_path/'archives')
