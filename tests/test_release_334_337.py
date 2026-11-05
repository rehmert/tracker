from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import LabReport
from app.attachment_integrity337 import (
    uploaded_transaction,
    delete_after_commit,
)
from app.routers import labs as labs_router


def test_failed_commit_rolls_back_and_cleans_new_file(tmp_path):
    engine=create_engine(f'sqlite:///{tmp_path / "test.db"}')
    Base.metadata.create_all(engine)

    path=tmp_path/'new.pdf'
    path.write_bytes(b'%PDF-synthetic')
    deleted=[]

    class FailingSession(Session):
        def commit(self):
            raise RuntimeError('synthetic commit failure')

    def cleanup(name,root):
        deleted.append(name)
        (root/name).unlink(missing_ok=True)

    with FailingSession(engine) as db:
        with pytest.raises(RuntimeError,match='synthetic'):
            with uploaded_transaction(
                db,
                {'original_name':'new.pdf','stored_name':'new.pdf'},
                tmp_path,
                cleanup
            ):
                db.add(LabReport(drawn_on=date(2026,11,4)))
                db.commit()

    assert deleted==['new.pdf']
    assert not path.exists()

    with Session(engine) as db:
        assert list(db.scalars(select(LabReport)))==[]

    engine.dispose()


def test_failed_lab_delete_preserves_attachment(monkeypatch,tmp_path):
    path=tmp_path/'existing.pdf'
    path.write_bytes(b'original')

    monkeypatch.setattr(
        labs_router,
        '_report',
        lambda db,rid:SimpleNamespace(stored_name='existing.pdf')
    )
    monkeypatch.setattr(labs_router.config,'LAB_DIR',tmp_path)

    deleted=[]
    monkeypatch.setattr(
        labs_router.services,
        'delete_stored_file',
        lambda name,root:deleted.append(name)
    )

    class FailingDB:
        def delete(self,record):
            pass
        def commit(self):
            raise RuntimeError('synthetic failure')

    with pytest.raises(RuntimeError,match='synthetic'):
        labs_router.delete_report(1,db=FailingDB())

    assert path.read_bytes()==b'original'
    assert deleted==[]


def test_post_commit_cleanup_failure_is_logged(caplog,tmp_path):
    def fail(name,root):
        raise OSError('synthetic filesystem failure')

    delete_after_commit('old.pdf',tmp_path,fail)
    assert 'Committed attachment cleanup failed' in caplog.text
