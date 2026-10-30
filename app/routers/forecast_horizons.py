"""Read-only multi-horizon average-demand comparisons."""
import csv
import io
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ..db import get_db
from ..templating import render
from .inventory_forecast import build_rows

router = APIRouter()
HORIZONS = (7, 14, 28, 56)

def compare_horizons(db):
    # Reuse existing inventory logic; do not independently recalculate stocks.
    result = {}
    for days in HORIZONS:
        for row in build_rows(db, days=days):
            key = (row['protocol_id'], row['compound'], row['unit'])
            item = result.setdefault(key, dict(protocol=row['protocol'],
                compound=row['compound'], unit=row['unit'], available=row['available'],
                vials=row['vials'], horizons={}, duplicates=False))
            if days in item['horizons']:
                item['duplicates'] = True
                item['horizons'][days] = None
            else:
                item['horizons'][days] = dict(demand=row['demand'], status=row['status'])
    return sorted(result.values(), key=lambda r:(r['compound'].lower(),r['protocol'].lower()))

@router.get('/forecast-horizons')
def forecast_horizons(request: Request, db: Session = Depends(get_db)):
    return render(request, 'forecast_horizons.html', rows=compare_horizons(db), horizons=HORIZONS)

@router.get('/forecast-horizons.csv')
def forecast_horizons_csv(db: Session = Depends(get_db)):
    output=io.StringIO(); writer=csv.writer(output)
    writer.writerow(['Protocol','Compound','Unit','Eligible vials','Approx remaining',
        'Multiple items warning']+[f'Approx demand {d}d' for d in HORIZONS]+
        [f'Planning flag {d}d' for d in HORIZONS])
    for row in compare_horizons(db):
        writer.writerow([row['protocol'],row['compound'],row['unit'],row['vials'],
            round(row['available'],4),'YES' if row['duplicates'] else '']+
            ['' if row['duplicates'] or row['horizons'].get(d) is None or row['horizons'][d]['demand'] is None
                else round(row['horizons'][d]['demand'],4) for d in HORIZONS]+
            ['' if row['duplicates'] or row['horizons'].get(d) is None
                else row['horizons'][d]['status'] for d in HORIZONS])
    return StreamingResponse(iter([output.getvalue()]), media_type='text/csv',
        headers={'Content-Disposition':'attachment; filename="forecast-horizons.csv"'})
