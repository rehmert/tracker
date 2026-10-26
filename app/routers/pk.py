from datetime import datetime, timedelta
import csv
import io
from fastapi.responses import Response
from math import isfinite
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Compound, DoseLog, Vial, PkScenario, PkPlannedDose
from ..templating import render
from .. import pk

router = APIRouter(prefix="/pk")

class ScenarioInput(BaseModel):
    compound_id: int
    name: str = Field(min_length=1, max_length=160)
    half_life_hours: float = Field(gt=0, le=10000)
    absorption_half_life_hours: float = Field(gt=0, le=10000)

class PlannedInput(BaseModel):
    planned_at: datetime
    amount_mg: float = Field(gt=0, le=10000)


def supported(db):
    return [c for c in db.scalars(select(Compound).order_by(Compound.name)) if pk.profile(c.name)]

@router.get("")
def page(request: Request, db: Session = Depends(get_db)):
    return render(request, "pk.html", compounds=supported(db), profile=pk.profile)

@router.post("/compounds", status_code=201)
def add_supported_compound(data: dict, db: Session = Depends(get_db)):
    """Explicitly add a PK-capable compound even before any dose/vial exists."""
    name = str(data.get("name", "")).strip()
    allowed = {"Testosterone Cypionate", "Testosterone Enanthate", "Testosterone"}
    if name not in allowed:
        raise HTTPException(400, "Unsupported starter compound")
    existing = db.scalar(select(Compound).where(Compound.name == name))
    if existing:
        return {"id": existing.id, "name": existing.name}
    c = Compound(name=name, category="testosterone")
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id, "name": c.name}

@router.get("/scenarios")
def scenarios(compound_id: int, db: Session = Depends(get_db)):
    return [{"id": s.id, "name": s.name, "half_life_hours": s.half_life_hours,
             "absorption_half_life_hours": s.absorption_half_life_hours,
             "doses": [{"id": d.id, "planned_at": d.planned_at.isoformat(), "amount_mg": d.amount_mg}
                       for d in sorted(s.doses, key=lambda x: x.planned_at)]}
            for s in db.scalars(select(PkScenario).where(PkScenario.compound_id == compound_id).order_by(PkScenario.id))]

@router.post("/scenarios", status_code=201)
def create_scenario(data: ScenarioInput, db: Session = Depends(get_db)):
    c = db.get(Compound, data.compound_id)
    if c is None or pk.profile(c.name) is None:
        raise HTTPException(400, "Unsupported compound")
    s = PkScenario(**data.model_dump())
    db.add(s); db.commit()
    return {"id": s.id}

@router.put("/scenarios/{sid}")
def update_scenario(sid: int, data: ScenarioInput, db: Session = Depends(get_db)):
    s = db.get(PkScenario, sid)
    if s is None: raise HTTPException(404)
    if s.compound_id != data.compound_id: raise HTTPException(400, "Cannot change scenario compound")
    if not all(isfinite(v) for v in (data.half_life_hours, data.absorption_half_life_hours)):
        raise HTTPException(400, "Invalid half-life")
    s.name = data.name
    s.half_life_hours = data.half_life_hours
    s.absorption_half_life_hours = data.absorption_half_life_hours
    db.commit(); return {"ok": True}

@router.delete("/scenarios/{sid}")
def delete_scenario(sid: int, db: Session = Depends(get_db)):
    s = db.get(PkScenario, sid)
    if s is None: raise HTTPException(404)
    db.delete(s); db.commit(); return {"ok": True}

@router.post("/scenarios/{sid}/doses", status_code=201)
def add_dose(sid: int, data: PlannedInput, db: Session = Depends(get_db)):
    if db.get(PkScenario, sid) is None: raise HTTPException(404)
    d = PkPlannedDose(scenario_id=sid, **data.model_dump())
    db.add(d); db.commit(); return {"id": d.id}

@router.put("/scenarios/{sid}/doses/{did}")
def edit_dose(sid: int, did: int, data: PlannedInput, db: Session = Depends(get_db)):
    d = db.get(PkPlannedDose, did)
    if d is None or d.scenario_id != sid: raise HTTPException(404)
    d.planned_at, d.amount_mg = data.planned_at, data.amount_mg
    db.commit(); return {"ok": True}

@router.delete("/scenarios/{sid}/doses/{did}")
def delete_dose(sid: int, did: int, db: Session = Depends(get_db)):
    d = db.get(PkPlannedDose, did)
    if d is None or d.scenario_id != sid: raise HTTPException(404)
    db.delete(d); db.commit(); return {"ok": True}

