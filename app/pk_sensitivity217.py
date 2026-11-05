"""Bounded two-parameter sensitivity using a common grid."""
from datetime import datetime,timedelta

from fastapi import HTTPException
from sqlalchemy import select

from .models import DoseLog,Vial
from .pk_scenario_ops import scenario
from .pk_alignment193 import shared_step,validate_alignment
from .pk_metrics181 import metrics
from .pk_precision225 import bounded_step,refined_peak
from . import pk
from .pk_fast261 import series_fast

FACTORS=(.75,1.,1.25)


def analyze(db,sid,days=30):
    if not 1<=days<=90:
        raise HTTPException(
            400,'Days outside 1–90 range'
        )

    obj=scenario(db,sid)
    start=datetime.now()
    end=start+timedelta(days=days)

    planned=[
        (x.planned_at,x.amount_mg)
        for x in obj.doses
        if x.planned_at>=start
    ]

    if not planned:
        raise HTTPException(
            400,
            'Scenario has no upcoming hypothetical doses'
        )

    history_start=start-timedelta(days=365)

    recorded=[
        (x.taken_at,x.amount_base/1000)
        for x in db.scalars(
            select(DoseLog).join(Vial).where(
                Vial.compound_id==obj.compound_id,
                DoseLog.kind=='dose',
                DoseLog.taken_at>=history_start,
                DoseLog.taken_at<=start
            )
        )
        if x.vial.content_unit in ('mg','mcg','g')
    ]

    step=min(
        shared_step(obj.half_life_hours),
        shared_step(obj.absorption_half_life_hours)
    )

    # Include both recorded and hypothetical doses in the work budget.
    step=bounded_step(days*24,step,len(recorded)+len(planned))

    variants=[]
    curves=[]

    for elim_factor in FACTORS:
        for absorption_factor in FACTORS:
            rows=series_fast(
                start,end,recorded,planned,
                obj.half_life_hours*elim_factor,
                obj.absorption_half_life_hours*absorption_factor,
                step_hours=step
            )

            curves.append(rows)
            summary=metrics(rows)

            variants.append({
                'elimination_factor':elim_factor,
                'absorption_factor':absorption_factor,
                'points':[
                    x['planned'] for x in rows
                ],
                'auc':summary['auc'],
                'mean':summary['mean'],
                'sampled_peak':summary['peak'],
                'refined_peak':refined_peak(
                    rows,recorded+planned,
                    obj.half_life_hours*elim_factor,
                    obj.absorption_half_life_hours*absorption_factor
                )
            })

    times=validate_alignment(curves)

    lower=[
        min(v['points'][i] for v in variants)
        for i in range(len(times))
    ]

    upper=[
        max(v['points'][i] for v in variants)
        for i in range(len(times))
    ]

    return {
        'times':times,
        'variants':variants,
        'lower':lower,
        'upper':upper,
        'sample_interval_hours':step,
        'scenario_id':sid,
        'recorded_administrations':len(recorded),
        'units':'modeled mg-equivalent exposure',
        'disclaimer':(
            'Assumption-sensitivity envelope, not a '
            'statistical confidence interval or dosing advice.'
        )
    }
