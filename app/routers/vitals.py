from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import charts, config, metrics, services
from ..db import get_db
from ..models import VitalReading
from ..templating import render

router = APIRouter()
RANGES = {30: "30 days", 90: "90 days", 365: "1 year", 3650: "All"}


def _opt(text: str, cast):
    text = (text or "").strip()
    if not text:
        return None
    try:
        return cast(text)
    except ValueError:
        raise ValueError(f"'{text}' is not a valid number.")


@router.get("/vitals")
def vitals_page(request: Request, days: int = 90, events: int = 1,
                db: Session = Depends(get_db)):
    days = days if days in RANGES else 90
    now = datetime.now()
    rows = list(db.scalars(select(VitalReading)
                           .where(VitalReading.measured_at >= now - timedelta(days=days))
                           .order_by(VitalReading.measured_at.desc(), VitalReading.id.desc())))
    unit = config.WEIGHT_UNIT

    def pts(getter):
        return [(r.measured_at, getter(r)) for r in rows if getter(r) is not None]

    w = pts(lambda r: metrics.weight_from_kg(r.weight_kg, unit))
    sy, di, hr = pts(lambda r: r.systolic), pts(lambda r: r.diastolic), pts(lambda r: r.pulse_bpm)

    # One shared time axis so dose / vial events line up across all three charts.
    x_start = (now - timedelta(days=days)) if days < 3650 else \
        min([r.measured_at for r in rows] or [now - timedelta(days=30)])
    x_range = (x_start, now)
    ev = services.events_between(db, x_start, now) if events else []
    markers = sorted((e for e in ev if e.kind == "marker"), key=lambda e: e.at, reverse=True)
    dose_counts: dict[str, int] = {}
    for e in ev:
        if e.kind == "dose":
            dose_counts[e.group] = dose_counts.get(e.group, 0) + 1
    return render(
        request, "vitals.html", rows=rows, unit=unit, days=days, ranges=RANGES,
        weight_unit_display=lambda kg: metrics.weight_from_kg(kg, unit),
        w=metrics.summarize(w, now), sy=metrics.summarize(sy, now),
        di=metrics.summarize(di, now), hr=metrics.summarize(hr, now),
        events_on=bool(events), markers=markers, dose_counts=dose_counts,
        weight_chart=charts.line_chart([charts.Series("Weight", w)], unit=f" {unit}",
                                       x_range=x_range, events=ev),
        bp_chart=charts.line_chart([charts.Series("Top number", sy, "s1", "{:.0f}"),
                                    charts.Series("Bottom number", di, "s2", "{:.0f}")],
                                   unit=" mmHg", x_range=x_range, events=ev),
        hr_chart=charts.line_chart([charts.Series("Pulse", hr, "s1", "{:.0f}")], unit=" bpm",
                                   x_range=x_range, events=ev),
        now=now.strftime("%Y-%m-%dT%H:%M"))


@router.post("/vitals")
def add_reading(measured_at: str = Form(""), weight: str = Form(""), weight_unit: str = Form("kg"),
                systolic: str = Form(""), diastolic: str = Form(""), pulse: str = Form(""),
                context: str = Form(""), notes: str = Form(""), db: Session = Depends(get_db)):
    try:
        w = _opt(weight, float)
        kg = metrics.weight_to_kg(w, weight_unit) if w is not None else None
        sy, di, hr = _opt(systolic, int), _opt(diastolic, int), _opt(pulse, int)
        when = services.parse_datetime(measured_at)
    except ValueError as exc:
        return services.flash_redirect("/vitals", err=str(exc))
    errors = metrics.validate(kg, sy, di, hr)
    if errors:
        return services.flash_redirect("/vitals", err=" ".join(errors))
    db.add(VitalReading(measured_at=when, weight_kg=kg, systolic=sy, diastolic=di, pulse_bpm=hr,
                        context=context.strip()[:80], notes=notes.strip()))
    db.commit()
    return services.flash_redirect("/vitals", msg="Reading saved.")



# Stage 34.87: Edit existing vital readings.

@router.get("/vitals/{rid}/edit")
def edit_reading_page(
    rid: int,
    request: Request,
    days: int = 90,
    events: int = 1,
    db: Session = Depends(get_db),
):
    reading = db.get(VitalReading, rid)
    if reading is None:
        raise HTTPException(404, "Reading not found")

    days = days if days in RANGES else 90
    unit = config.WEIGHT_UNIT

    weight = metrics.weight_from_kg(
        reading.weight_kg, unit
    )

    return render(
        request,
        "vitals_edit.html",
        reading=reading,
        unit=unit,
        weight=weight,
        days=days,
        events=1 if events else 0,
        measured_at=reading.measured_at.strftime(
            "%Y-%m-%dT%H:%M"
        ),
    )


@router.post("/vitals/{rid}/edit")
def update_reading(
    rid: int,
    measured_at: str = Form(""),
    weight: str = Form(""),
    weight_unit: str = Form("kg"),
    systolic: str = Form(""),
    diastolic: str = Form(""),
    pulse: str = Form(""),
    context: str = Form(""),
    notes: str = Form(""),
    days: int = Form(90),
    events: int = Form(1),
    db: Session = Depends(get_db),
):
    reading = db.get(VitalReading, rid)
    if reading is None:
        raise HTTPException(404, "Reading not found")

    days = days if days in RANGES else 90
    events = 1 if events else 0

    return_url = f"/vitals?days={days}&events={events}"
    edit_url = (
        f"/vitals/{rid}/edit?days={days}&events={events}"
    )

    try:
        if weight_unit not in ("kg", "lb"):
            raise ValueError("Invalid weight unit")

        w = _opt(weight, float)

        kg = (
            metrics.weight_to_kg(w, weight_unit)
            if w is not None
            else None
        )

        sy = _opt(systolic, int)
        di = _opt(diastolic, int)
        hr = _opt(pulse, int)
        when = services.parse_datetime(measured_at)

    except (ValueError, OverflowError) as exc:
        return services.flash_redirect(
            edit_url, err=str(exc)
        )

    errors = metrics.validate(kg, sy, di, hr)

    if errors:
        return services.flash_redirect(
            edit_url, err=" ".join(errors)
        )

    reading.measured_at = when
    reading.weight_kg = kg
    reading.systolic = sy
    reading.diastolic = di
    reading.pulse_bpm = hr
    reading.context = context.strip()[:80]
    reading.notes = notes.strip()

    db.commit()

    return services.flash_redirect(
        return_url,
        msg="Reading updated successfully.",
    )


@router.delete("/vitals/{rid}")
def delete_reading(rid: int, db: Session = Depends(get_db)):
    r = db.get(VitalReading, rid)
    if r is None:
        raise HTTPException(404, "Reading not found")
    db.delete(r)
    db.commit()
    return HTMLResponse("", headers={"HX-Refresh": "true"})   # charts and stats need a redraw
