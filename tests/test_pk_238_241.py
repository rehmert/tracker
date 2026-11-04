import json
from datetime import datetime
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Compound,PkScenario,PkPlannedDose,ChangeAudit
from app.pk_revision229 import (
    SnapshotPayload,preview,restore
)


def test_invalid_and_duplicate_snapshots():
    base={
        'compound_id':1,
        'name':'Example',
        'half_life_hours':120,
        'absorption_half_life_hours':12,
        'doses':[
            {'planned_at':'2026-11-05T08:00:00','amount_mg':2}
        ]
    }

    assert SnapshotPayload.model_validate(base).name=='Example'

    with pytest.raises(ValueError):
        SnapshotPayload.model_validate({
            **base,
            'doses':base['doses']*2
        })

    with pytest.raises(ValueError):
        SnapshotPayload.model_validate({
            **base,
            'half_life_hours':0
        })


def test_malformed_restore_leaves_scenario_unchanged(tmp_path):
    engine=create_engine(
        f'sqlite:///{tmp_path / "recovery.db"}'
    )
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
        db.add(PkPlannedDose(
            scenario_id=sid,
            planned_at=datetime(2026,11,5,8),
            amount_mg=2
        ))

        audit=ChangeAudit(
            entity_type='pk_scenario',
            entity_id=sid,
            action='malformed_test',
            before_json='{}',
            after_json=json.dumps({
                'compound_id':compound.id,
                'name':'Original',
                'half_life_hours':120,
                'absorption_half_life_hours':12,
                'doses':[
                    {'planned_at':'invalid-date','amount_mg':1}
                ]
            })
        )
        db.add(audit)
        db.commit()
        aid=audit.id

    with Session(engine) as db:
        with pytest.raises(HTTPException) as err:
            preview(db,sid,aid)
        assert err.value.status_code==409

    with Session(engine) as db:
        item=db.get(PkScenario,sid)
        assert item.name=='Original'
        assert len(item.doses)==1
        assert item.doses[0].amount_mg==2

    engine.dispose()
