from datetime import date, datetime, time, timedelta
import csv
import io
from fastapi.responses import Response, JSONResponse
from math import ceil, isfinite
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Compound, DoseLog, Vial, PkScenario, PkPlannedDose, Protocol
from ..calendar import staged_occurrences, occurrence_time
from ..templating import render
from .. import pk
from ..pk_library import (
    ExperimentSave, listing as experiment_list,
    save as experiment_save, delete as experiment_delete,
    revise as experiment_revise,
)
from ..pk_workbench import ExperimentInput, run_experiment
from ..pk_model_history import capture as model_capture
from ..pk_analysis_93 import metrics as exposure_metrics

from .. import pk_scenario_ops as scenario_ops
from .. import pk_scenario_version as scenario_version
from .. import pk_scenario_integrity145 as integrity
from .. import pk_calendar_schedule149 as calendar_rules
from .. import pk_delta153 as pk_delta
from .. import pk_staged_schedule as staged
from .. import pk_template_import as pk_import

from .. import pk_guarded_edit161 as guarded_edit
from .. import pk_transform165 as transform165

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
    interval_days: float | None = Field(default=None, ge=0.125, le=90)

class WhatIfProtocol(BaseModel):
    compound_id: int
    name: str = Field(min_length=1, max_length=160)
    start_at: datetime
    interval_days: float = Field(ge=0.125, le=90)
    duration_days: int = Field(ge=1, le=365)
    offset_days: int = Field(default=0, ge=0, le=90)
    stages: list[WhatIfStage] = Field(min_length=1, max_length=52)
    half_life_hours: float = Field(gt=0, le=10000)
    absorption_half_life_hours: float = Field(gt=0, le=10000)

    @model_validator(mode="after")
    def validate_stages(self):
        if not all(isfinite(x.amount_mg) for x in self.stages):
            raise ValueError("Invalid stage amount")
        if not isfinite(self.interval_days):
            raise ValueError("Invalid default interval")
        if any(
            x.interval_days is not None and
            not isfinite(x.interval_days)
            for x in self.stages
        ):
            raise ValueError("Invalid stage interval")
        if self.offset_days >= self.duration_days:
            raise ValueError("Starting offset must be less than duration")
        weeks = [x.week for x in self.stages]
        if weeks[0] != 1 or weeks != sorted(set(weeks)):
            raise ValueError("Stages must start at week 1 and have unique ascending weeks")
        return self


