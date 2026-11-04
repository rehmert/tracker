from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Compound,Vial,DoseLog
from app.pk_diagnostics213 import inspect


def test_sql_diagnostics_bounded_and_read_only(tmp_path):
    engine=create_engine(
        f'sqlite:///{tmp_path / "diag.db"}'
    )

    Base.metadata.create_all(engine)

    with Session(engine) as db:
        compound=Compound(
            name='Test compound'
        )
        db.add(compound)
        db.flush()

        vial=Vial(
            compound_id=compound.id,
            content_value=10,
            content_unit='mg'
        )
        db.add(vial)
        db.flush()

        for i in range(3):
            db.add(DoseLog(
                vial_id=vial.id,
                taken_at=datetime(2026,11,4),
                entered_value=0,
                entered_unit='mg',
                amount_base=0,
                kind='dose'
            ))

        db.commit()

    with Session(engine) as db:
        report=inspect(db,limit=2)

        assert report['read_only'] is True
        assert report['logs_checked']==3
        assert len(report['findings'])==2
        assert report['truncated'] is True

        assert {
            x['type']
            for x in report['findings']
        }=={'invalid_logged_amount'}

        assert not db.dirty
        assert not db.new
        assert not db.deleted

    engine.dispose()
