"""Batches 57-60: stateless saved-protocol experiments.

No mutation of Protocol, ProtocolItem, DoseLog, Vial,
LabReport, or LabResult. Changes exist only in the response.
"""
from datetime import date, datetime, time, timedelta
from math import isfinite
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from . import pk, services
from .pk_schedule_core import schedule_doses as precise_schedule
from .pk_precision import interval_assessment
from .pk_model_history import resolve as resolve_model
from .pk_dose_matching import candidates as dose_candidates
from .pk_inventory_events import forecast_inventory
from .pk_release_quality import timing_check, recorded, reconcile
from .models import (
    Protocol, Compound, Vial, LabReport, LabResult,
)


class DoseEdit(BaseModel):
    index: int = Field(ge=0, le=999)
    action: str = Field(pattern="^(keep|skip|delay|amount)$")
    hours: float = Field(default=0, ge=0, le=168)
    amount_mg: float | None = Field(
        default=None, gt=0, le=100000
    )


class ExperimentInput(BaseModel):
    compound_id: int = Field(gt=0)
    horizon_days: int = Field(default=84, ge=7, le=180)
    dose_multiplier: float = Field(
        default=1, ge=0.25, le=3
    )
    interval_multiplier: float = Field(
        default=1, ge=0.5, le=2
    )
    start_shift_days: int = Field(
        default=0, ge=-30, le=30
    )
    skip_dose_index: int | None = Field(
        default=None, ge=0, le=1000
    )
    delay_hours: float = Field(
        default=0, ge=0, le=168
    )
    lab_analyte: str = Field(default="", max_length=120)
    dose_edits: list[DoseEdit] = Field(
        default_factory=list, max_length=100
    )


UNITS = {"mg": 1.0, "mcg": 0.001, "g": 1000.0}


def schedule_doses(
    protocol, compound_id, anchor_date, days,
    dose_multiplier=1.0, interval_multiplier=1.0,
):
    return precise_schedule(
        protocol, compound_id, anchor_date, days,
        dose_multiplier=dose_multiplier,
        interval_multiplier=interval_multiplier,
    )



def summarize_stock(db, compound_id, baseline, modified):
    """Use recorded remaining stock, not original vial labels."""
    vials = list(db.scalars(
        select(Vial).where(
            Vial.compound_id == compound_id
        )
    ))

    views = services.vial_views(db, vials)
    eligible = []
    today = date.today()

    for vial in vials:
        view = views.get(vial.id)
        if view is None or view.dim != "mass":
            continue
        if vial.status not in ("sealed", "in_use"):
            continue
        if vial.closed_on:
            continue
        if vial.expires_on and vial.expires_on < today:
            continue
        if (
            vial.beyond_use_on and
            vial.beyond_use_on < today
        ):
            continue
        if view.remaining_base > 0:
            eligible.append(view)

    remaining = sum(
        view.remaining_base for view in eligible
    )

    value_cents = sum(
        view.remaining_base * view.cost_per_base
        for view in eligible
    )

    cost_per_mcg = (
        value_cents / remaining if remaining > 0
        else None
    )

    base_mg = sum(amount for _, amount in baseline)
    new_mg = sum(amount for _, amount in modified)

    def estimated_cost(mg):
        if cost_per_mcg is None:
            return None
        return round(mg * 1000 * cost_per_mcg / 100, 2)

    return {
        "available_mg": round(remaining / 1000, 5),
        "baseline_demand_mg": round(base_mg, 5),
        "modified_demand_mg": round(new_mg, 5),
        "baseline_estimated_cost": estimated_cost(base_mg),
        "modified_estimated_cost": estimated_cost(new_mg),
        "eligible_vials": len(eligible),
        "caveat": (
            "Approximate planning only. Recorded remaining "
            "mass excludes already logged consumption and "
            "transfers. Eligibility uses current expiration "
            "and beyond-use dates, not projected dates. "
            "Shared inventory, future consumption, pricing "
            "changes, preparation waste, and actual "
            "administration are not forecast."
        ),
    }


def selected_labs(db, analyte, first, last):
    """Up to three analytes; retain their distinct units."""
    from sqlalchemy import func

    names = [
        row[0] for row in db.execute(
            select(LabResult.analyte).distinct()
        ).all()
    ]
    names = sorted(names,key=str.casefold)[:200]
    selected = list(dict.fromkeys(
        term.strip().casefold()
        for term in analyte.split(",")
        if term.strip()
    ))
    if len(selected)>3:
        raise HTTPException(400,"Select at most three analytes")
    if not selected:
        return names, []

    rows = db.execute(
        select(LabResult,LabReport)
        .join(
            LabReport,
            LabResult.report_id == LabReport.id
        )
        .where(
            LabReport.drawn_on >= first,
            LabReport.drawn_on <= last,
            func.lower(LabResult.analyte).in_(selected),
        )
        .order_by(LabReport.drawn_on)
        .limit(300)
    ).all()

    observations = []
    for result, report in rows:
        observations.append({
            "report_id":report.id,
            "date":report.drawn_on.isoformat(),
            "analyte":result.analyte,
            "value":result.value,
            "unit":result.unit,
            "ref_low":result.ref_low,
            "ref_high":result.ref_high,
        })
    return names,observations



