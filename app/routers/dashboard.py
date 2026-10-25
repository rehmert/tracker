from collections import defaultdict

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import services
from ..db import get_db
from ..models import DoseLog, Vial
from ..templating import render

router = APIRouter()


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    vials = list(db.scalars(select(Vial).order_by(Vial.id.desc())))
    views = services.vial_views(db, vials)
    active = [(v, views[v.id]) for v in vials if v.status in ("sealed", "in_use")]
    low = [(v, d) for v, d in active if v.status == "in_use" and d.pct_remaining < 20]

    by_compound: dict[str, float] = defaultdict(float)
    by_month: dict[str, float] = defaultdict(float)
    for v in vials:
        cents = views[v.id].landed_cents
        by_compound[v.compound.name] += cents
        when = v.purchase.purchased_on if v.purchase else v.created_at.date()
        by_month[when.strftime("%Y-%m")] += cents

    recent = []
    for dose in db.scalars(select(DoseLog).order_by(DoseLog.taken_at.desc()).limit(8)):
        vd = views[dose.vial_id]
        recent.append({"dose": dose, "vial": dose.vial, "vd": vd,
                       "cost": vd.cost_per_base * dose.amount_base})

    return render(
        request, "dashboard.html",
        active=active, low=low, recent=recent,
        total_spend=sum(d.landed_cents for d in views.values()),
        inventory_value=sum(d.remaining_value_cents for _, d in active),
        by_compound=sorted(by_compound.items(), key=lambda kv: -kv[1]),
        by_month=sorted(by_month.items(), reverse=True)[:6],
        no_coa=sum(1 for v in vials if v.status != "discarded" and not v.coas),
    )
