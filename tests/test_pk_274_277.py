from datetime import datetime,timedelta
import json
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from app.db import Base
from app.models import (
    Compound,PkScenario,PkPlannedDose,ChangeAudit
)
from app.pk_revision_delta257 import Snapshot
from app.pk_scenario_version import snapshot
from app.pk_revision229 import restore,preview


def test_unknown_snapshot_fields_rejected():
    with pytest.raises(ValidationError):
        Snapshot.model_validate({
            'compound_id':1,
            'name':'Test',
            'half_life_hours':120,
            'absorption_half_life_hours':12,
            'doses':[],
            'unexpected_field':42
        })


def test_recovery_retains_matching_ids(tmp_path):
    engine=create_engine(
        f'sqlite:///{tmp_path / "test.db"}'
    )
    Base.metadata.create_all(engine)

    at=datetime(2026,11,4)

    with Session(engine) as db:
        c=Compound(name='Tirzepatide')
        db.add(c)
        db.flush()
        obj=PkScenario(
            compound_id=c.id,name='Test',
            half_life_hours=120,
            absorption_half_life_hours=12
        )
        db.add(obj)
        db.flush()
        sid=obj.id

        db.add_all([
            PkPlannedDose(
                scenario_id=sid,
                planned_at=at,
                amount_mg=2
            ),
            PkPlannedDose(
                scenario_id=sid,
                planned_at=at+timedelta(days=3),
                amount_mg=2
            )
        ])

        db.flush()
        original=snapshot(db,obj)

        audit=ChangeAudit(
            entity_type='pk_scenario',
            entity_id=sid,
            action='test_snapshot',
            before_json='{}',
            after_json=json.dumps(original)
        )
        db.add(audit)
        db.commit()
        aid=audit.id

    with Session(engine) as db:
        items=list(db.scalars(
            select(PkPlannedDose)
            .where(PkPlannedDose.scenario_id==sid)
            .order_by(PkPlannedDose.planned_at)
        ))
        original_id=items[0].id
        items[1].amount_mg=4
        db.commit()

    with Session(engine) as db:
        state=preview(db,sid,aid)
        result=restore(
            db,sid,aid,state['current_version']
        )
        assert result['modified']==1
        assert result['removed']==0

    with Session(engine) as db:
        items=list(db.scalars(
            select(PkPlannedDose)
            .where(PkPlannedDose.scenario_id==sid)
            .order_by(PkPlannedDose.planned_at)
        ))
        assert items[0].id==original_id
        assert [x.amount_mg for x in items]==[2,2]

    engine.dispose()
