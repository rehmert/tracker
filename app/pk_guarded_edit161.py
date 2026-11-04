"""Serialized, revision-checked hypothetical PK dose editing."""
from datetime import datetime
from fastapi import HTTPException
from pydantic import BaseModel,Field
from .models import PkPlannedDose
from . import pk_scenario_version as ver
from .pk_scenario_ops import scenario


class CheckedEdit(BaseModel):
    dose_id:int=Field(gt=0)
    planned_at:datetime
    amount_mg:float=Field(gt=0,le=10000)
    expected_version:str=Field(
        min_length=64,max_length=64
    )


from .pk_write177 import begin as lock_sqlite


def update(db,sid,data):
    lock_sqlite(db)

    obj=scenario(db,sid)
    ver.check(db,obj,data.expected_version)

    dose=db.get(PkPlannedDose,data.dose_id)
    if dose is None or dose.scenario_id!=sid:
        raise HTTPException(
            404,'Planned dose not found'
        )

    before=ver.snapshot(db,obj)

    dose.planned_at=data.planned_at
    dose.amount_mg=data.amount_mg

    db.flush()
    db.expire(obj,['doses'])

    after=ver.snapshot(db,obj)
    ver.audit(
        db,sid,'guarded_dose_update',
        before,after
    )
    db.commit()

    return {
        'ok':True,
        'version':ver.version(after)
    }
