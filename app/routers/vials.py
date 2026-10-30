from datetime import date, datetime
import math
import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import services, units as U
from ..db import get_db
from ..models import VIAL_STATUSES, DoseLog, Vial, Compound, Supply, SupplyUsage, Coa, PreparationEvent, PreparationSupply, ChangeAudit
from .. import manual_supplies
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


BULK_FIELDS = {
    "status": "choice",
    "lot": "text", "cap_color": "text", "storage_notes": "text", "notes": "text",
    "received_on": "date", "expires_on": "date", "beyond_use_on": "date",
    "first_punctured_on": "date", "first_dosed_on": "date", "closed_on": "date",
    "use_coa_content": "boolean",
}


@router.post("/vials/bulk")
async def bulk_update_vials(request: Request, db: Session = Depends(get_db)):
    """Apply only explicitly selected fields to explicitly checked vial IDs."""
    form = await request.form()
    try:
        ids = sorted({int(value) for value in form.getlist("vial_ids")})
    except (TypeError, ValueError):
        return services.flash_redirect("/vials", err="Invalid vial selection.")
    if not ids:
        return services.flash_redirect("/vials", err="Select at least one vial.")
    if len(ids) > 1000:
        return services.flash_redirect("/vials", err="Select at most 1,000 vials per update.")
    vials = list(db.scalars(select(Vial).where(Vial.id.in_(ids))))
    if len(vials) != len(ids):
        return services.flash_redirect("/vials", err="One or more selected vials no longer exist.")

    changes = {}
    try:
        for field, kind in BULK_FIELDS.items():
            mode = str(form.get(f"mode_{field}", "keep"))
            if mode not in ("keep", "set", "clear"):
                raise ValueError(f"Invalid action for {field}.")
            if mode == "keep":
                continue
            if mode == "clear":
                if kind in ("choice", "boolean"):
                    raise ValueError(f"{field} cannot be cleared.")
                changes[field] = None if kind == "date" else ""
                continue
            raw = str(form.get(f"value_{field}", "")).strip()
            if kind == "choice":
                if raw not in VIAL_STATUSES:
                    raise ValueError("Choose a valid status.")
                changes[field] = raw
            elif kind == "boolean":
                if raw not in ("yes", "no"):
                    raise ValueError("Choose Yes or No for COA content.")
                changes[field] = raw == "yes"
            elif kind == "date":
                if not raw:
                    raise ValueError(f"Enter a date for {field}, or select Clear.")
                changes[field] = services.parse_date(raw)
            else:
                if not raw:
                    raise ValueError(f"Enter a value for {field}, or select Clear.")
                changes[field] = raw
        if not changes:
            raise ValueError("Choose at least one field to update.")

        for vial in vials:
            proposed = {field: getattr(vial, field) for field in BULK_FIELDS}
            proposed.update(changes)
            if (proposed["received_on"] and proposed["first_punctured_on"]
                    and proposed["first_punctured_on"] < proposed["received_on"]):
                raise ValueError(f"Vial #{vial.id}: first puncture cannot precede receipt.")
            if (proposed["first_punctured_on"] and proposed["first_dosed_on"]
                    and proposed["first_dosed_on"] < proposed["first_punctured_on"]):
                raise ValueError(f"Vial #{vial.id}: first dose cannot precede first puncture.")
            if proposed["status"] == "sealed" and vial.doses:
                raise ValueError(f"Vial #{vial.id} has logged doses and cannot be marked sealed.")

        for vial in vials:
            before = {}
            after = {}
            for field, value in changes.items():
                old = getattr(vial, field)
                if old != value:
                    before[field] = old.isoformat() if isinstance(old, date) else old
                    after[field] = value.isoformat() if isinstance(value, date) else value
                    setattr(vial, field, value)
            if before:
                db.add(ChangeAudit(entity_type="vial", entity_id=vial.id,
                                   action="bulk_update", before_json=json.dumps(before),
                                   after_json=json.dumps(after)))
        db.commit()
    except (ValueError, TypeError) as exc:
        db.rollback()
        return services.flash_redirect("/vials", err=str(exc))
    return services.flash_redirect("/vials", msg=f"Bulk update reviewed for {len(vials)} selected vial(s).")


