"""Read-only, approximate inventory planning (not dosing guidance)."""
from collections import defaultdict
from datetime import date, timedelta
from math import isfinite
import csv
import io
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Protocol, ProtocolItem, Compound, Vial, DoseLog, BlendComponent
from ..templating import render

router = APIRouter()

FACTORS = {"mcg": 1.0, "mg": 1000.0, "g": 1000000.0, "IU": 1.0}

def normalized(value, unit):
    if unit not in FACTORS or value is None:
        return None
    try:
        v = float(value) * FACTORS[unit]
    except (TypeError, ValueError, OverflowError):
        return None
    return v if isfinite(v) and v >= 0 else None

def compatible(a, b):
    return a == b or (a in ("mcg", "mg", "g") and b in ("mcg", "mg", "g"))

def weekly(item):
    try:
        count = float(item.freq_count)
        dose = normalized(item.amount_value, item.amount_unit)
        if dose is None or not isfinite(count) or count <= 0 or dose <= 0:
            return None
        periods = {"day": 7.0, "week": 1.0, "month": 7.0 / (365.2425 / 12.0)}
        if item.freq_period not in periods:
            return None
        return dose * count * periods[item.freq_period]
    except (TypeError, ValueError, OverflowError):
        return None

def build_rows(db, days=28):
    today = date.today()
    protocols = db.scalars(select(Protocol).where(Protocol.is_active.is_(True))).all()
    compounds = {c.id: c for c in db.scalars(select(Compound)).all()}
    vials = db.scalars(select(Vial)).all()
    doses = db.scalars(select(DoseLog)).all()
    transfers = db.scalars(select(BlendComponent)).all()
    used = defaultdict(float)
    for d in doses:
        try:
            amount = float(d.amount_base or 0)
            if isfinite(amount) and amount > 0: used[d.vial_id] += amount
        except (TypeError, ValueError, OverflowError):
            pass
    for t in transfers:
        try:
            amount = float(t.transferred_base or 0)
            if isfinite(amount) and amount > 0: used[t.source_vial_id] += amount
        except (TypeError, ValueError, OverflowError):
            pass
    rows=[]
    for p in protocols:
        if p.start_date and p.start_date > today + timedelta(days=days): continue
        if p.end_date and p.end_date < today: continue
        for item in p.items:
            compound=compounds.get(item.compound_id)
            available=0.0; count=0; excluded=0
            for vial in vials:
                if vial.compound_id != item.compound_id: continue
                if vial.status not in ('sealed','in_use') or vial.closed_on:
                    excluded += 1; continue
                if (vial.expires_on and vial.expires_on < today) or (vial.beyond_use_on and vial.beyond_use_on < today):
                    excluded += 1; continue
                if not compatible(vial.content_unit, item.amount_unit):
                    excluded += 1; continue
                content=normalized(vial.content_value, vial.content_unit)
                if content is None:
                    excluded += 1; continue
                # amount_base and transferred_base are recorded in mcg or IU.
                available += max(0.0, content-used[vial.id]); count += 1
            rate=weekly(item)
            # A single weekly average is deliberately not treated as an exact
            # schedule. Escalation weeks, exclusions and timing aren't modeled.
            if rate is None:
                demand=None; weeks=None; status='Not estimable'
            else:
                demand=rate * days/7.0
                weeks=available/rate if rate else None
                status=('No matching inventory' if count==0 else
                        'Below rough demand' if available < demand else
                        'Roughly covered')
            unit='IU' if item.amount_unit=='IU' else 'mg'
            scale=1 if unit=='IU' else 1000
            rows.append(dict(protocol=p.name, compound=compound.name if compound else f'Compound #{item.compound_id}',
                unit=unit, vials=count, excluded=excluded, available=available/scale,
                demand=(demand/scale if demand is not None else None),
                weeks=weeks, status=status, protocol_id=p.id,
                caveat='Average only; ignores schedule windows, escalation, exclusions, and future expiration.'))
    return sorted(rows,key=lambda r:(r['status']!='No matching inventory',r['status']!='Below rough demand',r['compound'].lower(),r['protocol'].lower()))

@router.get('/inventory-forecast')
def inventory_forecast(request:Request, db:Session=Depends(get_db)):
    return render(request,'inventory_forecast.html',rows=build_rows(db),horizon=28)

@router.get('/inventory-forecast.csv')
def inventory_forecast_csv(db:Session=Depends(get_db)):
    buffer=io.StringIO(); writer=csv.writer(buffer)
    writer.writerow(['Protocol','Compound','Eligible vials','Excluded vials','Remaining (approx)','28-day demand (approx)','Unit','Weeks at average rate','Status','Caveat'])
    for r in build_rows(db):
        writer.writerow([r['protocol'],r['compound'],r['vials'],r['excluded'],round(r['available'],4),
            '' if r['demand'] is None else round(r['demand'],4),r['unit'],
            '' if r['weeks'] is None else round(r['weeks'],2),r['status'],r['caveat']])
    buffer.seek(0)
    return StreamingResponse(iter([buffer.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="inventory-forecast.csv"'})
