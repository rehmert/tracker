from datetime import date
import math

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import calc, services, units as U
from ..db import get_db
from ..models import Compound, Purchase, Vial, Supply, SupplyUsage, SupplyCategory
from ..supply_categories import ensure_categories, validate_supply
from ..templating import render

router = APIRouter()


@router.get("/purchases")
def purchases_page(request: Request, db: Session = Depends(get_db)):
    rows = []
    for p in db.scalars(select(Purchase).order_by(Purchase.purchased_on.desc(), Purchase.id.desc())):
        landed = services.purchase_landed(p)
        rows.append({"p": p, "n": len(p.vials), "supply_count": len(p.supplies),
                     "total": sum(landed.values())})
    return render(request, "purchases.html", rows=rows, today=date.today().isoformat())


@router.post("/purchases")
def create_purchase(vendor: str = Form(...), purchased_on: str = Form(""),
                    order_ref: str = Form(""), shipping: str = Form("0"), tax: str = Form("0"),
                    discount: str = Form("0"), notes: str = Form(""),
                    db: Session = Depends(get_db)):
    try:
        p = Purchase(vendor=vendor.strip() or "Unknown vendor",
                     purchased_on=services.parse_date(purchased_on) or date.today(),
                     order_ref=order_ref.strip(), shipping_cents=services.to_cents(shipping),
                     tax_cents=services.to_cents(tax), discount_cents=services.to_cents(discount),
                     notes=notes.strip())
    except ValueError as exc:
        return services.flash_redirect("/purchases", err=str(exc))
    db.add(p)
    db.commit()
    return services.flash_redirect(f"/purchases/{p.id}", msg="Purchase saved. Add vials, supplies or pills below.")


@router.get("/purchases/{pid}")
def purchase_detail(pid: int, request: Request, db: Session = Depends(get_db)):
    p = db.get(Purchase, pid)
    if p is None:
        raise HTTPException(404, "Purchase not found")
    views = services.vial_views(db, list(p.vials))
    subtotal = sum(v.unit_price_cents for v in p.vials) + sum(
        services.supply_line_cents(s) for s in p.supplies)
    compounds = list(db.scalars(select(Compound).order_by(Compound.name)))
    supplies = list(db.scalars(select(Supply).where(Supply.purchase_id == pid)))
    landed = services.purchase_landed(p)
    categories = ensure_categories(db)
    return render(request, "purchase_detail.html", categories=categories, category_map={c.key: c for c in categories}, p=p, views=views, supplies=supplies, subtotal=subtotal,
                  total=sum(landed.values()), supply_landed=landed, compounds=compounds, supply_line_cents=services.supply_line_cents)


@router.post("/purchases/{pid}")
def update_purchase(pid: int, vendor: str = Form(...), purchased_on: str = Form(""),
                    order_ref: str = Form(""), shipping: str = Form("0"), tax: str = Form("0"),
                    discount: str = Form("0"), notes: str = Form(""),
                    db: Session = Depends(get_db)):
    p = db.get(Purchase, pid)
    if p is None:
        raise HTTPException(404, "Purchase not found")
    try:
        p.vendor = vendor.strip() or p.vendor
        p.purchased_on = services.parse_date(purchased_on) or p.purchased_on
        p.order_ref = order_ref.strip()
        p.shipping_cents = services.to_cents(shipping)
        p.tax_cents = services.to_cents(tax)
        p.discount_cents = services.to_cents(discount)
        p.notes = notes.strip()
    except ValueError as exc:
        db.rollback()
        return services.flash_redirect(f"/purchases/{pid}", err=str(exc))
    db.commit()
    return services.flash_redirect(f"/purchases/{pid}", msg="Purchase updated.")