@router.get("/vials/{vid}")
def vial_detail(vid: int, request: Request, db: Session = Depends(get_db)):
    v = _get(db, vid)
    vd = services.vial_views(db, [v])[v.id]
    label_base, _ = U.to_base(v.content_value, v.content_unit)
    coa_variance = None
    measurements = []
    for c in v.all_coas:
        if c.reported_content_value is not None and c.reported_content_unit:
            content_base, dim = U.to_base(c.reported_content_value, c.reported_content_unit)
            if dim == U.parse_unit(v.content_unit).dim and content_base > 0:
                measurements.append((c, content_base))
    if measurements:
        average_base = sum(value for _, value in measurements) / len(measurements)
        coa_variance = {"count": len(measurements), "average": U.from_base(average_base, v.content_unit),
                        "unit": v.content_unit, "pct": 100 * (average_base - label_base) / label_base}
    doses = list(db.scalars(select(DoseLog).where(DoseLog.vial_id == vid)
                            .order_by(DoseLog.taken_at.desc())))
    rows = [{"dose": d, "cost": vd.cost_per_base * d.amount_base} for d in doses]
    return render(request, "vial_detail.html", v=v, vd=vd, label_base=label_base,
                  coa_variance=coa_variance, rows=rows, statuses=VIAL_STATUSES,
                  extras=vd.landed_cents - v.unit_price_cents, today=date.today().isoformat(),
                  bac_supplies=list(db.scalars(select(Supply).where(Supply.kind == "bac_water", Supply.remaining_qty > 0))),
                  all_coas=list(db.scalars(select(Coa).order_by(Coa.id.desc()))),
                  disposable_supplies=manual_supplies.available(db),
                  prep_events=list(db.scalars(select(PreparationEvent).where(PreparationEvent.vial_id == vid).order_by(PreparationEvent.id.desc()))), prep_usage={e.id: [(db.get(SupplyUsage, link.usage_id), db.get(Supply, db.get(SupplyUsage, link.usage_id).supply_id)) for link in db.scalars(select(PreparationSupply).where(PreparationSupply.event_id == e.id))] for e in db.scalars(select(PreparationEvent).where(PreparationEvent.vial_id == vid))})


@router.post("/vials/{vid}")
def update_vial(vid: int, label: str = Form(""), lot: str = Form(""), status: str = Form(...),
                content_value: float = Form(...), content_unit: str = Form(...),
                volume_ml: str = Form(""), reconstituted_on: str = Form(""),
                expires_on: str = Form(""), unit_price: str = Form("0"),
                received_on: str = Form(""), first_punctured_on: str = Form(""),
                first_dosed_on: str = Form(""), beyond_use_on: str = Form(""),
                closed_on: str = Form(""), storage_notes: str = Form(""),
                use_coa_content: str = Form(""), notes: str = Form(""), cap_color: str = Form(""),
                db: Session = Depends(get_db)):
    v = _get(db, vid)
    tracked = ("status", "received_on", "first_punctured_on", "first_dosed_on", "beyond_use_on", "closed_on", "storage_notes")
    previous = {key: str(getattr(v, key) or "") for key in tracked}
    back = f"/vials/{vid}"
    try:
        old_dim = U.parse_unit(v.content_unit).dim
        unit = U.parse_unit(content_unit)
        if v.compound.primary_unit == "IU" and unit.dim != "iu":
            raise ValueError("This compound is tracked in IU.")
        if unit.dim != old_dim:
            raise ValueError("Mass vs IU can't be changed on an existing vial. "
                             "Delete it and add a new one.")
        if not math.isfinite(content_value) or content_value <= 0:
            raise ValueError("Content must be a finite number above 0.")
        if status not in VIAL_STATUSES:
            raise ValueError("Unknown status.")
        vol = float(volume_ml) if volume_ml.strip() else None
        if vol is not None and (not math.isfinite(vol) or vol <= 0):
            raise ValueError("Volume must be a finite number above 0.")
        if status == "sealed" and v.doses:
            raise ValueError("A vial with logged doses cannot be marked sealed.")
        v.label, v.lot, v.status = label.strip(), lot.strip(), status
        v.content_value, v.content_unit, v.volume_ml = content_value, unit.name, vol
        v.reconstituted_on = services.parse_date(reconstituted_on)
        v.expires_on = services.parse_date(expires_on)
        for field, raw in (("received_on", received_on), ("first_punctured_on", first_punctured_on),
                           ("first_dosed_on", first_dosed_on), ("beyond_use_on", beyond_use_on),
                           ("closed_on", closed_on)):
            setattr(v, field, services.parse_date(raw))
        if v.first_punctured_on and v.received_on and v.first_punctured_on < v.received_on:
            raise ValueError("First puncture cannot precede receipt.")
        if v.first_dosed_on and v.first_punctured_on and v.first_dosed_on < v.first_punctured_on:
            raise ValueError("First dose cannot precede first puncture.")
        v.storage_notes = storage_notes.strip()
        v.unit_price_cents = services.to_cents(unit_price)
        v.use_coa_content = bool(use_coa_content)
        v.notes = notes.strip()
        v.cap_color = cap_color.strip()
    except ValueError as exc:
        db.rollback()
        return services.flash_redirect(back, err=str(exc))
    current = {key: str(getattr(v, key) or "") for key in tracked}
    if current != previous:
        db.add(ChangeAudit(entity_type="vial", entity_id=vid, action="lifecycle_update",
                           before_json=json.dumps(previous), after_json=json.dumps(current)))
    db.commit()
    return services.flash_redirect(back, msg="Vial updated.")