def run_experiment(db, protocol_id, settings, source_snapshot=None, model_assumptions=None):
    protocol = db.get(Protocol, protocol_id)
    if protocol is None:
        raise HTTPException(404, "Protocol not found")

    if source_snapshot is not None:
        try:
            protocol=SimpleNamespace(
                name=source_snapshot["name"],
                start_date=(
                    date.fromisoformat(
                        source_snapshot["start_date"]
                    )
                    if source_snapshot.get("start_date")
                    else None
                ),
                end_date=(
                    date.fromisoformat(
                        source_snapshot["end_date"]
                    )
                    if source_snapshot.get("end_date")
                    else None
                ),
                items=[
                    SimpleNamespace(**item)
                    for item in source_snapshot["items"]
                ],
            )
        except (KeyError,TypeError,ValueError) as exc:
            raise HTTPException(
                400,"Invalid saved source snapshot"
            ) from exc

    compound = db.get(Compound, settings.compound_id)
    if compound is None:
        raise HTTPException(404, "Compound not found")

    if not any(
        item.compound_id == compound.id
        for item in protocol.items
    ):
        raise HTTPException(
            400, "Compound is not in this protocol"
        )

    try:
        model, model_source, model_drift = resolve_model(
            compound, model_assumptions
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    parameters = (
        (
            model['half_life_hours'],
            model['absorption_half_life_hours'],
        )
        if model else None
    )

    info = (
        model['evidence']
        if model and model_source == 'saved'
        else pk.model_info(compound.name)
    )

    if (
        parameters is None or
        (
            info.get("needs_assumptions")
            and model_source != 'saved'
        )
    ):
        raise HTTPException(
            400,
            "This compound lacks usable default PK "
            "parameters; no assumptions were invented",
        )

    baseline_start = protocol.start_date or date.today()
    modified_start = (
        baseline_start +
        timedelta(days=settings.start_shift_days)
    )

    def effective_days(anchor):
        horizon = settings.horizon_days
        if (
            protocol.start_date is not None and
            protocol.end_date is not None
        ):
            # Shift end date with start date in the
            # hypothetical scenario.
            last = (
                protocol.end_date -
                protocol.start_date
            ).days + 1
            horizon = min(horizon, max(1, last))
        return max(1, horizon)

    try:
        baseline = schedule_doses(
            protocol, compound.id, baseline_start,
            effective_days(baseline_start),
        )
        modified = schedule_doses(
            protocol, compound.id, modified_start,
            effective_days(modified_start),
            dose_multiplier=settings.dose_multiplier,
            interval_multiplier=settings.interval_multiplier,
        )
    except (ValueError, OverflowError) as exc:
        raise HTTPException(400, str(exc)) from exc

    editable = list(modified)

    if settings.dose_edits:
        if settings.skip_dose_index is not None:
            raise HTTPException(
                400, "Use either individual dose edits or "
                "the legacy skip/delay control, not both"
            )
        indices = [edit.index for edit in settings.dose_edits]
        if len(set(indices)) != len(indices):
            raise HTTPException(400, "Duplicate dose edit")
        for edit in settings.dose_edits:
            if edit.index >= len(modified):
                raise HTTPException(
                    400, "Dose edit outside modeled schedule"
                )
            at, amount = modified[edit.index]
            if edit.action == "skip":
                modified[edit.index] = None
            elif edit.action == "delay":
                modified[edit.index] = (
                    at + timedelta(hours=edit.hours), amount
                )
            elif edit.action == "amount":
                if edit.amount_mg is None:
                    raise HTTPException(
                        400, "Enter an edited dose amount"
                    )
                modified[edit.index] = (
                    at, edit.amount_mg
                )
        modified = [
            row for row in modified if row is not None
        ]
    else:
        if (
            settings.skip_dose_index is not None and
            settings.skip_dose_index >= len(modified)
        ):
            raise HTTPException(
                400, "Skipped-dose number exceeds "
                "the experiment schedule"
            )
        if settings.skip_dose_index is not None:
            index = settings.skip_dose_index
            if settings.delay_hours > 0:
                at, amount = modified[index]
                modified[index] = (
                    at + timedelta(hours=settings.delay_hours),
                    amount,
                )
            else:
                modified.pop(index)
        elif settings.delay_hours:
            raise HTTPException(
                400, "Select a dose before entering a delay"
            )

    modified.sort(key=lambda pair: pair[0])

    start = datetime.combine(
        min(baseline_start, modified_start),
        time.min
    )
    end = datetime.combine(
        max(
            baseline_start +
            timedelta(days=effective_days(baseline_start)),
            modified_start +
            timedelta(days=effective_days(modified_start)),
        ),
        time.min
    ) + timedelta(hours=max(
        settings.delay_hours,
        *(edit.hours for edit in settings.dose_edits),
        0,
    ))

    shortest = min(parameters)
    hours = (end - start).total_seconds() / 3600

    # A bounded, common sample grid: no interpolation
    # mismatch between baseline and modified curves.
    step = max(
        0.25,
        hours / 1800,
        min(12.0, shortest / 3),
    )

    baseline_rows = pk.series(
        start, end, [], baseline,
        *parameters, step_hours=step
    )
    modified_rows = pk.series(
        start, end, [], modified,
        *parameters, step_hours=step
    )

    if (
        [row["at"] for row in baseline_rows] !=
        [row["at"] for row in modified_rows]
    ):
        raise HTTPException(
            500, "Mismatched experiment timelines"
        )

    names, labs = selected_labs(
        db, settings.lab_analyte,
        start.date(), end.date()
    )

    inventory = summarize_stock(
        db, compound.id, baseline, modified
    )

    inventory.update(forecast_inventory(
        db, protocol_id, compound.id,
        settings.horizon_days, modified
    ))

    for observation in labs:
        at = observation["date"]
        previous = [
            dose_at.date() for dose_at, _ in baseline
            if dose_at.date().isoformat() <= at
        ]
        observation["days_since_scheduled_dose"] = (
            (date.fromisoformat(at)-max(previous)).days
            if previous else None
        )

    today=date.today()
    first=today-timedelta(days=27)
    actual=recorded(db,compound.id,first,today)
    historical=reconcile(baseline,actual,first,today)
    alignment = dose_candidates(
        [
            (at, mg) for at, mg in baseline
            if first <= at.date() <= today
        ],
        actual,
    )
    timing=timing_check(
        protocol,compound.id,baseline_start,
        effective_days(baseline_start)
    )
    assumptions=[]
    if protocol.start_date is None:
        assumptions.append("Assumed protocol start: today")
    if inventory.get("unmodeled_active_protocols"):
        assumptions.append(
            "Some competing schedules not modeled"
        )
    if inventory.get("forecast_truncated"):
        assumptions.append(
            "Detailed ledger capped; aggregate totals complete"
        )
    assumptions.extend(timing["warnings"])

    for observation in labs:
        drawn=date.fromisoformat(observation["date"])
        earlier=[
            at.date() for at,_ in actual
            if at.date()<=drawn
        ]
        observation["days_since_recorded_dose"]=(
            (drawn-max(earlier)).days if earlier else None
        )

    def as_doses(rows):
        return [
            {
                "at": at.isoformat(),
                "amount_mg": amount,
            }
            for at, amount in rows
        ]

    return {
        "protocol": protocol.name,
        "compound": compound.name,
        "model": info,
        "model_assumptions": model,
        "model_source": model_source,
        "model_parameter_drift": model_drift,
        "assumed_start": protocol.start_date is None,
        "times": [
            row["at"] for row in baseline_rows
        ],
        "baseline": [
            row["planned"] for row in baseline_rows
        ],
        "modified": [
            row["planned"] for row in modified_rows
        ],
        "baseline_doses": as_doses(baseline),
        "modified_doses": as_doses(modified),
        "editable_doses": as_doses(editable),
        "applied_edits": [
            edit.model_dump() for edit in settings.dose_edits
        ],
        "baseline_interval_analysis":
            interval_assessment(baseline_rows, baseline),
        "modified_interval_analysis":
            interval_assessment(modified_rows, modified),
        "inventory": inventory,
        "recorded_reconciliation":historical,
        "dose_candidate_alignment":alignment,
        "schedule_consistency":timing,
        "assumptions":assumptions,
        "using_source_snapshot":source_snapshot is not None,
        "lab_options": names,
        "labs": labs,
        "disclaimer": (
            "Read-only hypothetical exposure in mg-equivalent "
            "units, not blood concentration or a treatment "
            "recommendation. Laboratory results are independent "
            "observations. No records or inventory changed."
        ),
    }