@router.post("/purchases/{pid}/vials")
def add_vials(pid: int, compound_id: int = Form(...), form: str = Form("lyophilized"),
              quantity: int = Form(1), content_value: str = Form(""), content_unit: str = Form("mg"),
              volume_ml: str = Form(""), concentration: str = Form(""),
              unit_price: str = Form("0"), label: str = Form(""), lot: str = Form(""),
              expires_on: str = Form(""), notes: str = Form(""),
              kit_size: int = Form(1), kit_count: int = Form(1), cap_color: str = Form(""),
              db: Session = Depends(get_db)):
    p = db.get(Purchase, pid)
    if p is None:
        raise HTTPException(404, "Purchase not found")
    back = f"/purchases/{pid}"
    try:
        if db.get(Compound, compound_id) is None:
            raise ValueError("Choose a compound first (add one on the Compounds page).")
        if kit_size not in (1, 5, 10) or not 1 <= kit_count <= 100:
            raise ValueError("Kit size must be 1, 5 or 10 and count must be 1-100.")
        quantity = kit_size * kit_count if kit_size != 1 else quantity
        if not 1 <= quantity <= 1000:
            raise ValueError("Quantity must be between 1 and 200.")
        def number(text: str, what: str) -> float:
            try:
                return float(text)
            except ValueError:
                raise ValueError(f"Enter {what} as a number.")

        unit = U.parse_unit(content_unit)
        if unit.dim == "volume":
            raise ValueError("A vial's contents are measured in mass or IU, not volume.")
        vol = number(volume_ml, "the liquid volume") if volume_ml.strip() else None
        if vol is not None and vol <= 0:
            raise ValueError("Volume must be more than 0.")
        if form == "solution":
            if vol is None:
                raise ValueError("A solution needs its liquid volume in mL.")
            if concentration.strip() and not content_value.strip():
                # concentration is "<number> <content unit>/mL"
                content = number(concentration, "the concentration") * vol
            else:
                content = number(content_value, "the vial contents")
        else:
            form = "lyophilized"
            content = number(content_value, "the vial contents")
        if content <= 0:
            raise ValueError("Enter how much is in the vial (above 0).")
        _, dim = U.to_base(content, unit.name)
        existing = db.scalars(select(Vial).where(Vial.compound_id == compound_id)).first()
        if existing and U.parse_unit(existing.content_unit).dim != dim:
            raise ValueError("This compound's other vials are tracked in a different "
                             "dimension (mass vs IU). Use the same one.")
        price = services.to_cents(unit_price)
        expiry = services.parse_date(expires_on)
    except ValueError as exc:
        return services.flash_redirect(back, err=str(exc))

    for i in range(quantity):
        db.add(Vial(cap_color=cap_color.strip(), kit_ref=(f"purchase-{pid}-kit-{i // kit_size + 1}" if kit_size > 1 else ""),compound_id=compound_id, purchase_id=pid, label=label.strip(),
                    lot=lot.strip(), form=form, content_value=content,
                    content_unit=unit.name, volume_ml=vol, expires_on=expiry,
                    unit_price_cents=price, notes=notes.strip()))
    db.commit()
    return services.flash_redirect(back, msg=f"Added {quantity} vial(s).")


@router.post("/purchases/{pid}/delete")
def delete_purchase(pid: int, db: Session = Depends(get_db)):
    p = db.get(Purchase, pid)
    if p is None:
        return services.flash_redirect("/purchases", err="Purchase not found.")
    if p.vials or p.supplies:
        return services.flash_redirect(
            f"/purchases/{pid}", err="Delete or move this purchase's vials, supplies and pills first.")
    db.delete(p)
    db.commit()
    return services.flash_redirect("/purchases", msg="Purchase deleted.")


def parse_bulk(db, kind, quantity, pack_count, units_per_pack, package_price):
    """Optional bulk pack purchase. Quantity remains in consumable units."""
    values = [str(v).strip() if isinstance(v, (str, int, float)) else ""
              for v in (pack_count, units_per_pack, package_price)]
    if not any(values):
        validate_supply(db, kind, quantity)
        return quantity, None, None, None
    if not all(values):
        raise ValueError("For bulk purchases, enter packs, units per pack, and total package price.")
    try:
        count = int(values[0])
        per_pack = float(values[1])
        price = services.to_cents(values[2])
    except (ValueError, OverflowError) as exc:
        raise ValueError("Invalid bulk package details.") from exc
    if count < 1 or count > 100000 or not math.isfinite(per_pack) or per_pack <= 0 or price < 0:
        raise ValueError("Bulk pack quantities and prices must be valid positive values.")
    total = count * per_pack
    if not math.isfinite(total) or total > 1000000:
        raise ValueError("Bulk purchase exceeds maximum supported inventory quantity.")
    validate_supply(db, kind, total)
    return total, count, per_pack, price


@router.post("/purchases/{pid}/supplies")
def add_purchase_supply(pid: int, name: str = Form(...), kind: str = Form(...),
                        quantity: float = Form(...), unit_price: str = Form("0"),
                        compound_id: str = Form(""), notes: str = Form(""),
                        db: Session = Depends(get_db), pack_count: str = Form(""),
                        units_per_pack: str = Form(""), package_price: str = Form("")):
    back = f"/purchases/{pid}"
    if db.get(Purchase, pid) is None:
        raise HTTPException(404, "Purchase not found")
    ensure_categories(db)
    try:
        quantity, bulk_count, bulk_size, bulk_cents = parse_bulk(
            db, kind, quantity, pack_count, units_per_pack, package_price)
    except ValueError as exc:
        return services.flash_redirect(back, err=str(exc))
    if not name.strip():
        return services.flash_redirect(back, err="Enter a valid supply type, name and quantity.")
    try:
        price = services.to_cents(unit_price)
        cid = int(compound_id) if compound_id else None
        if cid is not None and db.get(Compound, cid) is None:
            raise ValueError("Unknown compound.")
    except (ValueError, TypeError) as exc:
        return services.flash_redirect(back, err=str(exc))
    db.add(Supply(purchase_id=pid, name=name.strip(), kind=kind, compound_id=cid,
                  purchased_qty=quantity, remaining_qty=quantity,
                  unit_price_cents=price, bulk_pack_count=bulk_count,
                  bulk_units_per_pack=bulk_size, bulk_total_cents=bulk_cents, notes=notes.strip()))
    db.commit()
    return services.flash_redirect(back, msg="Supply or pills added to purchase.")


