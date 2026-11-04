from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base
from app.pk_operations237 import health


def test_integrity_check_is_read_only(tmp_path):
    engine=create_engine(f'sqlite:///{tmp_path / "ops.db"}')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        result=health(db)
        assert result['database_check']=='ok'
        assert result['read_only'] is True
        assert not db.dirty and not db.new and not db.deleted
    engine.dispose()
