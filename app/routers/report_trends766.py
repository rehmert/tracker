"""Release 766 integrated read-only weekly trends and private CSV export.

Each metric reports observed coverage; no interpolated or causal scores.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, time, timedelta
import io
import json
import math

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .. import config, metrics
from ..device_models766 import DeviceDay766
from ..models import DoseLog, VitalReading
from ..progress_models762 import ProgressMeasure762, ProgressSettings762
from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..workout_models654 import WorkoutSession654

router = APIRouter()
RANGES766 = (28, 90, 180)


def _mean766(values):
    return round(sum(values) / len(values), 2) if values else None


def _foods766(food_engine, start, end):
    if food_engine is None:
        return None
    try:
        with food_engine.connect() as conn:
            present = {row[0] for row in conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ))}
            if not {"tracker_food_products", "tracker_food_entries"}.issubset(present):
                return {}
            rows = conn.execute(text("""
                SELECT e.eaten_on, e.servings, p.nutrients
                FROM tracker_food_entries e JOIN tracker_food_products p
                  ON e.product_id=p.id
                WHERE e.eaten_on >= :start AND e.eaten_on <= :end
            """), {"start":start.isoformat(), "end":end.isoformat()}).all()
    except Exception:
        # Other domains still report accurately if optional Food is absent.
        return None
    daily = {}
    for day_str, servings, raw in rows:
        entry = daily.setdefault(str(day_str), {"sum": 0.0, "count": 0, "known": 0})
        entry["count"] += 1
        try:
            protein = json.loads(raw).get("proteins")
            number = float(protein) if protein is not None else None
            amount = float(servings)
            if number is None or not math.isfinite(number) or not math.isfinite(amount):
                continue
            if number < 0 or amount <= 0:
                continue
        except (ValueError, TypeError, AttributeError, OverflowError):
            continue
        entry["known"] += 1
        entry["sum"] += number * amount
    return {day:round(entry["sum"], 2) for day,entry in daily.items()
            if entry["count"] > 0 and entry["known"] == entry["count"]}


def weekly_rows766(db: Session, days: int, today: date, food_engine=None):
    if days not in RANGES766:
        raise ValueError("Unsupported reporting range")
    start = today - timedelta(days=days-1)
    week_start = start - timedelta(days=start.weekday())
    weeks = {}
    current = week_start
    while current <= today:
        weeks[current] = {
            "week": current, "end": min(current + timedelta(days=6), today),
            "weights": {}, "waists": {}, "steps": {}, "sleep": {},
            "rest": {}, "glucose": {}, "workouts": 0, "doses": 0,
            "protein": {},
        }
        current += timedelta(days=7)

    def bucket(day):
        if not start <= day <= today:
            return None
        return weeks.get(day - timedelta(days=day.weekday()))

    # Latest actual reading per calendar day; retain sample count by day.
    vitals = list(db.scalars(select(VitalReading).where(
        VitalReading.measured_at >= datetime.combine(start,time.min),
        VitalReading.measured_at < datetime.combine(today+timedelta(days=1),time.min),
    ).order_by(VitalReading.measured_at, VitalReading.id)))
    for reading in vitals:
        group = bucket(reading.measured_at.date())
        if group is not None and reading.weight_kg is not None:
            group["weights"][reading.measured_at.date()] = reading.weight_kg

    settings = db.get(ProgressSettings762, 1)
    tape_unit = settings.measurement_unit if settings and settings.measurement_unit in ("in","cm") else "in"
    for reading in db.scalars(select(ProgressMeasure762).where(
        ProgressMeasure762.measured_on >= start,
        ProgressMeasure762.measured_on <= today,
    ).order_by(ProgressMeasure762.measured_on, ProgressMeasure762.id)):
        group = bucket(reading.measured_on)
        if group is not None and reading.waist_navel is not None:
            group["waists"][reading.measured_on] = reading.waist_navel

    # Device sources can overlap. Latest nonempty measurement per date wins,
    # independently for each metric; never add steps from multiple devices.
    for reading in db.scalars(select(DeviceDay766).where(
        DeviceDay766.measured_on >= start,
        DeviceDay766.measured_on <= today,
    ).order_by(DeviceDay766.id)):
        group = bucket(reading.measured_on)
        if group is None:
            continue
        for column, key in (
            ("steps","steps"), ("sleep_hours","sleep"),
            ("resting_bpm","rest"), ("glucose_avg_mgdl","glucose"),
        ):
            value = getattr(reading, column)
            if value is not None:
                group[key][reading.measured_on] = value

    for session in db.scalars(select(WorkoutSession654).where(
        WorkoutSession654.completed_at.is_not(None),
        WorkoutSession654.started_at >= datetime.combine(start,time.min),
        WorkoutSession654.started_at < datetime.combine(today+timedelta(days=1),time.min),
    )):
        group = bucket(session.started_at.date())
        if group is not None:
            group["workouts"] += 1

    for dose in db.scalars(select(DoseLog).where(
        DoseLog.kind == "dose",
        DoseLog.taken_at >= datetime.combine(start,time.min),
        DoseLog.taken_at < datetime.combine(today+timedelta(days=1),time.min),
    )):
        group = bucket(dose.taken_at.date())
        if group is not None:
            group["doses"] += 1

    protein = _foods766(food_engine, start, today)
    if protein is not None:
        for day_str, value in protein.items():
            try:
                day = date.fromisoformat(day_str)
            except ValueError:
                continue
            group = bucket(day)
            if group is not None:
                group["protein"][day] = value

    rows = []
    for start_week,values in sorted(weeks.items(), reverse=True):
        def average(key, factor=1):
            return _mean766([value * factor for value in values[key].values()])
        rows.append({
            "week":start_week, "end":values["end"],
            "weight":_mean766([
                metrics.weight_from_kg(v, config.WEIGHT_UNIT) for v in values["weights"].values()
            ]),
            "weight_days":len(values["weights"]),
            "waist":average("waists", 1/2.54 if tape_unit == "in" else 1),
            "waist_days":len(values["waists"]),
            "workouts":values["workouts"], "doses":values["doses"],
            "protein":average("protein") if protein is not None else None,
            "protein_days":len(values["protein"]),
            "steps":average("steps"), "step_days":len(values["steps"]),
            "sleep":average("sleep"), "sleep_days":len(values["sleep"]),
            "rest":average("rest"), "rest_days":len(values["rest"]),
            "glucose":average("glucose"), "glucose_days":len(values["glucose"]),
        })
    return rows, {"weight":config.WEIGHT_UNIT, "waist":tape_unit,
                  "food_available":protein is not None,
                  "date_start":start, "date_end":today}


def optional_food766(request):
    from ..food_engine392 import get_food_engine392
    try:
        return get_food_engine392(request)
    except PermissionError:
        return None
    except HTTPException as exc:
        if exc.status_code in (403,503):
            return None
        raise


@router.get("/reports/trends")
def weekly_report766(
    request: Request, days: int = 90,
    db: Session = Depends(get_scoped_db390),
):
    days = days if days in RANGES766 else 90
    rows, units = weekly_rows766(db, days, date.today(), optional_food766(request))
    return render(
        request, "report_trends766.html", rows=rows, units=units, days=days,
        available=RANGES766,
    )


@router.get("/reports/trends.csv")
def weekly_report_csv766(
    request: Request, days: int = 90,
    db: Session = Depends(get_scoped_db390),
):
    days = days if days in RANGES766 else 90
    rows, units = weekly_rows766(db, days, date.today(), optional_food766(request))
    output = io.StringIO()
    writer = csv.writer(output)
    columns = ("week","end","weight","weight_days","waist","waist_days",
               "workouts","doses","protein","protein_days","steps","step_days",
               "sleep","sleep_days","rest","rest_days","glucose","glucose_days")
    writer.writerow(("week_start","week_end",f"weight_{units['weight']}",
                     "weight_days",f"waist_{units['waist']}","waist_days",
                     "completed_workouts","recorded_doses","protein_g_mean_logged_day",
                     "protein_complete_days","steps_mean_logged_day","steps_days",
                     "sleep_h_mean_logged_day","sleep_days",
                     "resting_bpm_mean_logged_day","resting_bpm_days",
                     "glucose_mgdl_mean_logged_day","glucose_days"))
    for row in rows:
        writer.writerow([row[k] if row[k] is not None else "" for k in columns])
    return Response(
        output.getvalue(), media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="tracker_weekly_trends.csv"',
            "Cache-Control":"private, no-store",
        },
    )
