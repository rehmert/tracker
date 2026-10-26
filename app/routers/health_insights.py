"""Read-only cross-domain health trend dashboard; no clinical inference."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import charts, config, labs, metrics, services
from ..db import get_db
from ..models import LabReport, LabResult, VitalReading
from ..templating import render

router = APIRouter()
RANGES = {30: "30 days", 90: "90 days", 365: "1 year", 1095: "3 years", 3650: "All"}


def _lab_choices(db: Session):
    pairs = db.execute(select(LabResult.analyte).distinct()).all()
    names = {}
    for (name,) in pairs:
        names.setdefault(labs.analyte_key(name), name)
    return sorted(names.items(), key=lambda pair: pair[1].casefold())


@router.get('/health-insights')
def health_insights(request: Request, days: int = 90, analyte: str = '', events: int = 1,
                    db: Session = Depends(get_db)):
    days = days if days in RANGES else 90
    now = datetime.now()
    since = now - timedelta(days=days)
    rows = list(db.scalars(select(VitalReading).where(VitalReading.measured_at >= since)
                           .order_by(VitalReading.measured_at)))
    choices = _lab_choices(db)
    keys = {key for key, _ in choices}
    selected = analyte if analyte in keys else (choices[0][0] if choices else '')
    dose_events = services.events_between(db, since, now) if events else []
    x_range = (since, now)

    def points(attribute, convert=lambda value: value):
        return [(r.measured_at, convert(getattr(r, attribute))) for r in rows
                if getattr(r, attribute) is not None]

    weight = points('weight_kg', lambda v: metrics.weight_from_kg(v, config.WEIGHT_UNIT))
    systolic = points('systolic')
    diastolic = points('diastolic')
    pulse = points('pulse_bpm')

    lab_chart = None
    lab_info = None
    if selected:
        results = db.execute(select(LabResult, LabReport).join(LabReport)
                             .where(LabReport.drawn_on >= since.date())).all()
        selected_results = [(r, report) for r, report in results
                            if labs.analyte_key(r.analyte) == selected]
        if selected_results:
            name = next((label for key, label in choices if key == selected), selected)
            series = labs.build_series(name, [labs.Point(report.drawn_on, r.value, r.unit,
                                                         r.ref_low, r.ref_high)
                                              for r, report in selected_results])
            lab_chart = charts.line_chart([charts.Series(name, series.points)],
                                          unit=f' {series.unit}', x_range=x_range,
                                          events=dose_events, band=series.band,
                                          band_label='Reference interval printed on report')
            lab_info = {'name': name, 'count': len(series.points), 'skipped': series.skipped,
                        'unit': series.unit}

    return render(request, 'health_insights.html', days=days, ranges=RANGES,
                  choices=choices, selected=selected, events_on=bool(events),
                  weight_unit=config.WEIGHT_UNIT, lab_chart=lab_chart, lab_info=lab_info,
                  weight_count=len(weight), bp_count=len(systolic), pulse_count=len(pulse),
                  weight_chart=charts.line_chart([charts.Series('Weight', weight)],
                                                 unit=f' {config.WEIGHT_UNIT}', x_range=x_range,
                                                 events=dose_events),
                  bp_chart=charts.line_chart([charts.Series('Systolic', systolic),
                                              charts.Series('Diastolic', diastolic, 's2')],
                                             unit=' mmHg', x_range=x_range, events=dose_events),
                  pulse_chart=charts.line_chart([charts.Series('Pulse', pulse)],
                                                unit=' bpm', x_range=x_range, events=dose_events))
