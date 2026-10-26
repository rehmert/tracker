import math
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Purchase, Supply, SupplyUsage, Compound, SupplyCategory
from ..supply_categories import ensure_categories, validate_supply
from .. import services
from ..templating import render
router = APIRouter()

@router.get("/supplies")
def index(request: Request, db: Session = Depends(get_db)):
    categories = ensure_categories(db)
    return render(request, "supplies.html", categories=categories, category_map={c.key: c for c in categories}, supplies=list(db.scalars(select(Supply).order_by(Supply.id.desc()))), purchases=list(db.scalars(select(Purchase).order_by(Purchase.id.desc()))), compounds=list(db.scalars(select(Compound).order_by(Compound.name))))

@router.post("/supplies")
def add(purchase_id: int = Form(...), name: str = Form(...), kind: str = Form(...), quantity: float = Form(...), unit_price: str = Form("0"), pack_count: str = Form(""),
        units_per_pack: str = Form(""), package_price: str = Form(""), compound_id: str = Form(""), db: Session = Depends(get_db)):
    ensure_categories(db)
    try:
        from .purchases import parse_bulk
        quantity, bulk_count, bulk_size, bulk_cents = parse_bulk(
            db, kind, quantity, pack_count, units_per_pack, package_price)
        if not name.strip(): raise ValueError("Name is required.")
    except ValueError as exc:
        return services.flash_redirect("/supplies", err=str(exc))
    if not db.get(Purchase, purchase_id):
        raise HTTPException(404)
    cid = int(compound_id) if compound_id else None
    if cid and not db.get(Compound, cid):
        raise HTTPException(404)
    db.add(Supply(purchase_id=purchase_id, name=name.strip(), kind=kind, compound_id=cid, purchased_qty=quantity, remaining_qty=quantity, unit_price_cents=services.to_cents(unit_price),
                  bulk_pack_count=bulk_count, bulk_units_per_pack=bulk_size, bulk_total_cents=bulk_cents))
    db.commit()
    return services.flash_redirect("/supplies", msg="Supply added.")

@router.post("/supplies/{sid}/use")
def use(sid: int, quantity: float = Form(...), db: Session = Depends(get_db)):
    s = db.get(Supply, sid)
    if not s: raise HTTPException(404)
    category = db.query(SupplyCategory).filter_by(key=s.kind).first()
    if quantity <= 0 or quantity > s.remaining_qty + 1e-9 or (category and category.unit == "count" and not float(quantity).is_integer()):
        return services.flash_redirect("/supplies", err="Quantity exceeds available stock.")
    s.remaining_qty -= quantity
    db.add(SupplyUsage(supply_id=sid, amount=quantity))
    db.commit()
    return services.flash_redirect("/supplies", msg="Usage recorded.")

@router.post('/supplies/{sid}/dose')
def log_pill(sid: int, quantity: int = Form(...), taken_at: str = Form(''), notes: str = Form(''), db: Session = Depends(get_db)):
    from ..models import SupplyUsage
    s = db.get(Supply, sid)
    if not s: raise HTTPException(404)
    if s.kind != 'pill' or quantity <= 0 or quantity > s.remaining_qty:
        return services.flash_redirect('/supplies', err='Invalid pill quantity or insufficient stock.')
    s.remaining_qty -= quantity
    db.add(SupplyUsage(supply_id=s.id, amount=quantity))
    db.commit()
    return services.flash_redirect('/supplies', msg=f'Recorded {quantity} pill(s) used.')

@router.post("/supplies/categories")
def create_category(label: str = Form(...), unit: str = Form("count"), db: Session = Depends(get_db)):
    import re
    ensure_categories(db)
    label = label.strip()[:100]
    if not label or unit not in ("count", "mL", "g", "mg", "L", "boxes", "packs"):
        return services.flash_redirect("/supplies", err="Enter a category name and valid unit.")
    key = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:20]
    if not key or db.query(SupplyCategory).filter((SupplyCategory.key == key) | (SupplyCategory.label == label)).first():
        return services.flash_redirect("/supplies", err="Category already exists or has an invalid name.")
    db.add(SupplyCategory(key=key, label=label, unit=unit))
    db.commit()
    return services.flash_redirect("/supplies", msg="Category created. It is now available on purchases and supplies.")
