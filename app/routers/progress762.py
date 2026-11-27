"""Release 762 mobile-first longitudinal progress dashboard.

Read existing workspace-scoped vital/lab/workout records. New measurements are
additive and optional. Food is accessed only via the authorized food engine.
No composite score, diagnosis or imputed missing readings.
"""
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
import json
import math
from urllib.parse import urlencode
from starlette.responses import RedirectResponse

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .. import charts, config, labs, metrics, services
from ..food_read_engine406 import get_food_read_engine406
from ..models import LabReport, LabResult, VitalReading
from ..progress_calc762 import (daily_weights762, moving762, weight_report762,
                                metric_change_details762, strength_trend762, interpret762)
from ..progress_models762 import (MEASURES762, COMPOSITION762, FREQUENCIES762,
    ProgressSettings762, ProgressMeasure762, ProgressComposition762,
    ProgressFunction762, ProgressMarker762)
from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from ..workout_models667 import WorkoutSetType667

router = APIRouter()
RANGES762 = {30: "30 days", 90: "90 days", 180: "6 months",
             365: "1 year", 0: "All time"}
KINDS762 = {
    "measure": ProgressMeasure762, "composition": ProgressComposition762,
    "function": ProgressFunction762, "marker": ProgressMarker762,
}
MARKER_KINDS762 = ("intervention", "workout", "nutrition", "photo", "other")
FUNCTION_FIELDS762 = {
    "knee_pain": (0, 10), "shoulder_pain": (0, 10),
    "walking_minutes": (0, 10000), "walking_distance_km": (0, 1000),
    "sit_to_stand_reps": (0, 1000), "recovery": (1, 5),
}
INTEGER_FIELDS762 = {"knee_pain", "shoulder_pain", "sit_to_stand_reps", "recovery"}


def _progress_filters806(values):
    """Allow only recognized display filters, never a return URL."""
    filters = {}
    for key, allowed in (("days", RANGES762), ("markers", (0, 1)),
                         ("reps", range(1, 201))):
        try:
            number = int(values.get(key, ""))
        except (ValueError, TypeError, OverflowError):
            continue
        if number in allowed:
            filters[key] = number
    try:
        machine = int(values.get("machine", ""))
        if 0 < machine <= 2**63 - 1:
            filters["machine"] = machine
    except (ValueError, TypeError, OverflowError):
        pass
    analyte = values.get("analyte", "")
    if isinstance(analyte, str) and 0 < len(analyte) <= 256:
        filters["analyte"] = analyte
    return filters


def _progress_redirect806(request, section, *, msg="", err="", edit_id=None):
    filters = _progress_filters806(request.query_params)
    if err and edit_id and 0 < edit_id <= 2**63 - 1 and section in KINDS762:
        filters.update(edit_kind=section, edit_id=edit_id)
    if err or msg:
        filters["err" if err else "msg"] = err or msg
    query = urlencode(filters)
    return RedirectResponse("/progress" + ("?" + query if query else "") + "#" + section,
                            status_code=303)


def _number762(raw, low, high, *, integer=False):
    if str(raw or "").strip() == "":
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Enter a valid numeric value.") from None
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"Measurement must be between {low} and {high}.")
    if integer and not value.is_integer():
        raise ValueError("This measurement must be a whole number.")
    return int(value) if integer else value


def _day762(raw):
    try:
        day = date.fromisoformat(str(raw or ""))
    except ValueError:
        raise ValueError("Enter a valid measurement date.") from None
    if not date(1900, 1, 1) <= day <= date.today():
        raise ValueError("Measurement date must not be in the future.")
    return day


def _cm762(value, unit):
    return value * 2.54 if unit == "in" else value


def _display762(value, unit):
    if value is None:
        return None
    return value / 2.54 if unit == "in" else value


def _settings762(db):
    return db.get(ProgressSettings762, 1)


def _frequencies762(settings):
    values = dict(FREQUENCIES762)
    if settings:
        try:
            incoming = json.loads(settings.frequencies_json or "{}")
            if isinstance(incoming, dict):
                for key in values:
                    if type(incoming.get(key)) is int and 0 <= incoming[key] <= 365:
                        values[key] = incoming[key]
        except (TypeError, ValueError):
            pass
    return values