def what_if_doses(data: WhatIfProtocol):
    """Build a hypothetical schedule with stage-specific cadence.

    Stage weeks are relative to the first modeled administration.
    An interval change begins with the first dose in that stage.
    No actual doses or inventory are modified.
    """
    stages = data.stages
    doses = []
    offset = float(data.offset_days)
    while offset < data.duration_days:
        elapsed = offset - data.offset_days
        week = int(elapsed // 7) + 1
        stage = next(
            stage for stage in reversed(stages)
            if stage.week <= week
        )
        doses.append((
            data.start_at + timedelta(days=offset),
            stage.amount_mg,
        ))
        interval = (
            stage.interval_days
            if stage.interval_days is not None
            else data.interval_days
        )
        offset += interval
    return doses


class MultiWhatIfInput(BaseModel):
    """Independent hypothetical schedules on one timeline."""

    schedules: list[WhatIfProtocol] = Field(
        min_length=1, max_length=4
    )

    @model_validator(mode="after")
    def validate_timeline(self):
        if any(s.start_at.tzinfo is not None for s in self.schedules):
            raise ValueError("Use local datetimes without timezone offsets")
        start = min(s.start_at for s in self.schedules)
        end = max(
            s.start_at + timedelta(days=s.duration_days)
            for s in self.schedules
        )
        if end <= start or end - start > timedelta(days=730):
            raise ValueError("Combined timeline cannot exceed 730 days")
        return self


@router.post("/what-if/multi-preview")
def preview_multi_what_if(
    data: MultiWhatIfInput,
    db: Session = Depends(get_db),
):
    """Calculate independent normalized exposure curves; no writes."""
    start = min(s.start_at for s in data.schedules)
    end = max(
        s.start_at + timedelta(days=s.duration_days)
        for s in data.schedules
    )

    hours = (end - start).total_seconds() / 3600
    shortest = min(
        min(s.half_life_hours, s.absorption_half_life_hours)
        for s in data.schedules
    )

    # Cap chart resolution at approximately 2,001 points.
    step = max(0.1, min(12.0, shortest / 3), hours / 1999)

    times = None
    output = []

    for schedule in data.schedules:
        verify_what_if_compound(db, schedule.compound_id)
        compound = db.get(Compound, schedule.compound_id)
        doses = what_if_doses(schedule)

        if len(doses) > 1000:
            raise HTTPException(
                400, "Maximum 1,000 simulated administrations per schedule"
            )

        rows = pk.series(
            start, end, [], doses,
            schedule.half_life_hours,
            schedule.absorption_half_life_hours,
            step_hours=step,
        )

        current_times = [row["at"] for row in rows]
        if times is None:
            times = current_times
        elif times != current_times:
            raise HTTPException(400, "Inconsistent chart timeline")

        values = [row["planned"] for row in rows]
        peak = max(values, default=0.0)

        output.append({
            "name": schedule.name,
            "compound_id": schedule.compound_id,
            "compound_name": compound.name,
            "model": pk.model_info(compound.name),
            "dose_count": len(doses),
            "doses": [
                {"at": at.isoformat(), "amount_mg": amount}
                for at, amount in doses
            ],
            "peak_mg_equivalent": peak,
            "values_percent": [
                round(100.0 * value / peak, 4)
                if peak > 0 else 0.0
                for value in values
            ],
        })

    return {
        "at": times or [],
        "series": output,
        "units": "percentage of each curve's own peak",
        "disclaimer": (
            "Independent hypothetical exposure shapes, not measured "
            "serum concentrations or comparable drug potency. "
            "Nothing was saved."
        ),
    }


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
    allowed = {"Testosterone Cypionate"}
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
    db.add(s)
    db.flush()
    scenario_version.audit(
        db,s.id,"scenario_create",{},
        scenario_version.snapshot(db,s)
    )
    db.commit()
    return {"id": s.id}

@router.put("/scenarios/{sid}")
def update_scenario(
    sid:int,data:ScenarioInput,
    db:Session=Depends(get_db),
    expected:str|None=Header(
        default=None,alias="X-PK-Expected-Version"
    )
):
    s = db.get(PkScenario, sid)
    if s is None: raise HTTPException(404)
    if s.compound_id != data.compound_id: raise HTTPException(400, "Cannot change scenario compound")
    if not all(isfinite(v) for v in (data.half_life_hours, data.absorption_half_life_hours)):
        raise HTTPException(400, "Invalid half-life")
    scenario_version.check(db,s,expected)
    before=scenario_version.snapshot(db,s)
    s.name = data.name
    s.half_life_hours = data.half_life_hours
    s.absorption_half_life_hours = data.absorption_half_life_hours
    scenario_version.audit(
        db,s.id,"scenario_update",
        before,scenario_version.snapshot(db,s)
    )
    db.commit()
    return {"ok":True}

@router.delete("/scenarios/{sid}")
def delete_scenario(
    sid:int,
    db:Session=Depends(get_db),
    expected:str|None=Header(
        default=None,
        alias="X-PK-Expected-Version"
    )
):
    s = db.get(PkScenario, sid)
    if s is None: raise HTTPException(404)
    scenario_version.check(db,s,expected)
    scenario_version.audit(
        db,s.id,"scenario_delete",
        scenario_version.snapshot(db,s),{}
    )
    db.delete(s)
    db.commit()
    return {"ok":True}

@router.post("/scenarios/{sid}/doses", status_code=201)
def add_dose(
    sid:int,data:PlannedInput,
    db:Session=Depends(get_db),
    expected:str|None=Header(
        default=None,alias="X-PK-Expected-Version"
    )
):
    if db.get(PkScenario, sid) is None: raise HTTPException(404)
    obj=scenario_ops.scenario(db,sid)
    scenario_version.check(db,obj,expected)
    d=PkPlannedDose(
        scenario_id=sid,**data.model_dump()
    )
    db.add(d)
    db.flush()
    scenario_version.audit(
        db,sid,"dose_add",{},
        {
            "id":d.id,
            "at":d.planned_at.isoformat(),
            "mg":d.amount_mg
        }
    )
    db.commit()
    return {"id":d.id}

@router.put("/scenarios/{sid}/doses/{did}")
def edit_dose(
    sid:int,did:int,data:PlannedInput,
    db:Session=Depends(get_db),
    expected:str|None=Header(
        default=None,alias="X-PK-Expected-Version"
    )
):
    d = db.get(PkPlannedDose, did)
    if d is None or d.scenario_id != sid: raise HTTPException(404)
    scenario_version.check(
        db,scenario_ops.scenario(db,sid),expected
    )
    before={
        "id":d.id,
        "at":d.planned_at.isoformat(),
        "mg":d.amount_mg
    }
    d.planned_at,d.amount_mg=(
        data.planned_at,data.amount_mg
    )
    scenario_version.audit(
        db,sid,"dose_update",before,
        {
            "id":d.id,
            "at":d.planned_at.isoformat(),
            "mg":d.amount_mg
        }
    )
    db.commit()
    return {"ok":True}

@router.delete("/scenarios/{sid}/doses/{did}")
def delete_dose(
    sid:int,did:int,
    db:Session=Depends(get_db),
    expected:str|None=Header(
        default=None,alias="X-PK-Expected-Version"
    )
):
    d = db.get(PkPlannedDose, did)
    if d is None or d.scenario_id != sid: raise HTTPException(404)
    scenario_version.check(
        db,scenario_ops.scenario(db,sid),expected
    )
    scenario_version.audit(
        db,sid,"dose_delete",
        {
            "id":d.id,
            "at":d.planned_at.isoformat(),
            "mg":d.amount_mg
        },
        {}
    )
    db.delete(d)
    db.commit()
    return {"ok":True}

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



@router.get("/protocol-exposure/{pid}")
def saved_protocol_exposure(
    pid: int, db: Session = Depends(get_db)
):
    """Read-only exposure of saved active or what-if protocols.

    Uses the saved stage schedule. Does not load dose history,
    change protocol status, record doses, or consume inventory.
    """
    protocol = db.get(Protocol, pid)
    if protocol is None:
        raise HTTPException(404, "Protocol not found")

    anchor_date = protocol.start_date or date.today()
    days = min(
        365,
        max(1, ceil(float(protocol.horizon_weeks or 12) * 7)),
    )

    if protocol.start_date and protocol.end_date:
        days = min(
            days,
            max(
                1,
                (protocol.end_date - anchor_date).days + 1,
            ),
        )

    grouped = {}
    for item in protocol.items:
        grouped.setdefault(item.compound_id, []).append(item)

    graphs = []
    skipped = []

    for compound_id, items in grouped.items():
        compound = db.get(Compound, compound_id)
        name = compound.name if compound else str(compound_id)

        parameters = pk.profile(name) if compound else None
        if parameters is None:
            skipped.append({
                "compound": name,
                "reason": "No supported PK model",
            })
            continue

        model = pk.model_info(name)
        if model["needs_assumptions"]:
            skipped.append({
                "compound": name,
                "reason": "Manual half-life assumptions required",
            })
            continue

        if not all(
            isfinite(float(x)) and 0 < float(x) <= 10000
            for x in parameters
        ):
            skipped.append({
                "compound": name,
                "reason": "Invalid model parameters",
            })
            continue

        # Resolve the duration using the existing short-lived
        # compound presentation policy.
        short = (
            parameters[0] <= 24
            or model["level"] in (
                "formulation-specific",
                "experimental",
                "illustrative",
            )
        )

        visible_days = min(days, 7) if short else days
        start_at = datetime.combine(anchor_date, time.min)
        end_at = start_at + timedelta(days=visible_days)

        planned = []
        unsupported_units = set()

        for item in items:
            factor = {
                "mg": 1.0,
                "mcg": 0.001,
                "g": 1000.0,
            }.get(item.amount_unit)

            if factor is None:
                unsupported_units.add(item.amount_unit)
                continue

            amount = float(item.amount_value) * factor
            if not isfinite(amount) or amount <= 0:
                continue

            for day in staged_occurrences(
                item, anchor_date, visible_days
            ):
                wall_time = occurrence_time(
                    item, anchor_date, day
                )
                try:
                    hour, minute = map(
                        int, (wall_time or "00:00").split(":")
                    )
                    at = datetime.combine(
                        day, time(hour, minute)
                    )
                except (ValueError, TypeError):
                    at = datetime.combine(day, time.min)

                if start_at <= at <= end_at:
                    planned.append((at, amount))

        if unsupported_units:
            skipped.append({
                "compound": name,
                "reason": (
                    "Skipped non-mass doses in units: " +
                    ", ".join(sorted(unsupported_units))
                ),
            })

        if not planned:
            skipped.append({
                "compound": name,
                "reason": "No modelable scheduled doses in window",
            })
            continue

        step = (
            0.25 if parameters[0] < 4
            else 1 if short
            else 12
        )

        rows = pk.series(
            start_at,
            end_at,
            [],
            sorted(planned),
            *parameters,
            step_hours=step,
        )

        graphs.append({
            "compound": name,
            "model": model,
            "times": [row["at"] for row in rows],
            "values": [row["planned"] for row in rows],
            "dose_count": len(planned),
            "doses": [
                {"at": at.isoformat(), "amount_mg": amount}
                for at, amount in sorted(planned)
            ],
            "duration_days": visible_days,
            "short_window": visible_days < days,
        })

    result = {
        "protocol": protocol.name,
        "status": (
            "Active" if protocol.is_active else "What-if"
        ),
        "assumed_start": protocol.start_date is None,
        "start_date": anchor_date.isoformat(),
        "horizon_days": days,
        "graphs": graphs,
        "skipped": skipped,
        "disclaimer": (
            "Hypothetical modeled mg-equivalent exposure, "
            "not measured serum concentration or a "
            "dosing recommendation. No records changed."
        ),
    }

    return JSONResponse(
        content=result,
        headers={"Cache-Control": "no-store"},
    )


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
    return {"model": pk.model_info(c.name), "rows": rows, "now": now.isoformat(),
            "planned_schedule": [
                {"at": at.isoformat(), "amount_mg": amount}
                for at, amount in planned
            ],
            "actual_doses": len(actual),
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



@router.get("/workspace")
def pk_workspace(
    request:Request, db:Session=Depends(get_db)
):
    from ..models import LabReport
    from ..routers.inventory_forecast import build_rows

    protocols=list(db.scalars(
        select(Protocol).order_by(Protocol.name)
    ))
    labs=list(db.scalars(
        select(LabReport).order_by(
            LabReport.drawn_on.desc()
        ).limit(5)
    ))
    stock=build_rows(db)
    recent_doses=list(db.scalars(
        select(DoseLog)
        .where(DoseLog.kind=='dose')
        .order_by(DoseLog.taken_at.desc())
        .limit(12)
    ))
    return render(
        request,"pk_workspace.html",
        protocols=protocols,labs=labs,stock=stock,
        recent_doses=recent_doses
    )


@router.post("/workbench/{pid}")
def protocol_experiment(
    pid: int,
    settings: ExperimentInput,
    db: Session = Depends(get_db),
):
    """Stateless read-only saved-protocol experiment."""
    return JSONResponse(
        content=run_experiment(db, pid, settings),
        headers={"Cache-Control": "no-store"},
    )



@router.get("/library/{pid}")
def pk_library_list(
    pid: int, db: Session = Depends(get_db)
):
    if db.get(Protocol,pid) is None:
        raise HTTPException(404,"Protocol not found")
    return JSONResponse(
        content=experiment_list(pid),
        headers={"Cache-Control":"no-store"}
    )


@router.post("/library/{pid}")
def pk_library_save(
    pid: int, data: ExperimentSave,
    db: Session = Depends(get_db)
):
    protocol = db.get(Protocol,pid)
    if protocol is None:
        raise HTTPException(404,"Protocol not found")
    if not any(
        item.compound_id == data.settings.compound_id
        for item in protocol.items
    ):
        raise HTTPException(
            400,"Selected compound not in source protocol"
        )
    return experiment_save(
        pid, protocol, data,
        model_assumptions=model_capture(
            db.get(Compound, data.settings.compound_id)
        ),
    )


@router.delete("/library/{pid}/{experiment_id}")
def pk_library_delete(
    pid: int, experiment_id: str,
    db: Session = Depends(get_db)
):
    if db.get(Protocol,pid) is None:
        raise HTTPException(404,"Protocol not found")
    if len(experiment_id)!=32 or not all(
        c in "0123456789abcdef" for c in experiment_id
    ):
        raise HTTPException(400,"Invalid experiment ID")
    return experiment_delete(pid,experiment_id)



class ExperimentComparisonInput(BaseModel):
    ids: list[str] = Field(min_length=2,max_length=4)
    include_previous: bool = False


@router.post("/library/{pid}/compare")
def pk_compare_experiments(
    pid:int,
    data:ExperimentComparisonInput,
    db:Session=Depends(get_db),
):
    if db.get(Protocol,pid) is None:
        raise HTTPException(404,"Protocol not found")

    if len(set(data.ids))!=len(data.ids):
        raise HTTPException(400,"Duplicate experiments")

    entries={
        item["id"]:item
        for item in experiment_list(pid)
    }
    if any(identifier not in entries for identifier in data.ids):
        raise HTTPException(404,"Experiment not found")

    chosen=[entries[i] for i in data.ids]
    if len({
        e["settings"]["compound_id"]
        for e in chosen
    })!=1:
        raise HTTPException(
            400,"Choose experiments for one compound"
        )

    if data.include_previous:
        augmented = list(chosen)
        for item in chosen:
            revisions = item.get('revisions') or []
            if revisions:
                older = dict(revisions[-1])
                older['name'] = (
                    str(older['name'])
                    + ' (previous revision)'
                )
                augmented.append(older)
        chosen = augmented

    rows=[]
    for item in chosen:
        settings=ExperimentInput.model_validate(
            item["settings"]
        )
        result=run_experiment(
            db,pid,settings,
            source_snapshot=item.get("source_snapshot"),
            model_assumptions=item.get("model_assumptions"),
        )
        values=result["modified"]
        rows.append({
            "id":item["id"],
            "name":item["name"],
            "compound":result["compound"],
            "times":result["times"],
            "values":values,
            "peak":max(values,default=0),
            "trough":min(values,default=0),
            "inventory_demand":result["inventory"].get(
                "selected_future_demand_mg"
            ),
            "snapshot":item.get("source_snapshot") is not None,
            "statistics": exposure_metrics(
                result["times"], values
            ),
            "model_source": result["model_source"],
            "model_parameter_drift":
                result["model_parameter_drift"],
        })

    return JSONResponse(
        content={
            "experiments":rows,
            "disclaimer":(
                "Exposure curves are hypothetical and "
                "normalized independently. Inventory and "
                "laboratory inputs use current data. Older "
                "experiments without snapshots use the "
                "current protocol."
            ),
        },
        headers={"Cache-Control":"no-store"},
    )


@router.put("/library/{pid}/{experiment_id}")
def pk_update_experiment(
    pid:int,
    experiment_id:str,
    data:ExperimentSave,
    db:Session=Depends(get_db),
):
    p=db.get(Protocol,pid)
    if p is None:
        raise HTTPException(404,"Protocol not found")
    if not any(
        item.compound_id==data.settings.compound_id
        for item in p.items
    ):
        raise HTTPException(400,"Compound not in protocol")

    return experiment_revise(
        pid, experiment_id, p, data,
        model_assumptions=model_capture(
            db.get(Compound, data.settings.compound_id)
        ),
    )



@router.get("/scenarios/{sid}/dose-state")
def pk_dose_state(
    sid:int,db:Session=Depends(get_db)
):
    return scenario_ops.state(db,sid)


@router.post("/scenarios/{sid}/doses/generate-preview")
def pk_dose_preview(
    sid:int,
    data:scenario_ops.SequenceInput,
    db:Session=Depends(get_db)
):
    scenario_ops.scenario(db,sid)
    return {"doses":scenario_ops.preview(data)}


@router.post("/scenarios/{sid}/doses/create-batch")
def pk_dose_batch_create(
    sid:int,
    data:scenario_ops.SequenceInput,
    db:Session=Depends(get_db)
):
    return scenario_ops.create_many(db,sid,data)


@router.post("/scenarios/{sid}/doses/delete-batch")
def pk_dose_batch_delete(
    sid:int,
    data:scenario_ops.DeleteInput,
    db:Session=Depends(get_db)
):
    return scenario_ops.delete_many(db,sid,data)


@router.post("/scenarios/{sid}/doses/undo-delete")
def pk_dose_batch_undo(
    sid:int,
    data:scenario_ops.RestoreInput,
    db:Session=Depends(get_db)
):
    return scenario_ops.restore(db,sid,data)



@router.post("/scenarios/{sid}/duplicate",status_code=201)
def pk_duplicate(
    sid:int,
    db:Session=Depends(get_db)
):
    original=scenario_ops.scenario(db,sid)

    copy=PkScenario(
        compound_id=original.compound_id,
        name=(original.name+' (copy)')[:160],
        half_life_hours=original.half_life_hours,
        absorption_half_life_hours=
            original.absorption_half_life_hours
    )

    db.add(copy)
    db.flush()

    for dose in sorted(
        original.doses,
        key=lambda x:(x.planned_at,x.id)
    ):
        db.add(PkPlannedDose(
            scenario_id=copy.id,
            planned_at=dose.planned_at,
            amount_mg=dose.amount_mg
        ))

    integrity.changed(
        db,copy,"scenario_duplicate",{}
    )
    db.commit()
    return {'id':copy.id,'name':copy.name}


@router.get("/scenarios/{sid}/change-history")
def pk_scenario_changes(
    sid:int,
    db:Session=Depends(get_db)
):
    from ..models import ChangeAudit

    scenario_ops.scenario(db,sid)

    entries=list(db.scalars(
        select(ChangeAudit)
        .where(
            ChangeAudit.entity_type=='pk_scenario',
            ChangeAudit.entity_id==sid
        )
        .order_by(ChangeAudit.id.desc())
        .limit(30)
    ))

    return [
        {
            'id':entry.id,
            'action':entry.action,
            'at':(
                entry.created_at.isoformat()
                if entry.created_at else None
            )
        }
        for entry in entries
    ]



@router.get("/scenarios/{sid}/revision")
def pk_scenario_revision(
    sid:int,db:Session=Depends(get_db)
):
    obj=scenario_ops.scenario(db,sid)
    return {
        "version":scenario_version.version(
            scenario_version.snapshot(db,obj)
        )
    }



@router.post("/scenarios/{sid}/staged-preview")
def pk_staged_preview(
    sid:int,
    data:staged.StagedInput,
    db:Session=Depends(get_db)
):
    scenario_ops.scenario(db,sid)
    return {
        "doses":staged.project(data),
        "caveat":"Elapsed wall-clock days; timezone and DST not interpreted"
    }


@router.post("/scenarios/{sid}/staged-replace")
def pk_staged_replace(
    sid:int,
    data:staged.StagedInput,
    db:Session=Depends(get_db)
):
    obj=scenario_ops.scenario(db,sid)

    if not data.expected_version:
        raise HTTPException(
            400,"Revision required; preview again"
        )

    scenario_version.check(
        db,obj,data.expected_version
    )

    generated=staged.project(data)
    before=scenario_version.snapshot(db,obj)

    for dose in list(obj.doses):
        db.delete(dose)

    db.flush()

    for dose in generated:
        db.add(PkPlannedDose(
            scenario_id=sid,
            planned_at=datetime.fromisoformat(
                dose["planned_at"]
            ),
            amount_mg=dose["amount_mg"]
        ))

    scenario_version.audit(
        db,sid,"staged_replace",
        before,{"doses":generated}
    )

    db.commit()

    return {"replaced":len(generated)}



@router.post("/scenarios/import-preview")
def pk_import_preview(
    data:pk_import.Template,
    db:Session=Depends(get_db)
):
    pk_import.validate(db,data)

    return {
        "name":data.name,
        "count":len(data.doses),
        "compound":data.compound_name,
        "first":min(
            (
                dose.planned_at.isoformat()
                for dose in data.doses
            ),
            default=None
        ),
        "last":max(
            (
                dose.planned_at.isoformat()
                for dose in data.doses
            ),
            default=None
        )
    }


@router.post(
    "/scenarios/import-confirm",
    status_code=201
)
def pk_import_confirm(
    data:pk_import.Template,
    db:Session=Depends(get_db)
):
    return pk_import.create(db,data)



@router.post("/scenarios/{sid}/doses/create-batch-checked")
def pk_create_batch_checked(
    sid:int,
    data:scenario_ops.SequenceInput,
    db:Session=Depends(get_db),
    expected:str|None=Header(
        default=None,
        alias="X-PK-Expected-Version"
    )
):
    obj=scenario_ops.scenario(db,sid)
    integrity.required(db,obj,expected)
    before=scenario_version.snapshot(db,obj)
    result=scenario_ops.create_many(
        db,sid,data,commit=False
    )
    integrity.changed(db,obj,"bulk_create",before)
    db.commit()
    return result



@router.post("/scenarios/{sid}/calendar-preview")
def pk_calendar_preview(
    sid:int,
    data:calendar_rules.CalendarRule,
    db:Session=Depends(get_db)
):
    scenario_ops.scenario(db,sid)
    return calendar_rules.project(data)


@router.post("/scenarios/{sid}/calendar-replace")
def pk_calendar_replace(
    sid:int,
    data:calendar_rules.CalendarRule,
    db:Session=Depends(get_db)
):
    obj=scenario_ops.scenario(db,sid)
    integrity.required(
        db,obj,data.expected_version
    )

    projected=calendar_rules.project(data)

    if projected['warnings']:
        raise HTTPException(
            409,
            'Resolve DST warnings before replacing the schedule'
        )

    before=scenario_version.snapshot(db,obj)

    for dose in list(obj.doses):
        db.delete(dose)

    db.flush()

    for dose in projected['doses']:
        db.add(PkPlannedDose(
            scenario_id=sid,
            planned_at=datetime.fromisoformat(
                dose['planned_at']
            ),
            amount_mg=dose['amount_mg']
        ))

    integrity.changed(
        db,obj,'calendar_replace',before
    )
    db.commit()

    return {
        'replaced':len(projected['doses'])
    }



@router.get("/scenarios/delta")
def pk_scenario_delta(
    compound_id:int,
    scenario_a:int,
    scenario_b:int,
    days_back:int=30,
    days_forward:int=60,
    db:Session=Depends(get_db)
):
    if scenario_a==scenario_b:
        raise HTTPException(
            400,'Choose different scenarios'
        )

    result=compare_scenarios(
        compound_id,
        f'{scenario_a},{scenario_b}',
        days_back,
        days_forward,
        db
    )

    first=next(
        (
            s for s in result['series']
            if s['id']==scenario_a
        ),
        None
    )

    second=next(
        (
            s for s in result['series']
            if s['id']==scenario_b
        ),
        None
    )

    if first is None or second is None:
        raise HTTPException(
            400,
            'Both scenarios must belong to the same compound'
        )

    summary=pk_delta.delta(
        result['at'],
        first['values'],
        second['values']
    )

    return {
        'at':result['at'],
        'scenario_a':first['name'],
        'scenario_b':second['name'],
        **summary,
        'disclaimer':(
            'Model difference only; not measured levels '
            'or relative clinical effect.'
        )
    }



@router.post("/workspace/{sid}/edit-dose")
def workspace_checked_dose_edit(
    sid:int,
    data:guarded_edit.CheckedEdit,
    db:Session=Depends(get_db)
):
    return guarded_edit.update(db,sid,data)



@router.post("/workspace/{sid}/transform-preview")
def pk_transform_preview(
    sid:int,data:transform165.Transform,
    db:Session=Depends(get_db)
):
    obj=scenario_ops.scenario(db,sid)
    scenario_version.check(
        db,obj,data.expected_version
    )
    return {
        'doses':transform165.projected(
            scenario_ops.rows(db,sid),data
        ),
        'saved':False
    }


@router.post("/workspace/{sid}/transform-apply")
def pk_transform_apply(
    sid:int,data:transform165.Transform,
    db:Session=Depends(get_db)
):
    return transform165.apply(db,sid,data)
