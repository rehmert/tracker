from collections import defaultdict

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, metrics, services
from ..db import get_db
from ..models import DoseLog, Vial, VitalReading, Protocol
from ..templating import render
from ..units import to_base

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

    protocol_summaries = []

    for protocol in protocols:
        items = []
        for item in protocol.items:

            try:
                unit_factor, unit_dim = to_base(1, item.amount_unit)
                inventory_base = inventory_by_compound.get(item.compound_id, 0.0)

                remaining = (inventory_base / unit_factor if unit_factor else 0)
                doses_remaining = (remaining / item.amount_value if remaining is not None and item.amount_value > 0 else None)
            except (ValueError, TypeError):
                remaining = None

            items.append({
                "compound": item.compound.name,
                "amount": item.amount_value,
                "unit": item.amount_unit,
                "frequency": (
                    f"Every {item.freq_count:g} days"
                    if item.freq_period == "interval"
                    else f"{item.freq_count:g}x per {item.freq_period}"
                ),
                "remaining": remaining,
                "doses_remaining": doses_remaining,
        })

        protocol_summaries.append({"id": protocol.id, "name": protocol.name, "compounds": items, "doses_remaining": doses_remaining})

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
        no_coa=sum(1 for v in vials if v.status != "discarded" and v.coa_id is None),
        protocol_summaries=protocol_summaries,
    )
