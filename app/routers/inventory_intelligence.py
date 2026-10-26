"""Read-only inventory intelligence, derived from existing vial and dose records."""
from collections import defaultdict
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Vial, DoseLog
from ..services import vial_views
from ..templating import render
from ..forecasting import forecast_inventory

router = APIRouter()


def inventory_summary(db: Session, today: date | None = None):
    today = today or date.today()
    vials = list(db.scalars(select(Vial).order_by(Vial.id.desc())))
    views = vial_views(db, vials)
    logs = list(db.scalars(select(DoseLog)))
    by_vial = defaultdict(list)
    for log in logs:
        by_vial[log.vial_id].append(log)
    rows = []
    totals = {"active_vials": 0, "expiring_30": 0, "expired": 0, "low_stock": 0,
              "landed_cents": 0.0, "used_cents": 0.0, "wasted_cents": 0.0}
    for v in vials:
        vd = views[v.id]
        active = v.status in ("sealed", "in_use")
        days = (v.expires_on - today).days if v.expires_on else None
        expired = active and days is not None and days < 0
        expiring = active and days is not None and 0 <= days <= 30
        low = active and not expired and vd.pct_remaining < 20
        used = sum(d.amount_base for d in by_vial[v.id] if d.kind == "dose")
        wasted = sum(d.amount_base for d in by_vial[v.id] if d.kind == "waste")
        used_cost = used * vd.cost_per_base
        wasted_cost = wasted * vd.cost_per_base
        if active:
            totals["active_vials"] += 1
            totals["landed_cents"] += vd.landed_cents
        totals["expiring_30"] += int(expiring)
        totals["expired"] += int(expired)
        totals["low_stock"] += int(low)
        totals["used_cents"] += used_cost
        totals["wasted_cents"] += wasted_cost
        rows.append({"vial": v, "view": vd, "days": days, "expired": expired,
                     "expiring": expiring, "low": low, "used": used, "wasted": wasted,
                     "used_cost": used_cost, "wasted_cost": wasted_cost,
                     "dose_count": sum(d.kind == "dose" for d in by_vial[v.id]),
                     "status_label": "Expired" if expired else "Expiring soon" if expiring else "Low stock" if low else v.status.replace("_", " ").title()})
    rows.sort(key=lambda r: (not r["expired"], not r["expiring"], not r["low"], r["vial"].compound.name.lower(), r["vial"].id))
    return rows, totals


@router.get("/inventory-intelligence")
def inventory_intelligence(request: Request, days: int = Query(90, ge=30, le=180), db: Session = Depends(get_db)):
    rows, totals = inventory_summary(db)
    window = days if days in (30, 90, 180) else 90
    forecasts, supply_forecasts = forecast_inventory(db, window_days=window)
    return render(request, "inventory_intelligence.html", rows=rows, totals=totals, forecasts=forecasts, supply_forecasts=supply_forecasts, forecast_days=window)


@router.get("/inventory-alerts")
def inventory_alerts(request: Request, days: int = Query(90, ge=30, le=180), horizon: int = Query(21, ge=1, le=365), db: Session = Depends(get_db)):
    from ..inventory_alerts import collect_inventory_alerts
    window = days if days in (30, 90, 180) else 90
    alerts = collect_inventory_alerts(db, window_days=window, horizon_days=horizon)
    return render(request, "inventory_alerts.html", alerts=alerts, forecast_days=window, horizon=horizon)