@router.get("/data")
def chart_data(compound_id: int, days_back: int = 60, days_forward: int = 45,
               half_life_hours: float | None = None, absorption_half_life_hours: float | None = None,
               scenario_id: int | None = None, db: Session = Depends(get_db)):
    c = db.get(Compound, compound_id)
    defaults = pk.profile(c.name) if c else None
    if defaults is None: raise HTTPException(400, "Unsupported compound")
    hl = half_life_hours if half_life_hours is not None else defaults[0]
    ahl = absorption_half_life_hours if absorption_half_life_hours is not None else defaults[1]
    if not all(isfinite(x) and 0 < x <= 10000 for x in (hl, ahl)):
        raise HTTPException(400, "Invalid half-life")
    if not (1 <= days_back <= 365 and 1 <= days_forward <= 365):
        raise HTTPException(400, "Date range out of bounds")
    now = datetime.now()
    start, end = now-timedelta(days=days_back), now+timedelta(days=days_forward)
    # Load sufficient lookback for accumulation; don't count waste as administration.
    history_start = start - timedelta(hours=min(hl*12, 365*24))
    q = (select(DoseLog).join(Vial).where(Vial.compound_id == compound_id,
         DoseLog.kind == "dose", DoseLog.taken_at >= history_start, DoseLog.taken_at <= now))
    actual = []
    for d in db.scalars(q):
        # DoseLog.amount_base is mcg for mass, IU for activity; only mass supported here.
        if d.vial.content_unit in ("mg", "mcg", "g"):
            actual.append((d.taken_at, d.amount_base / 1000))
    planned = []
    if scenario_id is not None:
        s = db.get(PkScenario, scenario_id)
        if s is None or s.compound_id != compound_id: raise HTTPException(400, "Invalid scenario")
        planned = [(d.planned_at, d.amount_mg) for d in s.doses if d.planned_at >= now]
    rows = pk.series(start, end, actual, planned, hl, ahl)
    return {"rows": rows, "now": now.isoformat(), "actual_doses": len(actual),
            "planned_doses": len(planned), "units": "modeled mg-equivalent exposure",
            "disclaimer": "Exploratory model, not measured blood concentration or clinical effectiveness."}


@router.get('/compare')
def compare_scenarios(compound_id: int, scenario_ids: str = '', days_back: int = 30,
                      days_forward: int = 60, db: Session = Depends(get_db)):
    """Return a common timeline for baseline and up to four hypothetical scenarios."""
    c = db.get(Compound, compound_id)
    defaults = pk.profile(c.name) if c else None
    if defaults is None: raise HTTPException(400, 'Unsupported compound')
    if not (1 <= days_back <= 365 and 1 <= days_forward <= 365):
        raise HTTPException(400, 'Invalid range')
    try:
        ids = list(dict.fromkeys(int(v) for v in scenario_ids.split(',') if v.strip()))
    except ValueError:
        raise HTTPException(400, 'Invalid scenario IDs')
    if len(ids) > 4: raise HTTPException(400, 'Compare at most four scenarios')
    now = datetime.now()
    start, end = now-timedelta(days=days_back), now+timedelta(days=days_forward)
    # Fetch enough history for slow-clearing compounds; same baseline for all scenarios.
    history_start = start-timedelta(days=365)
    q = select(DoseLog).join(Vial).where(Vial.compound_id == compound_id,
        DoseLog.kind == 'dose', DoseLog.taken_at >= history_start, DoseLog.taken_at <= now)
    actual = [(d.taken_at, d.amount_base/1000) for d in db.scalars(q)
              if d.vial.content_unit in ('mg','mcg','g')]
    base = pk.series(start, end, actual, [], *defaults)
    results = [{'name':'Recorded + decay only', 'id':None,
                'values':[r['actual'] for r in base]}]
    for sid in ids:
        scenario = db.get(PkScenario, sid)
        if scenario is None or scenario.compound_id != compound_id:
            raise HTTPException(400, 'Scenario does not belong to compound')
        planned = [(d.planned_at, d.amount_mg) for d in scenario.doses if d.planned_at >= now]
        series = pk.series(start, end, actual, planned, scenario.half_life_hours,
                           scenario.absorption_half_life_hours)
        results.append({'name':scenario.name, 'id':sid, 'values':[r['planned'] for r in series]})
    return {'at':[r['at'] for r in base], 'series':results,
            'units':'modeled mg-equivalent exposure',
            'disclaimer':'Hypothetical modeled exposure, not measured blood levels or a dosing recommendation.'}


@router.get('/compare.csv')
def export_scenario_comparison_csv(compound_id: int, scenario_ids: str = '',
                                   days_back: int = 30, days_forward: int = 60,
                                   db: Session = Depends(get_db)):
    """Export the exact PK comparison timeline as a spreadsheet-friendly CSV.

    Uses the same validation and model as /pk/compare; does not persist data.
    """
    comparison = compare_scenarios(compound_id, scenario_ids, days_back, days_forward, db)
    output = io.StringIO(newline='')
    writer = csv.writer(output)

    def safe_cell(value: str) -> str:
        # Prevent spreadsheet formula evaluation from user-controlled scenario names.
        return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else value

    writer.writerow(['Timestamp'] + [safe_cell(s['name']) for s in comparison['series']])
    for i, at in enumerate(comparison['at']):
        writer.writerow([at] + [s['values'][i] for s in comparison['series']])
    return Response(content=output.getvalue(), media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': 'attachment; filename="tracker-pk-comparison.csv"',
                             'Cache-Control': 'no-store'})
