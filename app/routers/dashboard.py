from collections import defaultdict
from datetime import datetime, timedelta
from math import isfinite

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, metrics, services, charts
from ..sparklines import sparkline
from ..today import schedule_summary
from ..projection_exclusions import exclusions_for
from ..db import get_db
from ..models import DoseLog, Vial, VitalReading, Protocol
from ..templating import render
from ..units import to_base, parse_unit, UnitError

router = APIRouter()


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    protocols = list(db.scalars(select(Protocol).order_by(Protocol.name)))
    inventory_by_compound = defaultdict(float)
    vials = list(db.scalars(select(Vial).order_by(Vial.id.desc())))
    views = services.vial_views(db, vials)
    active = [(v, views[v.id]) for v in vials if v.status in ("sealed", "in_use")]
    low = [(v, d) for v, d in active if v.status == "in_use" and d.pct_remaining < 20]
    by_compound: dict[str, float] = defaultdict(float)
    by_month: dict[str, float] = defaultdict(float)

    for vial, data in active:
        inventory_by_compound[vial.compound_id] += data.remaining_base

    # Each compound has its own unit dimension. Never mix mass, IU and volume.
    inventory_dims = defaultdict(lambda: defaultdict(float))
    for vial, data in active:
        if vial.expires_on and vial.expires_on < datetime.now().date():
            continue  # expired stock is excluded from usable supply forecasts
        inventory_dims[vial.compound_id][data.dim] += max(0.0, data.remaining_base)

    protocol_summaries = []
    weekly_use = defaultdict(float)
    now = datetime.now()
    for protocol in protocols:
        items = []
        for item in protocol.items:
            remaining = doses_remaining = None
            weekly = None
            try:
                u = parse_unit(item.amount_unit)
                inventory_base = inventory_dims[item.compound_id].get(u.dim, 0.0)
                remaining = inventory_base / u.factor
                if item.amount_value > 0 and isfinite(item.amount_value):
                    doses_remaining = remaining / item.amount_value
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
                        stage_day = (now.date() - protocol.start_date).days if protocol.start_date else None
                        stage_active = (stage_day is not None and stage_day >= 7 * (item.start_week - 1)
                                        and (item.end_week is None or stage_day < 7 * item.end_week)
                                        and (protocol.end_date is None or now.date() <= protocol.end_date))
                        if weekly is not None and protocol.is_active and stage_active:
                            weekly_use[(item.compound_id, u.dim)] += weekly * u.factor
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

    # Multiple active protocols can consume the same compound; combine their usage.
    forecasts = []
    for cid, dims in inventory_dims.items():
        for dim, amount in dims.items():
            rate = weekly_use.get((cid, dim), 0)
            if rate <= 0:
                continue
            days_left = 7 * amount / rate
            forecasts.append({"compound": next((v.compound.name for v in vials if v.compound_id == cid), str(cid)),
                              "remaining": amount, "unit": {"mass": "mcg", "iu": "IU", "volume": "mL"}.get(dim, dim),
                              "days_left": days_left,
                              "depletion": (now + timedelta(days=min(days_left, 365000))).date() if days_left >= 0 else None,
                              "low": days_left < 21})
    forecasts.sort(key=lambda x: x["days_left"])

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
    ).order_by(DoseLog.taken_at.desc())))
    today_summary = schedule_summary(protocols, recent_week, today_date,
                                     exclusions=exclusions_for(db, [item.id for p in protocols for item in p.items]))
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
        vital_trends=vital_trends, charts_by_range=charts_by_range,
        metric_sparklines=metric_sparklines,
        today_summary=today_summary, recent_administrations=recent_administrations,
        now_date=today_date,
    )
