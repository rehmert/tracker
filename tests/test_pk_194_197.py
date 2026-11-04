"""Behavioral SQLite rollback and stale revision tests."""
from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine,event,select,func
from sqlalchemy.orm import Session

from app.db import Base
from app.models import (
    Compound,PkScenario,PkPlannedDose,ChangeAudit
)
from app.pk_mutation197 import prepare,finish
from app.pk_scenario_version import snapshot,version


def test_guarded_mutation_rollback_and_revision(tmp_path):
    engine=create_engine(
        f'sqlite:///{tmp_path / "pk.db"}',
        connect_args={'timeout':1}
    )

    @event.listens_for(engine,'connect')
    def fk(connection,_):
        connection.execute('PRAGMA foreign_keys=ON')

    Base.metadata.create_all(engine)

    with Session(engine) as db:
        compound=Compound(name='Tirzepatide')
        db.add(compound)
        db.flush()

        obj=PkScenario(
            compound_id=compound.id,
            name='Original',
            half_life_hours=120,
            absorption_half_life_hours=12
        )

        db.add(obj)
        db.flush()
        sid=obj.id
        db.commit()

    with Session(engine) as db:
        obj=db.get(PkScenario,sid)
        revision=version(snapshot(db,obj))

    with Session(engine) as db:
        obj,before=prepare(db,sid,revision)

        db.add(PkPlannedDose(
            scenario_id=sid,
            planned_at=datetime(2026,11,5),
            amount_mg=1
        ))

        # Simulate a failure before the commit.
        db.rollback()

    with Session(engine) as db:
        assert db.scalar(
            select(func.count()).select_from(PkPlannedDose)
        )==0

    with Session(engine) as db:
        obj,before=prepare(db,sid,revision)

        db.add(PkPlannedDose(
            scenario_id=sid,
            planned_at=datetime(2026,11,5),
            amount_mg=1
        ))

        new_version=finish(
            db,obj,'test_insert',before
        )

        assert new_version!=revision

    with Session(engine) as db:
        with pytest.raises(HTTPException) as error:
            prepare(db,sid,revision)

        assert error.value.status_code==409
        db.rollback()

    with Session(engine) as db:
        assert db.scalar(
            select(func.count()).select_from(PkPlannedDose)
        )==1

        assert db.scalar(
            select(func.count())
            .select_from(ChangeAudit)
            .where(ChangeAudit.action=='test_insert')
        )==1

    engine.dispose()
