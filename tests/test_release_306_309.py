import sqlite3
import zipfile

import pytest

from app import backup
from app.backup_consistency309 import upload_inventory


def prepare(tmp_path):
    data=tmp_path/'data'
    data.mkdir()

    with sqlite3.connect(data/'tracker.db') as db:
        db.execute(
            'CREATE TABLE example (id INTEGER PRIMARY KEY)'
        )

    upload=data/'uploads'/'coa'/'reference.pdf'
    upload.parent.mkdir(parents=True)
    upload.write_bytes(b'initial-file')

    return data,upload


def test_backup_rejects_upload_change_without_publishing(
    tmp_path,monkeypatch
):
    data,upload=prepare(tmp_path)
    original=zipfile.ZipFile.write
    changed={'done':False}

    def race(self,filename,arcname=None,*args,**kwargs):
        result=original(
            self,filename,arcname,*args,**kwargs
        )

        if not changed['done'] and str(arcname)=='tracker.db':
            upload.write_bytes(b'changed-during-backup')
            changed['done']=True

        return result

    monkeypatch.setattr(zipfile.ZipFile,'write',race)

    with pytest.raises(
        ValueError,
        match='Uploads changed during backup'
    ):
        backup.create_backup(
            data,tmp_path/'backups'
        )

    assert changed['done']
    assert list(
        (tmp_path/'backups').glob('tracker-*.zip')
    )==[]


def test_backup_preserves_stable_files_and_rejects_symlinks(
    tmp_path
):
    data,upload=prepare(tmp_path)
    archive=backup.create_backup(
        data,tmp_path/'backups'
    )

    manifest=backup.verify_backup(archive)

    assert (
        'uploads/coa/reference.pdf'
        in manifest['files']
    )

    target=tmp_path/'outside'
    target.write_bytes(b'secret')

    (upload.parent/'linked.pdf').symlink_to(target)

    with pytest.raises(ValueError,match='symlink'):
        upload_inventory(data/'uploads')