@router.post("/vials/{vid}/reconstitute")
async def reconstitute(vid: int, request: Request, volume_ml: float = Form(...), supply_id: str = Form(""), db: Session = Depends(get_db)):
    v = _get(db, vid)
    if volume_ml <= 0:
        return services.flash_redirect(f"/vials/{vid}", err="Volume must be more than 0.")
    if v.volume_ml is not None:
        return services.flash_redirect(f"/vials/{vid}", err="Already has a recorded volume. Edit vial details instead.")
    try:
        selected = await manual_supplies.selections(request, db)
    except ValueError as exc:
        return services.flash_redirect(f"/vials/{vid}", err=str(exc))
    if supply_id:
        s = db.get(Supply, int(supply_id))
        if not s or s.kind != "bac_water" or s.remaining_qty + 1e-9 < volume_ml:
            return services.flash_redirect(f"/vials/{vid}", err="Insufficient BAC water inventory.")
        if any(item.id == s.id and qty + volume_ml > s.remaining_qty + 1e-9 for item, qty in selected):
            return services.flash_redirect(f"/vials/{vid}", err="Combined BAC water and disposable usage exceeds available stock.")
        s.remaining_qty -= volume_ml
        db.add(SupplyUsage(supply_id=s.id, vial_id=vid, amount=volume_ml))
    event = PreparationEvent(vial_id=vid, kind="reconstitution", notes=f"Added {volume_ml:g} mL")
    db.add(event)
    db.flush()
    for usage in manual_supplies.deduct(db, selected, vial_id=vid):
        db.flush()
        db.add(PreparationSupply(event_id=event.id, usage_id=usage.id))
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


@router.post("/vials/{vid}/filter")
async def record_filtering(vid: int, request: Request, notes: str = Form(""), db: Session = Depends(get_db)):
    _get(db, vid)
    try:
        selected = await manual_supplies.selections(request, db)
    except ValueError as exc:
        return services.flash_redirect(f"/vials/{vid}", err=str(exc))
    if not selected:
        return services.flash_redirect(f"/vials/{vid}", err="Select at least one supply used for filtering.")
    event = PreparationEvent(vial_id=vid, kind="filtering", notes=notes.strip())
    db.add(event)
    db.flush()
    for usage in manual_supplies.deduct(db, selected, vial_id=vid):
        db.flush()
        db.add(PreparationSupply(event_id=event.id, usage_id=usage.id))
    db.commit()
    return services.flash_redirect(f"/vials/{vid}", msg="Filtering supplies recorded.")


