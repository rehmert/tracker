import asyncio
from io import BytesIO
from types import SimpleNamespace
from fastapi import UploadFile
import pytest
from app.routers import coas


def test_upload_cleanup_after_failure_before_commit(monkeypatch,tmp_path):
    path=tmp_path/'new.pdf'
    calls=[]

    async def save_file(_file):
        path.write_bytes(b'%PDF-test')
        return dict(original_name='new.pdf',stored_name='new.pdf',
                    content_type='application/pdf',size_bytes=9,sha256='x')

    def delete_file(name,directory):
        calls.append(('delete',name))
        (directory/name).unlink(missing_ok=True)

    def fail_inspection(_connection):
        raise RuntimeError('injected pre-commit failure')

    class DB:
        def get(self,model,id): return SimpleNamespace(content_unit='mg')
        def connection(self): return object()
        def rollback(self): calls.append(('rollback',None))

    monkeypatch.setattr(coas.services,'save_upload',save_file)
    monkeypatch.setattr(coas.services,'delete_stored_file',delete_file)
    monkeypatch.setattr(coas.config,'UPLOAD_DIR',tmp_path)
    monkeypatch.setattr(coas,'inspect',fail_inspection)

    with pytest.raises(RuntimeError,match='pre-commit'):
        asyncio.run(coas.upload_coa(
            vid=1,file=UploadFile(filename='new.pdf',file=BytesIO(b'%PDF-test')),
            lab_name='',tested_on='',purity_pct='',reported_content='',
            reported_unit='mg',notes='',endotoxin_pct='',job_id='',
            verify_code='',db=DB()
        ))
    assert calls==[('rollback',None),('delete','new.pdf')]
    assert not path.exists()
