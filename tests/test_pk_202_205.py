from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Compound,Vial,DoseLog
from app.pk_crosscheck205 import inspect


def test_cross_module_check_is_read_only(tmp_path):
    engine=create_engine(
        f'sqlite:///{tmp_path / "check.db"}'
    )

    Base.metadata.create_all(engine)

    with Session(engine) as db:
        c=Compound(name='Example')
        db.add(c)
        db.flush()

        v=Vial(
            compound_id=c.id,
            content_value=10,
            content_unit='mg'
        )

        db.add(v)
        db.flush()

        db.add(DoseLog(
            vial_id=v.id,
            taken_at=datetime(2026,11,4),
            entered_value=0,
            entered_unit='mg',
            amount_base=0,
            kind='dose'
        ))

        db.commit()

    with Session(engine) as db:
        result=inspect(db)

        assert result['read_only'] is True
        assert result['logs_checked']==1
        assert any(
            x['type']=='invalid_logged_amount'
            for x in result['findings']
        )

        assert not db.dirty
        assert not db.new
        assert not db.deleted

    engine.dispose()