@router.post("/purchases/{pid}/supplies/{sid}/edit")
def edit_purchase_supply(pid: int, sid: int, name: str = Form(...),
                         kind: str = Form(...), quantity: float = Form(...),
                         unit_price: str = Form("0"), compound_id: str = Form(""),
                         notes: str = Form(""), db: Session = Depends(get_db),
                         pack_count: str = Form(""), units_per_pack: str = Form(""),
                         package_price: str = Form("")):
    """Edit a purchased supply/pill without resetting its usage history."""
    back = f"/purchases/{pid}"
    s = db.get(Supply, sid)
    if s is None or s.purchase_id != pid:
        raise HTTPException(404, "Purchase item not found")
    try:
        ensure_categories(db)
        quantity, bulk_count, bulk_size, bulk_cents = parse_bulk(
            db, kind, quantity, pack_count, units_per_pack, package_price)
        if not name.strip():
            raise ValueError("Choose a valid type and product name.")
        if not math.isfinite(quantity) or not 0 < quantity <= 1000000:
            raise ValueError("Purchased quantity must be positive and finite.")
        usage = list(db.scalars(select(SupplyUsage).where(SupplyUsage.supply_id == sid)))
        if usage and kind != s.kind:
            raise ValueError("Cannot change item type after usage is recorded.")
        used = sum(u.amount for u in usage)
        # Preserve current remaining inventory, including manual adjustments, by
        # applying only the change in purchased quantity.
        new_remaining = s.remaining_qty + (quantity - s.purchased_qty)
        if quantity + 1e-8 < used or new_remaining < -1e-8:
            raise ValueError("New purchased quantity cannot be below the amount already used.")
        if db.query(SupplyCategory).filter_by(key=kind).first().unit == "count" and abs(new_remaining - round(new_remaining)) > 1e-8:
            raise ValueError("Count-unit inventory must remain a whole number.")
        cid = int(compound_id) if compound_id.strip() else None
        if cid is not None and db.get(Compound, cid) is None:
            raise ValueError("Unknown compound.")
        price = services.to_cents(unit_price)
        if price < 0:
            raise ValueError("Unit price cannot be negative.")
        s.name = name.strip()
        s.kind = kind
        s.compound_id = cid
        s.purchased_qty = quantity
        s.remaining_qty = max(0.0, new_remaining)
        s.unit_price_cents = price
        s.bulk_pack_count = bulk_count
        s.bulk_units_per_pack = bulk_size
        s.bulk_total_cents = bulk_cents
        s.notes = notes.strip()
    except (ValueError, TypeError) as exc:
        db.rollback()
        return services.flash_redirect(back, err=str(exc))
    db.commit()
    return services.flash_redirect(back, msg="Purchased item updated.")


@router.post("/purchases/{pid}/supplies/{sid}/delete")
def delete_purchase_supply(pid: int, sid: int, db: Session = Depends(get_db)):
    back = f"/purchases/{pid}"
    s = db.get(Supply, sid)
    if s is None or s.purchase_id != pid:
        raise HTTPException(404, "Purchase item not found")
    if db.scalar(select(SupplyUsage.id).where(SupplyUsage.supply_id == sid).limit(1)) is not None:
        return services.flash_redirect(back, err="Cannot delete an item with recorded usage. Edit it instead.")
    if abs(s.remaining_qty - s.purchased_qty) > 1e-8:
        return services.flash_redirect(back, err="Cannot delete an item with adjusted inventory. Reconcile it first.")
    db.delete(s)
    db.commit()
    return services.flash_redirect(back, msg="Purchased item deleted.")


@router.post("/purchases/{pid}/vials/{vid}/delete")
def delete_purchase_vial(pid: int, vid: int, db: Session = Depends(get_db)):
    back = f"/purchases/{pid}"
    v = db.get(Vial, vid)
    if v is None or v.purchase_id != pid:
        raise HTTPException(404, "Purchase item not found")
    if v.doses:
        return services.flash_redirect(back, err="Cannot delete a vial with logged doses or waste.")
    if db.scalar(select(SupplyUsage.id).where(SupplyUsage.vial_id == vid).limit(1)) is not None:
        return services.flash_redirect(back, err="Cannot delete a vial with recorded supply usage (e.g. reconstitution).")
    db.delete(v)
    db.commit()
    return services.flash_redirect(back, msg="Vial deleted from purchase.")
