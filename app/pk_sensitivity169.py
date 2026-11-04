"""Sensitivity analysis for hypothetical PK parameters."""
from datetime import datetime,timedelta
from fastapi import HTTPException
from . import pk
from .pk_scenario_ops import scenario


def analyze(db,sid,days):
    if not 1<=days<=90:
        raise HTTPException(
            400,'Days must be between 1 and 90'
        )

    obj=scenario(db,sid)
    start=datetime.now()
    end=start+timedelta(days=days)

    planned=[
        (d.planned_at,d.amount_mg)
        for d in obj.doses
        if d.planned_at>=start
    ]

    if not planned:
        raise HTTPException(
            400,
            'No upcoming doses in this scenario'
        )

    variants=[]

    for factor in (.75,1.0,1.25):
        rows=pk.series(
            start,end,[],planned,
            obj.half_life_hours*factor,
            obj.absorption_half_life_hours,
            step_hours=12
        )

        values=[r['planned'] for r in rows]

        variants.append({
            'factor':factor,
            'half_life_hours':
                obj.half_life_hours*factor,
            'points':values,
            'peak':max(values),
            'trough':min(values),
            'mean':sum(values)/len(values)
        })

    return {
        'scenario_id':sid,
        'times':[r['at'] for r in rows],
        'variants':variants,
        'disclaimer':(
            'Illustrative parameter sensitivity; '
            'not measured blood concentration, clinical '
            'effect, or a recommended dose.'
        )
    }
