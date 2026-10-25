from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import calc, services, units as U
from ..db import get_db
from ..models import Compound, Purchase, Vial, Supply
from ..templating import render

router = APIRouter()


@router.get("/purchases")
def purchases_page(request: Request, db: Session = Depends(get_db)):
    rows = []
    for p in db.scalars(select(Purchase).order_by(Purchase.purchased_on.desc(), Purchase.id.desc())):
        landed = calc.allocate_landed({v.id: v.unit_price_cents for v in p.vials},
                                      p.shipping_cents, p.tax_cents, p.discount_cents)
        rows.append({"p": p, "n": len(p.vials), "total": sum(landed.values())})
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
    return services.flash_redirect(f"/purchases/{p.id}", msg="Purchase saved. Add its vials below.")


@router.get("/purchases/{pid}")
def purchase_detail(pid: int, request: Request, db: Session = Depends(get_db)):
    p = db.get(Purchase, pid)
    if p is None:
        raise HTTPException(404, "Purchase not found")
    views = services.vial_views(db, list(p.vials))
    subtotal = sum(v.unit_price_cents for v in p.vials)
    compounds = list(db.scalars(select(Compound).order_by(Compound.name)))
    supplies = list(db.scalars(select(Supply).where(Supply.purchase_id == pid)))
    return render(request, "purchase_detail.html", p=p, views=views, supplies=supplies, subtotal=subtotal,
                  total=sum(d.landed_cents for d in views.values()), compounds=compounds)


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
    if p.vials:
        return services.flash_redirect(
            f"/purchases/{pid}", err="Delete or move this purchase's vials first.")
    db.delete(p)
    db.commit()
    return services.flash_redirect("/purchases", msg="Purchase deleted.")
