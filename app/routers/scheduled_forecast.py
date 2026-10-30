"""Read-only schedule-aware demand planning; never modifies inventory."""
import csv
import io
from collections import defaultdict
from datetime import date, timedelta
from math import isfinite
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Protocol
from ..templating import render
from .. import calendar as cal
from ..projection_exclusions import exclusions_for, excluded
from .inventory_forecast import build_rows, normalized

router = APIRouter()
HORIZONS = (7, 14, 28, 56)

def build_schedule(db, today=None):
    today = today or date.today()
    end = today + timedelta(days=max(HORIZONS))
    protocols = list(db.scalars(select(Protocol).where(Protocol.is_active.is_(True))))
    rules = exclusions_for(db, [i.id for p in protocols for i in p.items])
    # Existing stock logic is reused. Multiple protocol items share stock;
    # never sum repeated stock values.
    stock = defaultdict(list)
    for r in build_rows(db, days=max(HORIZONS)):
        stock[(r['compound'], r['unit'])].append(r)
    result = defaultdict(lambda: {'items':set(),'protocols':set(),'counts':defaultdict(int),
                                  'demand':defaultdict(float),'unestimated':False})
    warnings = []
    for p in protocols:
        if p.start_date is None:
            warnings.append(f'{p.name}: start date missing; projections omitted')
            continue
        if p.start_date > end or (p.end_date and p.end_date < today):
            continue
        for item in p.items:
            name = item.compound.name
            unit = item.amount_unit
            key = (name,unit)
            entry = result[key]
            entry['items'].add(item.id)
            entry['protocols'].add(p.name)
            amount = normalized(item.amount_value, unit)
            if amount is None or not isfinite(amount):
                entry['unestimated'] = True
            try:
                dates = cal.staged_occurrences(item, p.start_date, (end-p.start_date).days+1)
                for when in dates:
                    if when < today or when >= end or (p.end_date and when > p.end_date):
                        continue
                    if excluded(rules,item.id,when):
                        continue
                    for horizon in HORIZONS:
                        if when < today + timedelta(days=horizon):
                            entry['counts'][horizon] += 1
                            if amount is not None:
                                entry['demand'][horizon] += amount
            except (ValueError, TypeError, OverflowError) as exc:
                entry['unestimated'] = True
                warnings.append(f'{p.name} / {name}: projection could not be calculated ({type(exc).__name__})')
    rows=[]
    for (name,unit),record in sorted(result.items(),key=lambda kv:(kv[0][0].casefold(),kv[0][1])):
        # Source demand is in base mass units; convert back for display.
        factor = {'mcg':1,'mg':1000,'g':1000000,'IU':1}.get(unit)
        stock_unit = 'IU' if unit == 'IU' else 'mg'
        matches=stock.get((name,stock_unit),[])
        values=[float(m['available']) for m in matches]
        consistent=bool(matches) and all(isfinite(v) and v>=0 for v in values) and len({round(v,8) for v in values})==1
        available=values[0] * (1000 / factor) if consistent and factor and unit != 'IU' else (values[0] if consistent else None)
        demands={h:(record['demand'][h]/factor if factor and not record['unestimated'] else None) for h in HORIZONS}
        flags={}
        for h in HORIZONS:
            demand=demands[h]
            flags[h]=('Review demand' if demand is None else
                      'Review stock' if available is None else
                      'Potential shortfall' if demand>available else 'Roughly covered')
        rows.append({'compound':name,'unit':unit,'protocols':len(record['protocols']),
                     'items':len(record['items']),'available':available,
                     'counts':dict(record['counts']),'demands':demands,'flags':flags})
    return rows,warnings

@router.get('/scheduled-forecast')
def scheduled_forecast(request:Request,db:Session=Depends(get_db)):
    rows,warnings=build_schedule(db)
    return render(request,'scheduled_forecast.html',rows=rows,warnings=warnings,horizons=HORIZONS)

@router.get('/scheduled-forecast.csv')
def scheduled_forecast_csv(db:Session=Depends(get_db)):
    rows,warnings=build_schedule(db)
    stream=io.StringIO()
    writer=csv.writer(stream)
    writer.writerow(['Compound','Unit','Active protocols','Items','Available estimate']+
                    [f'{h}d occurrences' for h in HORIZONS]+
                    [f'{h}d scheduled demand' for h in HORIZONS]+
                    [f'{h}d flag' for h in HORIZONS])
    for r in rows:
        writer.writerow([r['compound'],r['unit'],r['protocols'],r['items'],
                         '' if r['available'] is None else round(r['available'],4)]+
                        [r['counts'].get(h,0) for h in HORIZONS]+
                        ['' if r['demands'][h] is None else round(r['demands'][h],4) for h in HORIZONS]+
                        [r['flags'][h] for h in HORIZONS])
    return Response(stream.getvalue(),media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition':'attachment; filename="scheduled-forecast.csv"'})
