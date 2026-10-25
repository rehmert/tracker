from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Purchase, Supply, SupplyUsage, Compound
from .. import services
from ..templating import render
router = APIRouter()

@router.get("/supplies")
def index(request: Request, db: Session = Depends(get_db)):
    return render(request, "supplies.html", supplies=list(db.scalars(select(Supply).order_by(Supply.id.desc()))), purchases=list(db.scalars(select(Purchase).order_by(Purchase.id.desc()))), compounds=list(db.scalars(select(Compound).order_by(Compound.name))))

@router.post("/supplies")
def add(purchase_id: int = Form(...), name: str = Form(...), kind: str = Form(...), quantity: float = Form(...), unit_price: str = Form("0"), compound_id: str = Form(""), db: Session = Depends(get_db)):
    if kind not in ("bac_water", "pill") or quantity <= 0 or not name.strip():
        return services.flash_redirect("/supplies", err="Invalid supply or quantity.")
    if not db.get(Purchase, purchase_id):
        raise HTTPException(404)
    cid = int(compound_id) if compound_id else None
    if cid and not db.get(Compound, cid):
        raise HTTPException(404)
    db.add(Supply(purchase_id=purchase_id, name=name.strip(), kind=kind, compound_id=cid, purchased_qty=quantity, remaining_qty=quantity, unit_price_cents=services.to_cents(unit_price)))
    db.commit()
    return services.flash_redirect("/supplies", msg="Supply added.")

@router.post("/supplies/{sid}/use")
def use(sid: int, quantity: float = Form(...), db: Session = Depends(get_db)):
    s = db.get(Supply, sid)
    if not s: raise HTTPException(404)
    if quantity <= 0 or quantity > s.remaining_qty + 1e-9:
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
