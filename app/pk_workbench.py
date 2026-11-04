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
from .calendar import staged_occurrences, occurrence_time
from .models import (
    Protocol, Compound, Vial, LabReport, LabResult,
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


UNITS = {"mg": 1.0, "mcg": 0.001, "g": 1000.0}


def schedule_doses(
    protocol, compound_id, anchor_date, days,
    dose_multiplier=1.0, interval_multiplier=1.0,
):
    """Use existing staged calendar logic, without mutating rows."""
    planned = []

    for item in protocol.items:
        if item.compound_id != compound_id:
            continue

        factor = UNITS.get(item.amount_unit)
        if factor is None:
            raise ValueError(
                "Selected compound includes non-mass units"
            )

        amount = (
            float(item.amount_value) *
            factor * dose_multiplier
        )

        if not isfinite(amount) or amount <= 0:
            raise ValueError("Invalid modeled dose")

        if (
            item.dose_days and
            interval_multiplier != 1
        ):
            raise ValueError(
                "Interval adjustments are unavailable for "
                "fixed-weekday schedules; use dose changes "
                "or skip/delay experiments instead"
            )

        count = float(item.freq_count)
        if not isfinite(count) or count <= 0:
            raise ValueError("Invalid saved frequency")

        if item.freq_period == "interval":
            count *= interval_multiplier
        else:
            count /= interval_multiplier

        proxy = SimpleNamespace(
            freq_count=count,
            freq_period=item.freq_period,
            start_week=item.start_week,
            end_week=item.end_week,
            dose_days=item.dose_days,
            dose_time=item.dose_time,
        )

        for day in staged_occurrences(
            proxy, anchor_date, days
        ):
            wall = occurrence_time(
                proxy, anchor_date, day
            ) or "00:00"

            try:
                hour, minute = map(int, wall.split(":"))
                when = datetime.combine(
                    day, time(hour, minute)
                )
            except (ValueError, TypeError):
                raise ValueError(
                    "Invalid saved administration time"
                )

            planned.append((when, amount))

    planned.sort(key=lambda row: row[0])

    if len(planned) > 1000:
        raise ValueError(
            "Experiment exceeds 1,000 modeled doses"
        )

    return planned


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
    names = [
        row[0] for row in db.execute(
            select(LabResult.analyte).distinct()
        ).all()
    ]

    names = sorted(
        names, key=str.casefold
    )[:200]

    if not analyte.strip():
        return names, []

    chosen = analyte.strip().casefold()
    rows = db.execute(
        select(LabResult, LabReport)
        .join(
            LabReport,
            LabResult.report_id == LabReport.id,
        )
        .where(
            LabReport.drawn_on >= first,
            LabReport.drawn_on <= last,
        )
        .order_by(LabReport.drawn_on)
        .limit(500)
    ).all()

    observations = []
    for result, report in rows:
        if result.analyte.casefold() != chosen:
            continue

        observations.append({
            "date": report.drawn_on.isoformat(),
            "analyte": result.analyte,
            "value": result.value,
            "unit": result.unit,
            "ref_low": result.ref_low,
            "ref_high": result.ref_high,
        })

    return names, observations[:100]


def run_experiment(db, protocol_id, settings):
    protocol = db.get(Protocol, protocol_id)
    if protocol is None:
        raise HTTPException(404, "Protocol not found")

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

    parameters = pk.profile(compound.name)
    info = pk.model_info(compound.name)

    if parameters is None or info["needs_assumptions"]:
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

    if (
        settings.skip_dose_index is not None and
        settings.skip_dose_index >= len(modified)
    ):
        raise HTTPException(
            400,
            "Skipped-dose number exceeds the experiment schedule"
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
    ) + timedelta(hours=settings.delay_hours)

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
        "inventory": inventory,
        "lab_options": names,
        "labs": labs,
        "disclaimer": (
            "Read-only hypothetical exposure in mg-equivalent "
            "units, not blood concentration or a treatment "
            "recommendation. Laboratory results are independent "
            "observations. No records or inventory changed."
        ),
    }
