"""Preview or restore complete audited hypothetical PK scenario snapshots."""
import json
from datetime import datetime
from math import isfinite
from fastapi import HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import select,delete
from .models import ChangeAudit,PkPlannedDose
from .pk_scenario_ops import scenario
from .pk_mutation197 import prepare,finish
from .pk_scenario_version import snapshot,version


class RestoreRequest(BaseModel):
    expected_version:str=Field(min_length=64,max_length=64)


def parse_audit(db,sid,aid):
    audit=db.get(ChangeAudit,aid)
    if not audit or audit.entity_type!='pk_scenario' or audit.entity_id!=sid:
        raise HTTPException(404,'Scenario revision unavailable')
    try:
        value=json.loads(audit.after_json)
        assert isinstance(value,dict)
        assert isinstance(value.get('name'),str) and 1<=len(value['name'])<=160
        assert isinstance(value.get('doses'),list) and len(value['doses'])<=300
        assert int(value['compound_id'])==scenario(db,sid).compound_id
        h=float(value['half_life_hours']);a=float(value['absorption_half_life_hours'])
        assert all(isfinite(x) and 0<x<=10000 for x in (h,a))
        doses=[]
        for item in value['doses']:
            at=datetime.fromisoformat(item['planned_at'])
            amount=float(item['amount_mg'])
            assert isfinite(amount) and 0<amount<=10000
            doses.append((at,amount))
        assert len(set(at for at,_ in doses))==len(doses)
    except (ValueError,TypeError,KeyError,AssertionError,OverflowError):
        raise HTTPException(409,'Audit entry is not a complete restorable snapshot')
    return audit,value,doses


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
    return {'audit_id':aid,'action':audit.action,'restorable':True,
            'current_version':version(snapshot(db,current)),
            'name':value['name'],'dose_count':len(doses),
            'note':'Existing hypothetical dose IDs will be replaced upon restoration.'}


def restore(db,sid,aid,expected):
    obj,before=prepare(db,sid,expected)
    _,value,doses=parse_audit(db,sid,aid)
    db.execute(delete(PkPlannedDose).where(PkPlannedDose.scenario_id==sid))
    db.expire(obj,['doses'])
    obj.name=value['name']
    obj.half_life_hours=float(value['half_life_hours'])
    obj.absorption_half_life_hours=float(value['absorption_half_life_hours'])
    for at,amount in doses:
        db.add(PkPlannedDose(scenario_id=sid,planned_at=at,amount_mg=amount))
    new_version=finish(db,obj,'revision_restore',before)
    return {'restored':len(doses),'version':new_version,'audit_source':aid}
