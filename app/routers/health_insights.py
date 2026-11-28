"""Read-only cross-domain health trend dashboard; no clinical inference."""
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import charts, config, labs, metrics, services
from ..scoped_db390 import get_scoped_db390
from ..models import LabReport, LabResult, VitalReading, Compound, Blend, Protocol
from ..templating import render
from ..anatomical_sites807 import SITES, SITE_BY_CODE, valid_site
from ..wellness807 import METRICS, REACTIONS
from ..site_history807 import ROUTES
from ..health_analytics807 import effectiveness807, site_analytics807, weekly_report807
from ..wellness_models807 import WellnessDay807
from .progress762 import _nutrition762
from ..food_read_engine406 import get_food_read_engine406
from ..wellness807 import metric_summary, checked_day

router = APIRouter()
RANGES = {30: "30 days", 90: "90 days", 180: "6 months", 365: "1 year", 1095: "3 years", 3650: "All"}


def _lab_choices(db: Session):
    pairs = db.execute(select(LabResult.analyte).distinct()).all()
    names = {}
    for (name,) in pairs:
        names.setdefault(labs.analyte_key(name), name)
    return sorted(names.items(), key=lambda pair: pair[1].casefold())


@router.get('/health-insights')
def health_insights(request: Request, days: int = 90, analyte: str = '', events: int = 1,
                    db: Session = Depends(get_scoped_db390)):
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
                  **health_context807(db,request,now,choices),
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

def _int807(raw, *, maximum=2**63-1):
    try:
        n=int(raw)
        return n if 0<n<=maximum else None
    except (TypeError, ValueError):
        return None

def _range807(params, now, prefix, default=30, maximum=365):
    days=_int807(params.get(prefix+"_days"),maximum=maximum) or default
    end=now.date()
    start=end-timedelta(days=days-1)
    if params.get(prefix+"_start") or params.get(prefix+"_end"):
        try:
            start=checked_day(params.get(prefix+"_start"),end)
            end=checked_day(params.get(prefix+"_end"),end)
            if start>end or (end-start).days>=maximum:
                raise ValueError("Date range exceeds supported bounds.")
        except ValueError as exc:
            raise HTTPException(422,str(exc)) from None
    return datetime.combine(start,time.min),min(now,datetime.combine(end,time.max))

def _nutrition_for807(request,start,end):
    try:
        engine=get_food_read_engine406(request)
    except (HTTPException,PermissionError):
        return []
    return _nutrition762(engine,start.date(),end.date())[0]

def health_context807(db,request,now,choices):
    p=request.query_params
    start,end=_range807(p,now,"site")
    compound=_int807(p.get("site_compound"))
    blend=_int807(p.get("site_blend"))
    protocol=_int807(p.get("site_protocol"))
    route=p.get("site_route","all")
    route=route if route in ROUTES else None
    site=p.get("site","")
    site=site if site and valid_site(site) else None
    region=p.get("site_region","")
    region=region if region in ("abdomen","thigh","shoulder","gluteal") else None
    reaction=p.get("site_reaction","")
    reaction=reaction if reaction in REACTIONS else None
    severity=p.get("site_severity","")
    severity=int(severity) if severity in ("0","1","2","3","4","5") else None
    analytics=site_analytics807(db,start,end,compound=compound,blend=blend,protocol=protocol,
        route=route,site=site,region=region,reaction_type=reaction,severity=severity)
    compounds=list(db.scalars(select(Compound).order_by(Compound.name)))
    blends=list(db.scalars(select(Blend).order_by(Blend.label)))
    protocols=list(db.scalars(select(Protocol).order_by(Protocol.name)))
    effect_start,effect_end=_range807(p,now,"effect",default=30,maximum=90)
    effect_cid=_int807(p.get("effect_compound"))
    outcome_choices={key:value[0] for key,value in METRICS.items()}
    outcome_choices.update(weight="Weight",systolic="Systolic blood pressure",diastolic="Diastolic blood pressure",
                           pulse="Resting pulse",calories="Logged daily calories",protein="Logged daily protein",
                           symptom_severity="Reported symptom severity")
    outcome_choices.update({"lab:"+key:label+" (laboratory)" for key,label in choices})
    outcome=p.get("effect_metric","hunger")
    if outcome not in outcome_choices:
        outcome="hunger"
    nutrition=_nutrition_for807(request,effect_start,effect_end) if effect_cid else []
    effect=effectiveness807(db,effect_cid,outcome,effect_start,effect_end,nutrition) if effect_cid else None
    observed=effect["observed"] if effect else []
    paired=effect["paired"] if effect else []
    wellness_rows=list(db.scalars(select(WellnessDay807).where(WellnessDay807.day>=effect_start.date(),
                         WellnessDay807.day<=effect_end.date()).order_by(WellnessDay807.day)))
    week_start,week_end=_range807(p,now,"week",default=7,maximum=90)
    weekly=weekly_report807(db,week_start,week_end,_nutrition_for807(request,week_start,week_end)) if p.get("weekly")=="1" else None
    heat=p.get("site_heat","usage")
    if heat not in ("usage","recent","reaction"):
        heat="usage"
    return dict(site807=analytics,site807_stats={x["site"]:x for x in analytics["stats"]},
                site807_codes=SITES,site807_routes=ROUTES,site807_reactions=REACTIONS,
                site807_start=start.date(),site807_end=end.date(),site807_heat=heat,
                site807_filter=dict(compound=compound,blend=blend,protocol=protocol,route=route,site=site,region=region,reaction=reaction,severity=severity),
                wellness807_metrics=METRICS,wellness807_summary=metric_summary(wellness_rows),wellness807_count=len(wellness_rows),
                compounds807=compounds,blends807=blends,protocols807=protocols,
                effect807=effect,effect807_start=effect_start.date(),effect807_end=effect_end.date(),
                effect807_cid=effect_cid,effect807_metric=outcome,effect807_choices=outcome_choices,
                effect807_outcome_chart=charts.line_chart([charts.Series(outcome_choices[outcome],observed)],x_range=(effect_start,effect_end)),
                effect807_exposure_chart=charts.line_chart([charts.Series("Simulated exposure",[(r["at"],r["exposure"]) for r in paired])],unit=" mg-equivalent",x_range=(effect_start,effect_end)),
                week807=weekly,week807_start=week_start.date(),week807_end=week_end.date())

REPORT_SECTIONS807 = {
    "weight":"Weight and body composition", "nutrition":"Nutrition",
    "medication":"Medication, supplements and protocols", "wellness":"Wellness and symptoms",
    "reactions":"Injection site reactions and history", "cardio":"Blood pressure and pulse",
    "workouts":"Exercise", "labs":"Laboratory monitoring", "inventory":"Inventory"
}

@router.get("/health-insights/physician")
def physician807(request: Request, db: Session = Depends(get_scoped_db390)):
    now=datetime.now()
    start,end=_range807(request.query_params,now,"report",default=30,maximum=365)
    selected=set(request.query_params.getlist("section"))
    if not selected or not selected.issubset(REPORT_SECTIONS807):
        raise HTTPException(422,"Select at least one supported report section.")
    report=weekly_report807(db,start,end,_nutrition_for807(request,start,end) if "nutrition" in selected else [])
    return render(request,"physician807.html", report807=report, report807_start=start.date(),
                  report807_end=end.date(), report807_sections=REPORT_SECTIONS807,
                  report807_selected=selected,weight_unit=config.WEIGHT_UNIT,
                  weight_convert807=lambda kg:metrics.weight_from_kg(kg,config.WEIGHT_UNIT) if kg is not None else None,
                  wellness807_metrics=METRICS)