@router.get("/vials/{vid}/preparations/{eid}/edit")
def edit_preparation_page(vid: int, eid: int, request: Request, db: Session = Depends(get_db)):
    event = db.get(PreparationEvent, eid)
    if not event or event.vial_id != vid: raise HTTPException(404)
    links = list(db.scalars(select(PreparationSupply).where(PreparationSupply.event_id == eid)))
    used = {db.get(SupplyUsage, link.usage_id).supply_id:db.get(SupplyUsage, link.usage_id).amount for link in links}
    return render(request, "preparation_edit.html", event=event, vial=_get(db,vid), supplies=list(db.scalars(select(Supply).order_by(Supply.name))), used=used)


@router.post("/vials/{vid}/preparations/{eid}/edit")
async def edit_preparation(vid: int, eid: int, request: Request, notes: str = Form(""), occurred_at: str = Form(""), db: Session = Depends(get_db)):
    event = db.get(PreparationEvent, eid)
    if not event or event.vial_id != vid: raise HTTPException(404)
    back = f"/vials/{vid}/preparations/{eid}/edit"
    try:
        selected = await manual_supplies.selections(request, db, credits={db.get(SupplyUsage,l.usage_id).supply_id:db.get(SupplyUsage,l.usage_id).amount for l in db.scalars(select(PreparationSupply).where(PreparationSupply.event_id == eid))})
        links = list(db.scalars(select(PreparationSupply).where(PreparationSupply.event_id == eid)))
        previous = [db.get(SupplyUsage, link.usage_id) for link in links]
        original = {}
        for u in previous: original[u.supply_id] = original.get(u.supply_id,0)+u.amount
        for item, qty in selected:
            if qty > item.remaining_qty + original.get(item.id,0) + 1e-9:
                raise ValueError(f"Insufficient {item.name} stock.")
        when = datetime.fromisoformat(occurred_at) if occurred_at else event.occurred_at
        before = {"notes":event.notes,"occurred_at":event.occurred_at.isoformat(),"supplies":original}
        for link, u in zip(links,previous):
            item = db.get(Supply,u.supply_id)
            if item: item.remaining_qty += u.amount
            db.delete(link)
            db.delete(u)
        db.flush()
        for item, qty in selected:
            item.remaining_qty -= qty
            u = SupplyUsage(supply_id=item.id, vial_id=vid, amount=qty)
            db.add(u); db.flush()
            db.add(PreparationSupply(event_id=eid, usage_id=u.id))
        event.notes, event.occurred_at = notes.strip(), when
        db.add(ChangeAudit(entity_type="preparation",entity_id=eid,action="edit",before_json=json.dumps(before),after_json=json.dumps({"notes":event.notes,"occurred_at":when.isoformat(),"supplies":{str(i.id):q for i,q in selected}})))
        db.commit()
    except (ValueError,TypeError) as exc:
        db.rollback()
        return services.flash_redirect(back,err=str(exc))
    return services.flash_redirect(f"/vials/{vid}",msg="Preparation corrected.")


@router.post("/vials/{vid}/preparations/{eid}/delete")
def delete_preparation(vid: int, eid: int, db: Session = Depends(get_db)):
    event = db.get(PreparationEvent,eid)
    if not event or event.vial_id != vid: raise HTTPException(404)
    # Reconstitution records affect vial volume and are not safe to erase after doses.
    if event.kind == "reconstitution":
        return services.flash_redirect(f"/vials/{vid}",err="Reconstitution records cannot be deleted here; correct the vial's recorded volume instead.")
    links = list(db.scalars(select(PreparationSupply).where(PreparationSupply.event_id == eid)))
    old = {}
    for link in links:
        u = db.get(SupplyUsage,link.usage_id)
        if u:
            item = db.get(Supply,u.supply_id)
            if item: item.remaining_qty += u.amount
            old[str(u.supply_id)] = old.get(str(u.supply_id),0)+u.amount
            db.delete(u)
        db.delete(link)
    db.add(ChangeAudit(entity_type="preparation",entity_id=eid,action="delete",before_json=json.dumps({"kind":event.kind,"supplies":old,"notes":event.notes})))
    db.delete(event); db.commit()
    return services.flash_redirect(f"/vials/{vid}",msg="Preparation removed; supplies restored.")
