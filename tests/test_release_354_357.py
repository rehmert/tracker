import asyncio
from io import BytesIO
from types import SimpleNamespace
from fastapi import UploadFile
import pytest
from app.routers import coas


def exercise_edit(monkeypatch,tmp_path,fail):
    old=tmp_path/'old.pdf';new=tmp_path/'new.pdf'
    old.write_bytes(b'old original')
    deleted=[]
    coa=SimpleNamespace(original_name='old.pdf',stored_name='old.pdf',
                        all_vials=[],notes='',lab_name='')
    class DB:
        def get(self,model,id): return coa
        def commit(self):
            if fail: raise RuntimeError('injected commit failure')
        def rollback(self): deleted.append('rollback')
    async def save(_file, directory):
        # Explicit directory routing must remain active
        # for both successful and failed replacements.
        assert directory == tmp_path
        (directory / 'new.pdf').write_bytes(b'new attachment')
        return dict(original_name='new.pdf',stored_name='new.pdf',
                    content_type='application/pdf',size_bytes=14,sha256='new')
    def delete(name,directory):
        deleted.append(name)
        (directory/name).unlink(missing_ok=True)
    monkeypatch.setattr(coas.services,'save_upload',save)
    monkeypatch.setattr(coas.services,'delete_stored_file',delete)
    monkeypatch.setattr(coas.config,'UPLOAD_DIR',tmp_path)
    monkeypatch.setattr(coas,'_revision',lambda db,coa,event:None)
    args=dict(cid=12,file=UploadFile(filename='new.pdf',file=BytesIO(b'abc')),
              lab_name='',tested_on='',purity_pct='',endotoxin_pct='',
              reported_content='',reported_unit='mg',job_id='',
              verify_code='',notes='',db=DB())
    if fail:
        with pytest.raises(RuntimeError,match='injected commit failure'):
            asyncio.run(coas.coa_edit(**args))
        assert old.read_bytes()==b'old original'
        assert not new.exists()
        assert deleted==['rollback','new.pdf']
    else:
        response=asyncio.run(coas.coa_edit(**args))
        assert response.status_code==303
        assert not old.exists()
        assert new.exists()
        assert deleted==['old.pdf']


def test_replace_commit_failure_keeps_original(monkeypatch,tmp_path):
    exercise_edit(monkeypatch,tmp_path,True)


def test_replace_success_deletes_only_old_file(monkeypatch,tmp_path):
    exercise_edit(monkeypatch,tmp_path,False)
