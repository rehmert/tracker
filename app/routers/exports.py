"""CSV exports for user-owned records; no third-party services."""
import csv
import io
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Compound, DoseLog, Purchase, Supply, Vial, VitalReading
from ..templating import render

router = APIRouter()
DATASETS = {
    'vitals': (VitalReading, ('id','measured_at','weight_kg','systolic','diastolic','pulse_bpm','context','notes')),
    'doses': (DoseLog, ('id','vial_id','taken_at','entered_value','entered_unit','amount_base','kind','site','notes')),
    'vials': (Vial, ('id','compound_id','purchase_id','label','lot','form','content_value','content_unit','volume_ml','expires_on','status','unit_price_cents','notes')),
    'supplies': (Supply, ('id','purchase_id','compound_id','name','kind','purchased_qty','remaining_qty','unit_price_cents','notes')),
    'purchases': (Purchase, ('id','vendor','purchased_on','order_ref','shipping_cents','tax_cents','discount_cents','notes')),
    'compounds': (Compound, ('id','name','category','notes')),
}

def csv_text(db: Session, dataset: str) -> str:
    if dataset not in DATASETS: raise ValueError('Unknown dataset')
    model, fields = DATASETS[dataset]
    stream=io.StringIO(newline='')
    writer=csv.writer(stream)
    writer.writerow(fields)
    for obj in db.scalars(select(model).order_by(model.id)):
        values=[]
        for field in fields:
            value=getattr(obj,field)
            if isinstance(value,(date,datetime)): value=value.isoformat()
            if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@','\t','\r')): value="'"+value
            values.append(value)
        writer.writerow(values)
    return stream.getvalue()

@router.get('/exports')
def index(request: Request):
    return render(request,'exports.html',datasets=DATASETS)

@router.get('/exports/{dataset}.csv')
def download(dataset: str,db: Session=Depends(get_db)):
    if dataset not in DATASETS: raise HTTPException(404,'Unknown export')
    content=csv_text(db,dataset)
    return StreamingResponse(iter([content]),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="tracker-{dataset}.csv"','Cache-Control':'no-store'})
