import json
from datetime import datetime
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from app.db import Base
from app.models import Compound,PkScenario,PkPlannedDose,ChangeAudit
from app.pk_scenario_version import snapshot,version
from app.pk_revision229 import preview,restore


def test_revision_preview_restore_and_audit(tmp_path):
    engine=create_engine(f'sqlite:///{tmp_path / "test.db"}')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        c=Compound(name='Tirzepatide');db.add(c);db.flush()
        obj=PkScenario(compound_id=c.id,name='Original',half_life_hours=120,absorption_half_life_hours=12)
        db.add(obj);db.flush();sid=obj.id
        db.add(PkPlannedDose(scenario_id=sid,planned_at=datetime(2026,11,5),amount_mg=2))
        db.flush();stored=snapshot(db,obj)
        audit=ChangeAudit(entity_type='pk_scenario',entity_id=sid,action='scenario_create',before_json='{}',after_json=json.dumps(stored))
        db.add(audit);db.commit();aid=audit.id
    with Session(engine) as db:
        dose=db.scalar(select(PkPlannedDose).where(PkPlannedDose.scenario_id==sid));dose.amount_mg=3;db.commit()
    with Session(engine) as db:
        info=preview(db,sid,aid);assert info['dose_count']==1
        result=restore(db,sid,aid,info['current_version'])
        assert result['restored']==1
    with Session(engine) as db:
        item=db.scalar(select(PkPlannedDose).where(PkPlannedDose.scenario_id==sid))
        assert item.amount_mg==2
        assert db.scalar(select(ChangeAudit).where(ChangeAudit.action=='revision_restore')) is not None
    engine.dispose()
