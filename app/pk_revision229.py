"""Preview or restore complete audited hypothetical PK scenario snapshots."""
import json
from datetime import datetime
from math import isfinite
from fastapi import HTTPException
from pydantic import BaseModel,Field,ValidationError,model_validator
from sqlalchemy import select,delete
from .models import ChangeAudit,PkPlannedDose
from .pk_scenario_ops import scenario
from .pk_mutation197 import prepare,finish
from .pk_scenario_version import snapshot,version
from .pk_revision_delta257 import Snapshot,changes,equivalent


class RestoreRequest(BaseModel):
    expected_version:str=Field(min_length=64,max_length=64)


class SnapshotDose(BaseModel):
    id:int|None=None
    planned_at:datetime
    amount_mg:float=Field(gt=0,le=10000)


class SnapshotPayload(BaseModel):
    compound_id:int=Field(gt=0)
    name:str=Field(min_length=1,max_length=160)
    half_life_hours:float=Field(gt=0,le=10000)
    absorption_half_life_hours:float=Field(gt=0,le=10000)
    doses:list[SnapshotDose]=Field(max_length=300)

    @model_validator(mode='after')
    def unique_dates(self):
        dates=[d.planned_at for d in self.doses]
        if len(dates)!=len(set(dates)):
            raise ValueError('Duplicate planned timestamps')
        return self


def parse_audit(db,sid,aid):
    audit=db.get(ChangeAudit,aid)
    if (
        audit is None
        or audit.entity_type!='pk_scenario'
        or audit.entity_id!=sid
    ):
        raise HTTPException(404,'Scenario revision unavailable')

    try:
        payload=Snapshot.model_validate_json(
            audit.after_json
        )
        if payload.compound_id!=scenario(db,sid).compound_id:
            raise ValueError('Wrong compound')
    except (ValidationError,ValueError,TypeError):
        raise HTTPException(
            409,'Audit entry is not a complete restorable snapshot'
        )

    data=payload.model_dump(mode='json')
    doses=[
        (d.planned_at,d.amount_mg)
        for d in payload.doses
    ]
    return audit,data,doses


def history(db,sid,limit=30):
    scenario(db,sid)
    out=[]
    for item in db.scalars(select(ChangeAudit).where(
        ChangeAudit.entity_type=='pk_scenario',ChangeAudit.entity_id==sid
    ).order_by(ChangeAudit.id.desc()).limit(limit)):
        try:
            parse_audit(db,sid,item.id)
            eligible=True
        except HTTPException:
            eligible=False
        out.append({'id':item.id,'action':item.action,
                    'at':item.created_at.isoformat() if item.created_at else None,
                    'restorable':eligible})
    return out


def preview(db,sid,aid):
    audit,value,doses=parse_audit(db,sid,aid)
    current=scenario(db,sid)
    old=snapshot(db,current)
    diff=changes(old,value)

    return {
        'audit_id':aid,
        'action':audit.action,
        'restorable':True,
        'current_version':version(old),
        'name':value['name'],
        'dose_count':len(doses),
        **diff,
        'note':'Historical restoration replaces hypothetical dose IDs.'
    }


def restore(db,sid,aid,expected):
    obj,before=prepare(db,sid,expected)
    _,value,doses=parse_audit(db,sid,aid)

    if equivalent(before,value):
        db.rollback()
        return {
            'restored':0,
            'version':version(before),
            'audit_source':aid,
            'unchanged':True
        }

    db.execute(delete(PkPlannedDose).where(PkPlannedDose.scenario_id==sid))
    db.expire(obj,['doses'])
    obj.name=value['name']
    obj.half_life_hours=float(value['half_life_hours'])
    obj.absorption_half_life_hours=float(value['absorption_half_life_hours'])
    for at,amount in doses:
        db.add(PkPlannedDose(scenario_id=sid,planned_at=at,amount_mg=amount))
    new_version=finish(db,obj,'revision_restore',before)
    return {'restored':len(doses),'version':new_version,'audit_source':aid}
