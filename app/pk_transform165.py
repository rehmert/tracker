"""Preview and commit hypothetical schedule transformations."""
from datetime import timedelta
from fastapi import HTTPException
from pydantic import BaseModel,Field
from .pk_guarded_edit161 import lock_sqlite
from .pk_scenario_ops import scenario,rows
from . import pk_scenario_version as ver


class Transform(BaseModel):
    shift_hours:float=Field(ge=-8760,le=8760)
    amount_multiplier:float=Field(
        gt=0,le=10
    )
    expected_version:str=Field(
        min_length=64,max_length=64
    )


def projected(items,data):
    result=[]

    for item in items:
        value=item.amount_mg*data.amount_multiplier
        if not 0<value<=10000:
            raise HTTPException(
                400,'Transformed amount out of range'
            )

        result.append({
            'id':item.id,
            'planned_at':(
                item.planned_at+
                timedelta(hours=data.shift_hours)
            ).isoformat(),
            'amount_mg':value
        })

    times=[x['planned_at'] for x in result]
    if len(set(times))!=len(times):
        raise HTTPException(
            409,'Transformation produces duplicate dates'
        )

    return result


def apply(db,sid,data):
    lock_sqlite(db)
    obj=scenario(db,sid)
    ver.check(db,obj,data.expected_version)

    before=ver.snapshot(db,obj)
    current=rows(db,sid)
    proposed=projected(current,data)

    if not proposed:
        raise HTTPException(
            400,'Scenario has no doses to transform'
        )

    by_id={x.id:x for x in current}

    for item in proposed:
        target=by_id[item['id']]
        target.planned_at=target.planned_at+timedelta(
            hours=data.shift_hours
        )
        target.amount_mg=item['amount_mg']

    db.flush()
    db.expire(obj,['doses'])

    after=ver.snapshot(db,obj)
    ver.audit(
        db,sid,'schedule_transform',
        before,after
    )
    db.commit()

    return {
        'updated':len(proposed),
        'version':ver.version(after)
    }
