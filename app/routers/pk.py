from datetime import datetime, timedelta
import csv
import io
from fastapi.responses import Response
from math import isfinite
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Compound, DoseLog, Vial, PkScenario, PkPlannedDose, Protocol
from ..calendar import staged_occurrences
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



class WhatIfStage(BaseModel):
    week: int = Field(ge=1, le=52)
    amount_mg: float = Field(gt=0, le=10000)

class WhatIfProtocol(BaseModel):
    compound_id: int
    name: str = Field(min_length=1, max_length=160)
    start_at: datetime
    interval_days: float = Field(ge=0.125, le=90)
    duration_days: int = Field(ge=1, le=365)
    stages: list[WhatIfStage] = Field(min_length=1, max_length=52)
    half_life_hours: float = Field(gt=0, le=10000)
    absorption_half_life_hours: float = Field(gt=0, le=10000)

    @model_validator(mode="after")
    def validate_stages(self):
        if not all(isfinite(x.amount_mg) for x in self.stages):
            raise ValueError("Invalid stage amount")
        weeks = [x.week for x in self.stages]
        if weeks[0] != 1 or weeks != sorted(set(weeks)):
            raise ValueError("Stages must start at week 1 and have unique ascending weeks")
        return self


def what_if_doses(data: WhatIfProtocol):
    stages = data.stages
    doses = []
    for index in range(int(data.duration_days / data.interval_days) + 1):
        offset = index * data.interval_days
        if offset >= data.duration_days: break
        week = int(offset // 7) + 1
        amount = next(stage.amount_mg for stage in reversed(stages) if stage.week <= week)
        doses.append((data.start_at + timedelta(days=offset), amount))
    return doses


def verify_what_if_compound(db: Session, compound_id: int):
    c = db.get(Compound, compound_id)
    if c is None or pk.profile(c.name) is None:
        raise HTTPException(400, "Unsupported compound")


@router.post("/what-if/preview")
def preview_what_if(data: WhatIfProtocol, db: Session = Depends(get_db)):
    """Preview hypothetical recurring doses without writing anything to the database."""
    verify_what_if_compound(db, data.compound_id)
    now = datetime.now()
    start = now - timedelta(days=60)
    end = max(now + timedelta(days=45), data.start_at + timedelta(days=data.duration_days))
    if end - start > timedelta(days=730):
        raise HTTPException(400, "What-if timeline exceeds 730 days")
    history_start = start - timedelta(hours=min(data.half_life_hours * 12, 365 * 24))
    q = select(DoseLog).join(Vial).where(Vial.compound_id == data.compound_id,
        DoseLog.kind == "dose", DoseLog.taken_at >= history_start, DoseLog.taken_at <= now)
    actual = [(d.taken_at, d.amount_base / 1000) for d in db.scalars(q)
              if d.vial.content_unit in ("mg", "mcg", "g")]
    schedule = what_if_doses(data)
    planned = [(at, amount) for at, amount in schedule if at >= now]
    rows = pk.series(start, end, actual, planned, data.half_life_hours, data.absorption_half_life_hours)
    return {"rows": rows, "now": now.isoformat(), "actual_doses": len(actual),
            "planned_doses": len(planned), "units": "modeled mg-equivalent exposure",
            "schedule": [{"planned_at": at.isoformat(), "amount_mg": amount} for at, amount in schedule],
            "disclaimer": "Hypothetical exposure only; no protocol, inventory, or dose records changed."}


@router.post("/what-if/save", status_code=201)
def save_what_if(data: WhatIfProtocol, db: Session = Depends(get_db)):
    """Save recurring what-if doses as an existing PK scenario, not an actual protocol."""
    verify_what_if_compound(db, data.compound_id)
    doses = [(at, amount) for at, amount in what_if_doses(data) if at >= datetime.now()]
    if not doses:
        raise HTTPException(400, "No future doses to save")
    scenario = PkScenario(compound_id=data.compound_id, name=data.name,
        half_life_hours=data.half_life_hours, absorption_half_life_hours=data.absorption_half_life_hours)
    db.add(scenario)
    db.flush()
    for at, amount in doses:
        db.add(PkPlannedDose(scenario_id=scenario.id, planned_at=at, amount_mg=amount))
    db.commit()
    return {"id": scenario.id, "planned_doses": len(doses)}

def supported(db):
    return [c for c in db.scalars(select(Compound).order_by(Compound.name)) if pk.profile(c.name)]

@router.get("")
def page(request: Request, db: Session = Depends(get_db)):
    return render(request, "pk.html", compounds=supported(db), protocols=list(db.scalars(select(Protocol).order_by(Protocol.name))), profile=pk.profile, model_info=pk.model_info)

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

def protocol_planned_doses(db: Session, protocol_id: int, compound_id: int, start: datetime, end: datetime):
    """Read-only scheduled mg doses from a saved protocol, with escalation stages."""
    protocol = db.get(Protocol, protocol_id)
    if protocol is None or protocol.start_date is None:
        raise HTTPException(400, "Protocol not found or has no start date")
    if not protocol.is_active:
        raise HTTPException(400, "Select an active protocol")
    days = max(0, (end.date() - protocol.start_date).days + 2)
    if days > 5000:
        raise HTTPException(400, "Protocol projection exceeds supported horizon")
    planned = []
    for item in protocol.items:
        if item.compound_id != compound_id:
            continue
        if item.amount_unit != "mg":
            if item.amount_unit == "mcg":
                factor = 0.001
            elif item.amount_unit == "g":
                factor = 1000.0
            else:
                continue  # IU and other non-mass units cannot be converted to mg
        else:
            factor = 1.0
        for day in staged_occurrences(item, protocol.start_date, days):
            if protocol.end_date and day > protocol.end_date:
                continue
            at = datetime.combine(day, datetime.min.time())
            if item.dose_time:
                try:
                    at = datetime.strptime(day.isoformat() + "T" + item.dose_time, "%Y-%m-%dT%H:%M")
                except ValueError:
                    pass
            if start <= at <= end:
                planned.append((at, item.amount_value * factor))
    return sorted(planned)


@router.get("/data")
def chart_data(compound_id: int, days_back: int = 60, days_forward: int = 45,
               half_life_hours: float | None = None, absorption_half_life_hours: float | None = None,
               scenario_id: int | None = None, protocol_id: int | None = None, db: Session = Depends(get_db)):
    c = db.get(Compound, compound_id)
    defaults = pk.profile(c.name) if c else None
    if defaults is None: raise HTTPException(400, "Unsupported compound")
    if pk.model_info(c.name)["needs_assumptions"] and (half_life_hours is None or absorption_half_life_hours is None):
        raise HTTPException(400, "Enter both hypothetical half-lives for BPC-157")
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
    if protocol_id is not None:
        if scenario_id is not None:
            raise HTTPException(400, "Select either a protocol or a saved scenario")
        planned = protocol_planned_doses(db, protocol_id, compound_id, now, end)
    # Short-lived compounds require sub-hour sampling. Limit sample count by
    # using a compact recent window instead of falsely smooth multi-month curves.
    short = hl <= 24 or pk.model_info(c.name)["level"] in ("formulation-specific", "experimental", "illustrative")
    if short:
        start = max(start, now - timedelta(hours=24))
        end = min(end, now + timedelta(hours=48))
        step = 0.05 if hl < 0.5 else (0.25 if hl < 4 else 1.0)
        # Include all planned events in the displayed window.
        if protocol_id is not None:
            planned = protocol_planned_doses(db, protocol_id, compound_id, now, end)
    else:
        step = 12
    rows = pk.series(start, end, actual, planned, hl, ahl, step_hours=step)
    return {"model": pk.model_info(c.name), "rows": rows, "now": now.isoformat(), "actual_doses": len(actual),
            "planned_doses": len(planned), "units": "modeled mg-equivalent exposure",
            "disclaimer": "Exploratory model, not measured blood concentration or clinical effectiveness."}


@router.get('/compare')
def compare_scenarios(compound_id: int, scenario_ids: str = '', days_back: int = 30,
                      days_forward: int = 60, db: Session = Depends(get_db)):
    """Return a common timeline for baseline and up to four hypothetical scenarios."""
    c = db.get(Compound, compound_id)
    defaults = pk.profile(c.name) if c else None
    if defaults is None: raise HTTPException(400, 'Unsupported compound')
    if pk.model_info(c.name)['needs_assumptions']:
        raise HTTPException(400, 'BPC-157 comparisons require explicit model assumptions; use the main graph')
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


@router.get('/overlay')
def multi_compound_overlay(compound_ids: str, days_back: int = 30,
                           days_forward: int = 60, db: Session = Depends(get_db)):
    """Compare distinct compounds as percent of each compound's displayed peak.

    Values across different compounds are *not* comparable concentrations.
    Actual administrations only; no future dose recommendations or persistence.
    """
    try:
        ids = list(dict.fromkeys(int(item.strip()) for item in compound_ids.split(',') if item.strip()))
    except ValueError:
        raise HTTPException(400, 'Invalid compound IDs')
    if not 1 <= len(ids) <= 4 or any(i <= 0 for i in ids):
        raise HTTPException(400, 'Select between one and four compounds')
    if not (1 <= days_back <= 365 and 1 <= days_forward <= 365):
        raise HTTPException(400, 'Invalid range')
    now = datetime.now()
    start, end = now-timedelta(days=days_back), now+timedelta(days=days_forward)
    output = []
    timeline = None
    for compound_id in ids:
        c = db.get(Compound, compound_id)
        defaults = pk.profile(c.name) if c else None
        if defaults is None:
            raise HTTPException(400, 'Unsupported compound')
        if pk.model_info(c.name)['needs_assumptions']:
            raise HTTPException(400, 'BPC-157 overlay requires explicit model assumptions')
        hl, ahl = defaults
        history_start = start - timedelta(hours=min(hl*12, 365*24))
        doses = db.scalars(select(DoseLog).join(Vial).where(
            Vial.compound_id == compound_id, DoseLog.kind == 'dose',
            DoseLog.taken_at >= history_start, DoseLog.taken_at <= now
        ).order_by(DoseLog.taken_at)).all()
        actual = [(d.taken_at, d.amount_base / 1000) for d in doses
                  if d.vial.content_unit in ('mg', 'mcg', 'g')]
        rows = pk.series(start, end, actual, [], hl, ahl)
        if timeline is None:
            timeline = [row['at'] for row in rows]
        values = [row['actual'] for row in rows]
        peak = max(values, default=0)
        output.append({
            'compound_id': c.id, 'name': c.name,
            'values_percent': [round(value * 100 / peak, 3) if peak else 0 for value in values],
            'display_peak_mg_equivalent': peak,
            'administrations': [{'at': d.isoformat(), 'amount_mg': amount}
                                for d, amount in actual if start <= d <= now],
        })
    return {
        'at': timeline, 'now': now.isoformat(), 'series': output,
        'units': 'percent of each compound’s own peak in the displayed window',
        'disclaimer': 'Normalized shapes only; percentages are NOT cross-compound potency, blood levels, or dosing advice.'
    }
