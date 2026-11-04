"""Read-only PK scenario consistency checks. Never mutate clinical records."""
from sqlalchemy import select
from .models import PkScenario,PkPlannedDose,Compound

def inspect(db):
    findings=[]
    scenarios=list(db.scalars(select(PkScenario)))
    for scenario in scenarios:
        if db.get(Compound,scenario.compound_id) is None:
            findings.append({'scenario_id':scenario.id,'issue':'missing_compound'})
        doses=list(db.scalars(select(PkPlannedDose).where(PkPlannedDose.scenario_id==scenario.id)))
        by_time={}
        for dose in doses:
            by_time.setdefault(dose.planned_at,[]).append(dose.id)
            if dose.amount_mg<=0:
                findings.append({'scenario_id':scenario.id,'dose_id':dose.id,'issue':'nonpositive_amount'})
        for at,ids in by_time.items():
            if len(ids)>1:
                findings.append({'scenario_id':scenario.id,'dose_ids':ids,'issue':'duplicate_timestamp','at':at.isoformat()})
    return {'scenarios_checked':len(scenarios),'findings':findings,
            'read_only':True,'note':'Hypothetical PK scenario checks only; no dosing or inventory changes'}
