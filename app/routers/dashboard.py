from collections import defaultdict
from datetime import datetime, timedelta
from math import isfinite

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import config, metrics, services, charts
from ..sparklines import sparkline
from ..daily_workspace790 import summary790
from ..scoped_db390 import get_scoped_db390
from ..workout_dashboard661 import workout_dashboard661
from ..dashboard_forecast752 import build_dashboard_forecasts752
from ..models import DoseLog, Vial, VitalReading, Protocol, ProtocolItem
from ..templating import render
from ..units import to_base, parse_unit, UnitError
from ..google_protocol_review783 import pending_links783

router = APIRouter()


@router.get("/")
def home(request: Request, workout_page: int | None = Query(default=None, ge=1, le=100000),
         db: Session = Depends(get_scoped_db390)):
    protocols = list(db.scalars(select(Protocol).where(Protocol.is_active.is_(True)).options(selectinload(Protocol.items).selectinload(ProtocolItem.compound)).order_by(Protocol.name)))
    inventory_by_compound = defaultdict(float)
    vials = list(db.scalars(select(Vial).options(selectinload(Vial.compound), selectinload(Vial.purchase)).order_by(Vial.id.desc())))
    views = services.vial_views(db, vials)
    active = [(v, views[v.id]) for v in vials if v.status in ("sealed", "in_use")]
    low = [(v, d) for v, d in active if v.status == "in_use" and d.pct_remaining < 20]
    by_compound: dict[str, float] = defaultdict(float)
    by_month: dict[str, float] = defaultdict(float)

    for vial, data in active:
        inventory_by_compound[vial.compound_id] += data.remaining_base

    # Base mass/IU and liquid volume must be calculated separately.
    # Derive physical volume per vial from the same canonical inventory view
    # used by the Inventory Forecast, without mixing different strengths.
    inventory_dims = defaultdict(lambda: defaultdict(float))
    strengths_by_compound = defaultdict(list)
    volume_without_concentration = set()
    today = datetime.now().date()
    for vial, data in active:
        if (vial.closed_on or
                (vial.expires_on and vial.expires_on < today) or
                (vial.beyond_use_on and vial.beyond_use_on < today)):
            continue
        inventory_dims[vial.compound_id][data.dim] += max(0.0, data.remaining_base)
        conc = data.conc_per_ml
        if (conc is None or not isfinite(conc) or conc <= 0
                or not isfinite(data.remaining_base)):
            volume_without_concentration.add(vial.compound_id)
            continue
        inventory_dims[vial.compound_id]["volume"] += max(0.0, data.remaining_base) / conc
        strengths_by_compound[vial.compound_id].append((data.dim, conc))

    for cid in set(strengths_by_compound) | volume_without_concentration:
        strengths = strengths_by_compound[cid]
        if cid in volume_without_concentration:
            quality = "partial" if strengths else "missing"
        elif any(
            dim != strengths[0][0] or
            abs(conc - strengths[0][1]) > max(conc, strengths[0][1]) * 1e-6
            for dim, conc in strengths[1:]
        ):
            quality = "mixed"
        else:
            quality = None
        if quality:
            inventory_dims[cid]["_volume_quality"] = quality

    protocol_summaries = []
    now = datetime.now()
    for protocol in protocols:
        # Dashboard cards show active protocols only; saved what-if plans
        # remain available in the full protocol manager.
        if not protocol.is_active:
            continue
        items = []
        for item in protocol.items:
            remaining = doses_remaining = None
            weekly = None
            try:
                u = parse_unit(item.amount_unit)
                by_dimension = inventory_dims[item.compound_id]
                inventory_base = by_dimension.get(u.dim, 0.0)
                volume_unknown = (u.dim == "volume" and
                                  bool(by_dimension.get("_volume_quality")))
                remaining = None if volume_unknown else inventory_base / u.factor
                if item.amount_value > 0 and isfinite(item.amount_value):
                    doses_remaining = (remaining / item.amount_value
                                       if remaining is not None else None)
                    if item.freq_count > 0 and isfinite(item.freq_count):
                        if item.freq_period == "interval":
                            weekly = item.amount_value * 7 / item.freq_count
                            frequency = f"Every {item.freq_count:g} days"
                        elif item.freq_period in ("day", "week", "month"):
                            period_days = {"day": 1, "week": 7, "month": 365.2425 / 12}[item.freq_period]
                            weekly = item.amount_value * item.freq_count * 7 / period_days
                            frequency = f"{item.freq_count:g}× per {item.freq_period}"
                        else:
                            frequency = "Unknown frequency"
                    else:
                        frequency = "Invalid frequency"
                else:
                    frequency = "Invalid amount"
            except (UnitError, ValueError, TypeError, ZeroDivisionError):
                frequency = "Unknown frequency"
            items.append({"compound": item.compound.name, "compound_id": item.compound_id,
                          "amount": item.amount_value, "unit": item.amount_unit,
                          "frequency": frequency, "remaining": remaining,
                          "doses_remaining": doses_remaining, "weekly": weekly})
        protocol_summaries.append({"id": protocol.id, "name": protocol.name,
                                   "is_active": protocol.is_active, "compounds": items})

    # Preserve a row for every active protocol item, including no-stock items.
    forecasts, low_forecasts, inventory_watch_forecasts = (
        build_dashboard_forecasts752(protocols, inventory_dims, now.date())
    )

    # Summary and charts are based only on recorded readings, not forecasts.
    vital_rows = list(db.scalars(select(VitalReading).where(
        VitalReading.measured_at >= now - timedelta(days=365)).order_by(VitalReading.measured_at)))
    def points(attr, transform=lambda x: x):
        return [(r.measured_at, transform(getattr(r, attr))) for r in vital_rows
                if getattr(r, attr) is not None]
    weight_points = points("weight_kg", lambda v: metrics.weight_from_kg(v, config.WEIGHT_UNIT))
    sys_points = points("systolic")
    dia_points = points("diastolic")
    pulse_points = points("pulse_bpm")
    vital_trends = {"weight": metrics.summarize(weight_points, now),
                    "systolic": metrics.summarize(sys_points, now),
                    "diastolic": metrics.summarize(dia_points, now),
                    "pulse": metrics.summarize(pulse_points, now)}
    metric_sparklines = {"weight": sparkline(weight_points, "Weight", now=now),
                         "bp": sparkline(sys_points, "Systolic blood pressure", now=now),
                         "pulse": sparkline(pulse_points, "Pulse", now=now)}
    def within(pts, days):
        return [(t, v) for t, v in pts if t >= now - timedelta(days=days)]
    charts_by_range = {}
    for days in (30, 90, 365):
        charts_by_range[days] = {
            "weight": charts.line_chart([charts.Series("Weight", within(weight_points, days))], unit=f" {config.WEIGHT_UNIT}"),
            "bp": charts.line_chart([charts.Series("Systolic", within(sys_points, days)),
                                      charts.Series("Diastolic", within(dia_points, days), "s2")], unit=" mmHg"),
            "pulse": charts.line_chart([charts.Series("Pulse", within(pulse_points, days))], unit=" bpm"),
        }

    for v in vials:
        cents = views[v.id].landed_cents
        by_compound[v.compound.name] += cents
        when = v.purchase.purchased_on if v.purchase else v.created_at.date()
        by_month[when.strftime("%Y-%m")] += cents

    # The Today card reads recorded administrations and active protocol schedules.
    # This query includes today's records for same-day reconciliation and the
    # preceding week for a compact recent-history view.
    today_date = now.date()
    recent_week = list(db.scalars(select(DoseLog).where(
        DoseLog.kind == 'dose',
        DoseLog.taken_at >= datetime.combine(today_date - timedelta(days=7), datetime.min.time()),
        DoseLog.taken_at < datetime.combine(today_date + timedelta(days=1), datetime.min.time())
    ).order_by(DoseLog.taken_at.desc()).limit(5)))
    today_summary = summary790(db, today_date)
    # Dashboard only: tomorrow through the following three calendar days.
    # Keep schedule_summary's seven-day projection for mobile and calendar.
    dashboard_upcoming = [
        (day, event) for day, event in today_summary['upcoming']
        if today_date < day <= today_date + timedelta(days=3)
    ]
    recent_administrations = recent_week[:5]

    recent = []
    for dose in db.scalars(select(DoseLog).order_by(DoseLog.taken_at.desc()).limit(8)):
        vd = views[dose.vial_id]
        recent.append({"dose": dose, "vial": dose.vial, "vd": vd,
                       "cost": vd.cost_per_base * dose.amount_base})

    def latest(column):
        return db.scalar(select(VitalReading).where(column.is_not(None))
                         .order_by(VitalReading.measured_at.desc(), VitalReading.id.desc()).limit(1))

    lw, lbp, lhr = latest(VitalReading.weight_kg), latest(VitalReading.systolic), \
        latest(VitalReading.pulse_bpm)
    vitals = {"weight": metrics.weight_from_kg(lw.weight_kg, config.WEIGHT_UNIT) if lw else None,
              "unit": config.WEIGHT_UNIT, "bp": lbp, "pulse": lhr.pulse_bpm if lhr else None}

    return render(
        request, "dashboard.html", vitals=vitals,
        active=active, low=low, recent=recent,
        total_spend=sum(d.landed_cents for d in views.values()),
        inventory_value=sum(d.remaining_value_cents for _, d in active),
        by_compound=sorted(by_compound.items(), key=lambda kv: -kv[1]),
        by_month=sorted(by_month.items(), reverse=True)[:6],
        no_coa=sum(1 for v in vials if v.status != "discarded" and not v.all_coas),
        protocol_summaries=protocol_summaries, forecasts=forecasts,
        low_forecasts=low_forecasts, inventory_watch_forecasts=inventory_watch_forecasts,
        vital_trends=vital_trends, charts_by_range=charts_by_range,
        metric_sparklines=metric_sparklines,
        today_summary=today_summary, dashboard_upcoming=dashboard_upcoming,
        recent_administrations=recent_administrations,
        now_date=today_date, google_pending_count=len(pending_links783(db)),
        workout_summary=workout_dashboard661(
            db, today_date, page=workout_page or 1,
            expanded=workout_page is not None,
        ),
    )
