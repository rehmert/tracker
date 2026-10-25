from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import services, units as U
from ..db import get_db
from ..models import VIAL_STATUSES, DoseLog, Vial, Compound, Supply, SupplyUsage, Coa
from ..templating import render

router = APIRouter()


def _get(db: Session, vid: int) -> Vial:
    v = db.get(Vial, vid)
    if v is None:
        raise HTTPException(404, "Vial not found")
    return v


@router.get("/vials")
def vials_page(request: Request, status: str = "active", compound_id: str | None = None, db: Session = Depends(get_db)):
    # Convert compound_id to integer, treating empty strings as None
    compound_id = int(compound_id) if compound_id and compound_id.isdigit() else None

    vials = list(db.scalars(select(Vial).order_by(Vial.id.desc())))

    if compound_id is not None:
        vials = [v for v in vials if v.compound_id == compound_id]
    if status == "active":
        vials = [v for v in vials if v.status in ("sealed", "in_use")]
    elif status in VIAL_STATUSES:
        vials = [v for v in vials if v.status == status]
    return render(request, "vials.html", vials=vials, views=services.vial_views(db, vials),
                  status=status, statuses=VIAL_STATUSES, compound_id=compound_id, compounds=list(db.scalars(select(Compound).order_by(Compound.name))))


@router.get("/vials/{vid}")
def vial_detail(vid: int, request: Request, db: Session = Depends(get_db)):
    v = _get(db, vid)
    vd = services.vial_views(db, [v])[v.id]
    label_base, _ = U.to_base(v.content_value, v.content_unit)
    coa_variance = None
    for c in ([v.coa] if v.coa else []):
        if c.reported_content_value and c.reported_content_unit:
            coa_base, _ = U.to_base(c.reported_content_value, c.reported_content_unit)
            coa_variance = {"coa": c, "pct": 100 * (coa_base - label_base) / label_base}
            break
    doses = list(db.scalars(select(DoseLog).where(DoseLog.vial_id == vid)
                            .order_by(DoseLog.taken_at.desc())))
    rows = [{"dose": d, "cost": vd.cost_per_base * d.amount_base} for d in doses]
    return render(request, "vial_detail.html", v=v, vd=vd, label_base=label_base,
                  coa_variance=coa_variance, rows=rows, statuses=VIAL_STATUSES,
                  extras=vd.landed_cents - v.unit_price_cents, today=date.today().isoformat(),
                  bac_supplies=list(db.scalars(select(Supply).where(Supply.kind == "bac_water", Supply.remaining_qty > 0))),
                  all_coas=list(db.scalars(select(Coa).order_by(Coa.id.desc()))))


@router.post("/vials/{vid}")
def update_vial(vid: int, label: str = Form(""), lot: str = Form(""), status: str = Form(...),
                content_value: float = Form(...), content_unit: str = Form(...),
                volume_ml: str = Form(""), reconstituted_on: str = Form(""),
                expires_on: str = Form(""), unit_price: str = Form("0"),
                use_coa_content: str = Form(""), notes: str = Form(""), cap_color: str = Form(""),
                db: Session = Depends(get_db)):
    v = _get(db, vid)
    back = f"/vials/{vid}"
    try:
        old_dim = U.parse_unit(v.content_unit).dim
        unit = U.parse_unit(content_unit)
        if unit.dim != old_dim:
            raise ValueError("Mass vs IU can't be changed on an existing vial. "
                             "Delete it and add a new one.")
        if content_value <= 0:
            raise ValueError("Content must be above 0.")
        if status not in VIAL_STATUSES:
            raise ValueError("Unknown status.")
        vol = float(volume_ml) if volume_ml.strip() else None
        if vol is not None and vol <= 0:
            raise ValueError("Volume must be more than 0.")
        v.label, v.lot, v.status = label.strip(), lot.strip(), status
        v.content_value, v.content_unit, v.volume_ml = content_value, unit.name, vol
        v.reconstituted_on = services.parse_date(reconstituted_on)
        v.expires_on = services.parse_date(expires_on)
        v.unit_price_cents = services.to_cents(unit_price)
        v.use_coa_content = bool(use_coa_content)
        v.notes = notes.strip()
        v.cap_color = cap_color.strip()
    except ValueError as exc:
        db.rollback()
        return services.flash_redirect(back, err=str(exc))
    db.commit()
    return services.flash_redirect(back, msg="Vial updated.")


@router.post("/vials/{vid}/reconstitute")
def reconstitute(vid: int, volume_ml: float = Form(...), supply_id: str = Form(""), db: Session = Depends(get_db)):
    v = _get(db, vid)
    if volume_ml <= 0:
        return services.flash_redirect(f"/vials/{vid}", err="Volume must be more than 0.")
    if v.volume_ml is not None:
        return services.flash_redirect(f"/vials/{vid}", err="Already has a recorded volume. Edit vial details instead.")
    if supply_id:
        s = db.get(Supply, int(supply_id))
        if not s or s.kind != "bac_water" or s.remaining_qty + 1e-9 < volume_ml:
            return services.flash_redirect(f"/vials/{vid}", err="Insufficient BAC water inventory.")
        s.remaining_qty -= volume_ml
        db.add(SupplyUsage(supply_id=s.id, vial_id=vid, amount=volume_ml))
    v.volume_ml, v.reconstituted_on = volume_ml, date.today()
    if v.status == "sealed":
        v.status = "in_use"
    db.commit()
    return services.flash_redirect(f"/vials/{vid}", msg="Reconstitution recorded.")


@router.post("/vials/{vid}/delete")
def delete_vial(vid: int, db: Session = Depends(get_db)):
    v = _get(db, vid)
    if v.doses:
        return services.flash_redirect(
            f"/vials/{vid}", err="This vial has logged doses. Mark it discarded instead.")
    pid = v.purchase_id
    db.delete(v)
    db.commit()
    return services.flash_redirect(f"/purchases/{pid}" if pid else "/vials", msg="Vial deleted.")
