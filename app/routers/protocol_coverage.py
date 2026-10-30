"""Read-only inventory visibility for active protocols; not a dosing recommendation."""
from collections import defaultdict
from datetime import date
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
import csv
import io
from ..db import get_db
from ..models import Protocol, ProtocolItem, Compound, Vial

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))

# Deliberately counts vials, not remaining doses: concentrations, IU and
# escalation schedules cannot safely be converted to a common quantity.
def coverage_rows(db):
    today=date.today()
    protocols=list(db.scalars(select(Protocol).where(Protocol.is_active.is_(True)).options(selectinload(Protocol.items)).order_by(Protocol.name,Protocol.id)))
    compounds={c.id:c.name for c in db.scalars(select(Compound))}
    vials=defaultdict(list)
    for vial in db.scalars(select(Vial)):
        vials[vial.compound_id].append(vial)
    rows=[]
    for protocol in protocols:
        for item in protocol.items:
            stock=vials[item.compound_id]
            available=[]
            expired=0
            closed=0
            for vial in stock:
                if vial.closed_on is not None or (vial.status or '').lower() in ('closed','empty','discarded','depleted','used','disposed'):
                    closed+=1
                    continue
                if any(d is not None and d<today for d in (vial.expires_on,vial.beyond_use_on)):
                    expired+=1
                    continue
                available.append(vial)
            available.sort(key=lambda v:((v.expires_on or date.max),(v.beyond_use_on or date.max),v.id))
            nearest=min((d for v in available for d in (v.expires_on,v.beyond_use_on) if d is not None),default=None)
            rows.append({
                'protocol':protocol.name,'protocol_id':protocol.id,
                'compound':compounds.get(item.compound_id,f'Compound #{item.compound_id}'),
                'compound_id':item.compound_id,
                'planned':f'{item.amount_value:g} {item.amount_unit}',
                'frequency':f'{item.freq_count:g} / {item.freq_period}',
                'available':len(available),'excluded_expired':expired,'excluded_closed':closed,
                'next_date':nearest.isoformat() if nearest else '',
                'flag':'Review inventory' if not available else ('Expires within 30 days' if nearest and 0<=(nearest-today).days<=30 else 'Vials present'),
            })
    return rows

@router.get('/protocol-coverage')
def protocol_coverage(request:Request, db:Session=Depends(get_db)):
    rows=coverage_rows(db)
    return templates.TemplateResponse(request,'protocol_coverage.html',{'path':'/protocol-coverage','rows':rows,'protocol_count':len(set(r['protocol_id'] for r in rows))})

@router.get('/protocol-coverage.csv')
def protocol_coverage_csv(db:Session=Depends(get_db)):
    rows=coverage_rows(db)
    fields=['protocol','compound','planned','frequency','available','excluded_expired','excluded_closed','next_date','flag']
    buffer=io.StringIO()
    writer=csv.DictWriter(buffer,fieldnames=fields,extrasaction='ignore')
    writer.writeheader()
    for row in rows:
        writer.writerow({key: ("'"+str(row[key]) if isinstance(row[key],str) and row[key].lstrip().startswith(('=','+','-','@')) else row[key]) for key in fields})
    return StreamingResponse(iter([buffer.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="protocol-coverage.csv"','Cache-Control':'no-store'})