def _nutrition762(engine, since, today):
    """Optional, reported-only aggregate; incomplete days stay incomplete."""
    try:
        with engine.connect() as conn:
            tables = {row[0] for row in conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name IN ('tracker_food_entries','tracker_food_products','tracker_food_targets')"
            )).all()}
            if not {"tracker_food_entries", "tracker_food_products"}.issubset(tables):
                return [], None
            rows = conn.execute(text("""
                SELECT e.eaten_on, e.servings, p.nutrients
                FROM tracker_food_entries e
                JOIN tracker_food_products p ON p.id=e.product_id
                WHERE e.eaten_on BETWEEN :start AND :end
                ORDER BY e.eaten_on, e.id
            """), {"start": since.isoformat(), "end": today.isoformat()}).all()
            target = conn.execute(text(
                "SELECT value FROM tracker_food_targets WHERE nutrient='proteins'"
            )).scalar_one_or_none() if "tracker_food_targets" in tables else None
    except (ValueError, TypeError, KeyError):
        return [], None
    daily = {}
    for stamp, servings, packed in rows:
        try:
            nutrients = json.loads(packed)
            amount = float(servings)
            if not isinstance(nutrients, dict) or not math.isfinite(amount) or amount <= 0:
                continue
        except (ValueError, TypeError):
            continue
        entry = daily.setdefault(str(stamp), {"count": 0, "protein": 0.0, "energy": 0.0,
                                              "protein_coverage": 0, "energy_coverage": 0})
        entry["count"] += 1
        for key, key2 in (("proteins", "protein"), ("energy", "energy")):
            value = nutrients.get(key)
            if value is not None:
                try:
                    value = float(value)
                    if not math.isfinite(value) or value < 0:
                        continue
                except (TypeError, ValueError):
                    continue
                entry[key2] += value * amount
                entry[key2 + "_coverage"] += 1
    for stamp, item in daily.items():
        item["date"] = date.fromisoformat(stamp)
        item["complete_protein"] = item["protein_coverage"] == item["count"]
        item["complete_energy"] = item["energy_coverage"] == item["count"]
    return sorted(daily.values(), key=lambda x: x["date"]), (
        float(target) if target is not None and math.isfinite(float(target)) and float(target) > 0 else None
    )


def _checklist762(today, frequencies, weights, measures, compositions, function_rows, markers, sessions, labs_rows):
    latest = {
        "weight": weights[-1][0] if weights else None,
        "waist": max((r.measured_on for r in measures if r.waist_navel is not None), default=None),
        "other": max((r.measured_on for r in measures if any(getattr(r, key) is not None
            for key in MEASURES762 if key != "waist_navel")), default=None),
        "strength": max((s.started_at.date() for s in sessions), default=None),
        "bia": max((r.measured_on for r in compositions if r.method == "BIA"), default=None),
        "photos": max((r.measured_on for r in markers if r.category == "photo"), default=None),
        "dexa": max((r.measured_on for r in compositions if r.method == "DEXA"), default=None),
        "labs": max((r.drawn_on for r in labs_rows), default=None),
    }
    names = {"weight": "Body weight", "waist": "Waist · navel", "other": "Other measurements",
             "strength": "Strength (automatic)", "bia": "BIA (optional)",
             "photos": "Progress photo date", "dexa": "DEXA (optional)", "labs": "Labs"}
    result = []
    for key, cadence in frequencies.items():
        if cadence == 0:
            continue
        recent = latest[key]
        result.append({"key": key, "label": names[key], "every": cadence, "last": recent,
                       "due": recent is None or (today - recent).days >= cadence})
    return result


