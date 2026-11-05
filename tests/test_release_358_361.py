import hashlib
import json
import sqlite3
import zipfile
import pytest
from app.backup import verify_backup


def archive(tmp_path,with_upload):
    db=tmp_path/'tracker.db'
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE coas (stored_name TEXT, original_name TEXT)')
        conn.execute("INSERT INTO coas VALUES ('coa.pdf','original.pdf')")
    contents={'tracker.db':db.read_bytes()}
    if with_upload:
        contents['uploads/coa/coa.pdf']=b'%PDF-attachment'
    manifest={'version':1,'files':{
        name:dict(sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
        for name,data in contents.items()
    }}
    path=tmp_path/('complete.zip' if with_upload else 'incomplete.zip')
    with zipfile.ZipFile(path,'w') as z:
        for name,data in contents.items(): z.writestr(name,data)
        z.writestr('manifest.json',json.dumps(manifest))
    return path


def test_checksum_valid_archive_still_rejects_missing_reference(tmp_path):
    path=archive(tmp_path,False)
    with pytest.raises(ValueError,match='missing referenced attachment'):
        verify_backup(path)


def test_archive_with_referenced_file_passes(tmp_path):
    path=archive(tmp_path,True)
    assert 'uploads/coa/coa.pdf' in verify_backup(path)['files']
