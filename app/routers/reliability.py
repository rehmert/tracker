"""Inventory reconciliation and read-only data-quality checks."""
import math
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Supply, SupplyUsage, InventoryAdjustment, ChangeAudit, Vial, DoseLog, Purchase
from .. import services
from ..templating import render
import json

router = APIRouter()

@router.get("/reconciliation")
def reconciliation(request: Request, db: Session = Depends(get_db)):
    supplies = list(db.scalars(select(Supply).order_by(Supply.name,Supply.id)))
    history = list(db.scalars(select(InventoryAdjustment).order_by(InventoryAdjustment.id.desc()).limit(100)))
    return render(request,"reconciliation.html",supplies=supplies,history=history,
                  supply_names={s.id:s.name for s in supplies})

@router.post("/reconciliation/{sid}")
def reconcile(sid:int, counted:float=Form(...), reason:str=Form(...), db:Session=Depends(get_db)):
    s=db.get(Supply,sid)
    if not s: raise HTTPException(404)
    if not math.isfinite(counted) or counted < 0 or not reason.strip():
        return services.flash_redirect('/reconciliation',err='Enter a nonnegative count and a reason.')
    from ..models import SupplyCategory
    cat=db.scalars(select(SupplyCategory).where(SupplyCategory.key==s.kind)).first()
    if cat and cat.unit=='count' and not counted.is_integer():
        return services.flash_redirect('/reconciliation',err='Counted supplies require whole quantities.')
    db.add(InventoryAdjustment(supply_id=sid,previous_qty=s.remaining_qty,counted_qty=counted,reason=reason.strip()[:240]))
    db.add(ChangeAudit(entity_type='supply',entity_id=sid,action='reconcile',before_json=json.dumps({'remaining_qty':s.remaining_qty}),after_json=json.dumps({'remaining_qty':counted,'reason':reason.strip()})))
    s.remaining_qty=counted
    db.commit()
    return services.flash_redirect('/reconciliation',msg='Physical count recorded with audit history.')

@router.get('/data-integrity')
def integrity(request:Request,db:Session=Depends(get_db)):
    issues=[]
    for s in db.scalars(select(Supply)):
        if s.remaining_qty < -1e-7: issues.append(('Error',f'Supply #{s.id} {s.name} has negative remaining stock.',f'/supplies'))
        if s.purchased_qty < 0: issues.append(('Error',f'Supply #{s.id} has negative purchased quantity.','/supplies'))
        if not s.name.strip(): issues.append(('Warning',f'Supply #{s.id} is unnamed.','/supplies'))
    for v in db.scalars(select(Vial)):
        if v.expires_on and v.expires_on < date.today() and v.status in ('sealed','in_use'):
            issues.append(('Warning',f'Vial #{v.id} has expired but is still active.',f'/vials/{v.id}'))
        if v.reconstituted_on and v.reconstituted_on > date.today():
            issues.append(('Warning',f'Vial #{v.id} has a future reconstitution date.',f'/vials/{v.id}'))
    for d in db.scalars(select(DoseLog)):
        if d.amount_base <= 0: issues.append(('Error',f'Dose #{d.id} has nonpositive quantity.','/doses'))
    return render(request,'data_integrity.html',issues=issues)

@router.get('/consumption')
def consumption(request:Request,days:int=90,db:Session=Depends(get_db)):
    days=max(7,min(days,3650))
    since=__import__('datetime').datetime.now()-timedelta(days=days)
    supplies=list(db.scalars(select(Supply).order_by(Supply.name)))
    rows=[]
    for s in supplies:
        used=db.scalar(select(func.coalesce(func.sum(SupplyUsage.amount),0)).where(SupplyUsage.supply_id==s.id,SupplyUsage.created_at>=since)) or 0
        rate=used/days
        rows.append({'s':s,'used':used,'per_day':rate,'coverage':s.remaining_qty/rate if rate else None})
    return render(request,'consumption.html',rows=rows,days=days)

@router.get('/quick-entry')
def quick_entry(request:Request):
    return render(request,'quick_entry.html')


@router.get('/release-info')
def release_info(request:Request,db:Session=Depends(get_db)):
    from sqlalchemy import inspect
    return render(request,'release_info.html',version='2.0.0',tables=len(inspect(db.bind).get_table_names()))
