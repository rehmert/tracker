"""Scenario revision checks and audit records."""
import hashlib
import json
from fastapi import HTTPException
from .models import ChangeAudit
from .pk_scenario_ops import rows


def snapshot(db, scenario):
    return {
        'compound_id':scenario.compound_id,
        'name':scenario.name,
        'half_life_hours':scenario.half_life_hours,
        'absorption_half_life_hours':
            scenario.absorption_half_life_hours,
        'doses':[
            {
                'id':item.id,
                'planned_at':item.planned_at.isoformat(),
                'amount_mg':item.amount_mg
            }
            for item in rows(db,scenario.id)
        ]
    }


def version(data):
    payload=json.dumps(
        data,sort_keys=True,separators=(',',':')
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def check(db, scenario, expected):
    if expected is not None and expected!=version(
        snapshot(db,scenario)
    ):
        raise HTTPException(
            409,'Scenario changed; reload before editing'
        )


def audit(db, sid, action, before, after):
    db.add(ChangeAudit(
        entity_type='pk_scenario',
        entity_id=sid,
        action=action,
        before_json=json.dumps(before,sort_keys=True),
        after_json=json.dumps(after,sort_keys=True)
    ))