@router.get("/progress")
def progress762(
    request: Request,
    days: int = 90, machine: int | None = None, reps: int | None = None,
    analyte: str = "", markers: int = 0, edit_kind: str = "", edit_id: int = 0,
    db: Session = Depends(get_scoped_db390),
    food_engine=Depends(get_food_read_engine406),
):
    days = days if days in RANGES762 else 90
    today = date.today()
    now = datetime.now()
    since = today - timedelta(days=days - 1) if days else date(1900, 1, 1)
    chart_start = datetime.combine(since, time.min) if days else None
    chart_range = (chart_start, now) if chart_start else None

    settings = _settings762(db)
    tape_unit = settings.measurement_unit if settings and settings.measurement_unit in ("in", "cm") else "in"
    vitals_all = list(db.scalars(select(VitalReading).order_by(
        VitalReading.measured_at, VitalReading.id)))
    observed = daily_weights762(vitals_all)
    weight = weight_report762(observed, today,
        settings.starting_weight_kg if settings else None,
        settings.goal_weight_kg if settings else None)
    weight_convert = lambda kg: metrics.weight_from_kg(kg, config.WEIGHT_UNIT)
    display_weight = {k: weight_convert(weight[k]) if weight[k] is not None else None
                      for k in ("latest", "first", "lost", "remaining", "avg7", "avg28", "d7", "d28")}
    visible_weight = [(datetime.combine(day, time(12)), weight_convert(value))
                      for day, value in observed if day >= since]
    rolling7 = [(t, weight_convert(v)) for t, v, count in moving762(observed, 7, min_samples=3)
                if t.date() >= since]
    rolling28 = [(t, weight_convert(v)) for t, v, count in moving762(observed, 28, min_samples=7)
                 if t.date() >= since]

    measure_all = list(db.scalars(select(ProgressMeasure762).order_by(
        ProgressMeasure762.measured_on, ProgressMeasure762.id)))
    comp_all = list(db.scalars(select(ProgressComposition762).order_by(
        ProgressComposition762.measured_on, ProgressComposition762.id)))
    function_all = list(db.scalars(select(ProgressFunction762).order_by(
        ProgressFunction762.measured_on, ProgressFunction762.id)))
    marker_all = list(db.scalars(select(ProgressMarker762).order_by(
        ProgressMarker762.measured_on, ProgressMarker762.id)))
    visible_tape = [r for r in measure_all if r.measured_on >= since]
    visible_comp = [r for r in comp_all if r.measured_on >= since]
    visible_function = [r for r in function_all if r.measured_on >= since]
    visible_marker = [r for r in marker_all if r.measured_on >= since]
    waist_details = metric_change_details762(visible_tape, "waist_navel")
    waist_delta = waist_details["delta"] if waist_details else None
    latest_body_fat = next((r for r in reversed(comp_all)
        if r.body_fat_pct is not None), None)
    latest_waist = next((r.waist_navel for r in reversed(measure_all) if r.waist_navel is not None), None)
    waist_height = latest_waist / settings.height_cm if (
        latest_waist is not None and settings and settings.height_cm) else None

    available_equipment = list(db.scalars(select(WorkoutEquipment654).order_by(
        WorkoutEquipment654.name, WorkoutEquipment654.id)))
    workout_records = list(db.execute(select(WorkoutSession654, WorkoutSet654, WorkoutSetType667)
        .join(WorkoutSet654, WorkoutSet654.session_id == WorkoutSession654.id)
        .outerjoin(WorkoutSetType667, WorkoutSetType667.set_id == WorkoutSet654.id)
        .where(WorkoutSession654.completed_at.is_not(None),
               WorkoutSession654.started_at >= datetime.combine(since, time.min))
        .order_by(WorkoutSession654.started_at, WorkoutSet654.id)))
    working_rows = [(s.started_at.date(), x.equipment_id, x.reps, x.weight_lb)
                    for s, x, kind in workout_records
                    if kind is None or kind.set_type == "working"]
    sessions = {s.id: s for s, x, kind in workout_records}
    recent_machine = working_rows[-1][1] if working_rows else None
    selected_machine = machine if any(e.id == machine for e in available_equipment) else recent_machine
    if selected_machine is None and available_equipment:
        selected_machine = available_equipment[0].id
    rep_counts = Counter(r for d, equipment_id, r, w in working_rows
                         if equipment_id == selected_machine)
    selected_reps = reps if reps is not None and 1 <= reps <= 200 else (
        rep_counts.most_common(1)[0][0] if rep_counts else 8)
    strength_pairs, strength_status = strength_trend762(
        working_rows, selected_machine, selected_reps)
    strength_chart = charts.line_chart([charts.Series(
        f"{selected_reps}-rep matched set", [(datetime.combine(d, time(12)), w)
        for d, w in strength_pairs])], unit=" lb", x_range=chart_range)
    session_dates = sorted({s.started_at.date() for s in sessions.values()})
    session7 = len({sid for sid, s in sessions.items() if s.started_at.date() >= today-timedelta(days=6)})
    session28 = len({sid for sid, s in sessions.items() if s.started_at.date() >= today-timedelta(days=27)})
    # Frequency chart uses only completed sessions with a recorded set.
    freq_start = since if days else (session_dates[0] if session_dates else today)
    week_buckets = Counter((s.started_at.date() - freq_start).days // 7 for s in sessions.values())
    frequency_chart = charts.line_chart([charts.Series("Completed sessions / 7-day block",
        [(datetime.combine(freq_start + timedelta(days=i*7+3), time(12)), float(v))
         for i, v in sorted(week_buckets.items())])], x_range=chart_range)

    daily_food, protein_target = _nutrition762(food_engine, since, today)
    complete_protein = [r for r in daily_food if r["complete_protein"]]
    complete_kcal = [r for r in daily_food if r["complete_energy"]]
    protein_chart = charts.line_chart([charts.Series("Recorded protein",
        [(datetime.combine(x["date"], time(12)), x["protein"]) for x in complete_protein]),
        charts.Series("Personal target",
        [(datetime.combine(x["date"], time(12)), protein_target) for x in complete_protein], "s2")
        if protein_target is not None else charts.Series("No target entered", [])],
        unit=" g", x_range=chart_range)
    protein_avg = (sum(x["protein"] for x in complete_protein) / len(complete_protein)
                   if complete_protein else None)
    protein_per_kg = protein_avg / weight["latest"] if (
        protein_avg is not None and weight["latest"] is not None and weight["latest"] > 0) else None

    current_vitals = [r for r in vitals_all if r.measured_at.date() >= since]
    bp_chart = charts.line_chart([
        charts.Series("Systolic", [(r.measured_at, r.systolic) for r in current_vitals if r.systolic is not None]),
        charts.Series("Diastolic", [(r.measured_at, r.diastolic) for r in current_vitals if r.diastolic is not None], "s2")],
        unit=" mmHg", x_range=chart_range)
    heart_chart = charts.line_chart([charts.Series("Pulse", [
        (r.measured_at, r.pulse_bpm) for r in current_vitals if r.pulse_bpm is not None])],
        unit=" bpm", x_range=chart_range)

    labs_rows = list(db.scalars(select(LabReport).order_by(LabReport.drawn_on)))
    analyte_names = {labs.analyte_key(r.analyte): r.analyte for r in
                     db.scalars(select(LabResult)) if r.analyte}
    analyte_choices = sorted(analyte_names.items(), key=lambda kv: kv[1].casefold())
    chosen_analyte = analyte if analyte in analyte_names else (
        analyte_choices[0][0] if analyte_choices else "")
    lab_chart = None
    lab_note = None
    if chosen_analyte:
        joined = db.execute(select(LabResult, LabReport)
            .join(LabReport, LabResult.report_id == LabReport.id)
            .where(LabReport.drawn_on >= since)
            .order_by(LabReport.drawn_on)).all()
        comparable = [(r, report) for r, report in joined
                      if labs.analyte_key(r.analyte) == chosen_analyte]
        if comparable:
            serie = labs.build_series(analyte_names[chosen_analyte], [
                labs.Point(report.drawn_on, r.value, r.unit, r.ref_low, r.ref_high)
                for r, report in comparable])
            lab_chart = charts.line_chart([charts.Series(analyte_names[chosen_analyte],
                serie.points)], unit=f" {serie.unit}", x_range=chart_range)
            lab_note = f"{len(serie.points)} comparable result(s); {serie.skipped} incompatible units omitted"

    events = [charts.Event(datetime.combine(r.measured_on, time(12)), "marker",
                           r.label, mark="M") for r in visible_marker] if markers else []
    weight_chart = charts.line_chart([
        charts.Series("Recorded weight", visible_weight),
        charts.Series("7-day average", rolling7, "s2"),
        charts.Series("28-day average", rolling28, "s3")],
        unit=f" {config.WEIGHT_UNIT}", x_range=chart_range, events=events)
    waist_chart = charts.line_chart([charts.Series("Waist at navel", [
        (datetime.combine(r.measured_on, time(12)), _display762(r.waist_navel, tape_unit))
        for r in visible_tape if r.waist_navel is not None])],
        unit=f" {tape_unit}", x_range=chart_range, events=events)
    composition_charts = {}
    for method in ("BIA", "DEXA"):
        subset = [r for r in visible_comp if r.method == method]
        composition_charts[method] = charts.line_chart([
            charts.Series("Body-fat estimate (%)", [
                (datetime.combine(r.measured_on, time(12)), r.body_fat_pct)
                for r in subset if r.body_fat_pct is not None])],
            unit=" %", x_range=chart_range)
    frequencies = _frequencies762(settings)
    checklist = _checklist762(today, frequencies, observed, measure_all,
        comp_all, function_all, marker_all, list(sessions.values()), labs_rows)
    summary = interpret762(weight, waist_delta, strength_status)
    progress_query = urlencode(_progress_filters806({
        "days": days, "markers": int(bool(markers)), "machine": selected_machine,
        "reps": selected_reps, "analyte": chosen_analyte,
    }))
    edit_model = KINDS762.get(edit_kind)
    editing = db.get(edit_model, edit_id) if edit_model and 0 < edit_id <= 2**63 - 1 else None
    return render(request, "progress762.html",
        days=days, ranges=RANGES762, markers=bool(markers), now=today, settings=settings,
        progress_query=progress_query,
        unit=config.WEIGHT_UNIT, tape_unit=tape_unit, display_weight=display_weight,
        weight=weight, weight_chart=weight_chart, waist_chart=waist_chart,
        waist_delta=_display762(waist_delta, tape_unit), waist_details=waist_details,
        latest_body_fat=latest_body_fat,
        latest_waist=_display762(latest_waist, tape_unit), waist_height=waist_height,
        measure_fields=MEASURES762, composition_fields=COMPOSITION762,
        measures=list(reversed(visible_tape))[:12], compositions=list(reversed(visible_comp))[:12],
        functional=list(reversed(visible_function))[:12], intervention=list(reversed(visible_marker))[:12],
        composition_charts=composition_charts, strength_chart=strength_chart,
        strength_status=strength_status, strength_count=len(strength_pairs),
        equipment=available_equipment, selected_machine=selected_machine, selected_reps=selected_reps,
        sessions7=session7, sessions28=session28, frequency_chart=frequency_chart,
        working_count=len(working_rows), protein_chart=protein_chart,
        protein_target=protein_target, protein_avg=protein_avg,
        protein_per_kg=protein_per_kg, food_days=len(daily_food),
        complete_food_days=len(complete_protein), complete_kcal_days=len(complete_kcal),
        bp_chart=bp_chart, heart_chart=heart_chart, lab_chart=lab_chart,
        analyte_choices=analyte_choices, chosen_analyte=chosen_analyte, lab_note=lab_note,
        frequencies=frequencies, checklist=checklist, summary=summary,
        editing=editing, edit_kind=edit_kind if editing else "")


@router.post("/progress/settings")
async def save_settings762(request: Request, db: Session = Depends(get_scoped_db390)):
    form = await request.form()
    try:
        height_unit = str(form.get("height_unit", "in"))
        weight_unit = str(form.get("weight_unit", "lb"))
        tape_unit = str(form.get("measurement_unit", "in"))
        if height_unit not in ("in", "cm") or tape_unit not in ("in", "cm") or weight_unit not in ("lb", "kg"):
            raise ValueError("Select a supported unit.")
        height = _number762(form.get("height"), 20, 280)
        if height is not None:
            height = _cm762(height, height_unit)
            if not 100 <= height <= 250:
                raise ValueError("Height is outside the supported range.")
        start = _number762(form.get("starting_weight"), 20, 1100)
        goal = _number762(form.get("goal_weight"), 20, 1100)
        if start is not None: start = metrics.weight_to_kg(start, weight_unit)
        if goal is not None: goal = metrics.weight_to_kg(goal, weight_unit)
        if start is not None and goal is not None and goal >= start:
            raise ValueError("Goal must be below starting weight.")
        frequencies = {}
        for key in FREQUENCIES762:
            value = _number762(form.get("freq_" + key), 0, 365, integer=True)
            frequencies[key] = 0 if value is None else value
    except ValueError as exc:
        return _progress_redirect806(request, "progress-settings", err=str(exc))
    setting = _settings762(db)
    if setting is None:
        setting = ProgressSettings762(id=1)
        db.add(setting)
    setting.height_cm = height
    setting.starting_weight_kg = start
    setting.goal_weight_kg = goal
    setting.measurement_unit = tape_unit
    setting.frequencies_json = json.dumps(frequencies, sort_keys=True)
    db.commit()
    return _progress_redirect806(request, "progress-settings", msg="Progress preferences saved.")


@router.post("/progress/{kind}/save")
async def save_progress762(kind: str, request: Request,
                           db: Session = Depends(get_scoped_db390)):
    model = KINDS762.get(kind)
    if model is None:
        raise HTTPException(404)
    form = await request.form()
    rid = 0
    try:
        rid = int(form.get("record_id") or 0)
        if not 0 <= rid <= 2**63 - 1:
            raise ValueError("Invalid record ID.")
        item = db.get(model, rid) if rid else model()
        if item is None:
            raise HTTPException(404, "Measurement not found.")
        item.measured_on = _day762(form.get("measured_on"))
        if kind == "measure":
            unit = str(form.get("unit", "in"))
            if unit not in ("in", "cm"):
                raise ValueError("Select inches or centimeters.")
            count = 0
            for key, (label, low, high) in MEASURES762.items():
                value = _number762(form.get(key), low / (2.54 if unit == "in" else 1),
                                   high / (2.54 if unit == "in" else 1))
                setattr(item, key, _cm762(value, unit) if value is not None else None)
                count += value is not None
            if not count:
                raise ValueError("Enter at least one circumference.")
            item.notes = str(form.get("notes", "")).strip()[:2000]
        elif kind == "composition":
            method = str(form.get("method", ""))
            if method not in ("BIA", "DEXA", "other"):
                raise ValueError("Choose a measurement method.")
            unit = str(form.get("mass_unit", "lb"))
            if unit not in ("lb", "kg"):
                raise ValueError("Choose lb or kg.")
            count = 0
            for key, (label, low, high) in COMPOSITION762.items():
                max_value = high * (2.2046226218 if unit == "lb" and key.endswith("_kg") else 1)
                value = _number762(form.get(key), low, max_value)
                if key.endswith("_kg") and value is not None:
                    value = metrics.weight_to_kg(value, unit)
                setattr(item, key, value)
                count += value is not None
            if not count:
                raise ValueError("Enter at least one body-composition estimate.")
            item.method = method
            item.device = str(form.get("device", "")).strip()[:160]
            item.conditions = str(form.get("conditions", "")).strip()[:2000]
            item.segmental_notes = str(form.get("segmental_notes", "")).strip()[:2000]
        elif kind == "function":
            count = 0
            for key, (low, high) in FUNCTION_FIELDS762.items():
                value = _number762(form.get(key), low, high, integer=key in INTEGER_FIELDS762)
                setattr(item, key, value)
                count += value is not None
            unit = str(form.get("distance_unit", "mi"))
            if unit not in ("mi", "km"):
                raise ValueError("Choose mi or km.")
            if item.walking_distance_km is not None and unit == "mi":
                item.walking_distance_km *= 1.609344
            item.notes = str(form.get("notes", "")).strip()[:2000]
            if not count and not item.notes:
                raise ValueError("Enter a functional observation or note.")
        else:
            category = str(form.get("category", "other"))
            label = str(form.get("label", "")).strip()
            if category not in MARKER_KINDS762 or not 1 <= len(label) <= 160:
                raise ValueError("Select a category and enter a short event label.")
            item.category = category
            item.label = label
            item.notes = str(form.get("notes", "")).strip()[:2000]
    except (ValueError, OverflowError) as exc:
        db.rollback()
        return _progress_redirect806(request, kind, err=str(exc), edit_id=rid if rid > 0 else None)
    if not rid:
        db.add(item)
    db.commit()
    return _progress_redirect806(request, kind, msg="Progress record saved.")


@router.post("/progress/{kind}/{rid}/delete")
async def delete_progress762(kind: str, rid: int, request: Request,
                             db: Session = Depends(get_scoped_db390)):
    model = KINDS762.get(kind)
    if model is None:
        raise HTTPException(404)
    item = db.get(model, rid)
    if item is None:
        raise HTTPException(404, "Measurement not found.")
    db.delete(item)
    db.commit()
    return _progress_redirect806(request, kind, msg="Progress record deleted.")
